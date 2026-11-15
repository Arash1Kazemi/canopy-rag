import copy

import pytest

from baseline_runner.ollama_api import OllamaClient, OllamaError, stats_from


class Spy:
    """A spy: a transport that records what was sent and returns a canned reply."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def __call__(self, method, path, payload):
        self.sent.append((method, path, copy.deepcopy(payload)))  # a copy: the client may change the payload later
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


REPLY = {"message": {"content": "25"}, "total_duration": 3_000_000_000, "load_duration": 1_000_000_000,
         "prompt_eval_count": 100, "prompt_eval_duration": 500_000_000, "eval_count": 20, "eval_duration": 2_000_000_000}


def test_durations_in_nanoseconds_become_seconds_and_rates():
    stats = stats_from(REPLY)
    assert stats.total_s == 3.0 and stats.load_s == 1.0 and stats.prompt_s == 0.5
    assert stats.ttft_s == 1.5          # loading plus reading the prompt
    assert stats.tokens_per_s == 10.0   # 20 tokens in 2 seconds


def test_a_reply_without_timings_gives_zeros_not_errors():
    stats = stats_from({})
    assert stats.ttft_s == 0 and stats.tokens_per_s == 0


def test_chat_sends_the_fixed_options_and_returns_the_text():
    spy = Spy([REPLY])
    result = OllamaClient(transport=spy).chat("m", [{"role": "user", "content": "hi"}])
    _, path, payload = spy.sent[0]
    assert path == "/api/chat" and payload["stream"] is False
    assert payload["options"] == {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 256}
    assert "think" not in payload and "format" not in payload
    assert result.text == "25"


def test_an_option_set_to_none_is_dropped():
    spy = Spy([REPLY])
    OllamaClient(transport=spy).chat("m", [{"role": "user", "content": "hi"}], options={"temperature": 0.7, "seed": None})
    options = spy.sent[0][2]["options"]
    assert options["temperature"] == 0.7 and "seed" not in options


def test_images_go_on_the_last_message_and_json_mode_sets_the_format():
    spy = Spy([REPLY])
    OllamaClient(transport=spy).chat("m", [{"role": "user", "content": "read"}], images=["AAAA"], json_mode=True, think=False)
    payload = spy.sent[0][2]
    assert payload["messages"][-1]["images"] == ["AAAA"]
    assert payload["format"] == "json" and payload["think"] is False


def test_a_model_without_thinking_is_asked_again_without_the_setting():
    spy = Spy([OllamaError("HTTP 400: model does not support thinking"), REPLY])
    result = OllamaClient(transport=spy).chat("m", [{"role": "user", "content": "hi"}], think=False)
    assert len(spy.sent) == 2
    assert "think" in spy.sent[0][2] and "think" not in spy.sent[1][2]
    assert result.text == "25"


def test_other_errors_are_not_retried():
    spy = Spy([OllamaError("HTTP 500: out of memory")])
    with pytest.raises(OllamaError):
        OllamaClient(transport=spy).chat("m", [{"role": "user", "content": "hi"}], think=False)
    assert len(spy.sent) == 1


def test_embed_refuses_to_truncate_and_checks_the_count():
    spy = Spy([{"embeddings": [[1, 0], [0, 1]]}])
    result = OllamaClient(transport=spy).embed("m", ["a", "b"])
    assert spy.sent[0][2]["truncate"] is False and spy.sent[0][1] == "/api/embed"
    assert result.vectors == [[1, 0], [0, 1]]
    with pytest.raises(OllamaError):
        OllamaClient(transport=Spy([{"embeddings": [[1, 0]]}])).embed("m", ["a", "b"])


def test_models_lists_tags_with_digests():
    spy = Spy([{"models": [{"name": "qwen3:4b", "digest": "abc"}]}])
    assert OllamaClient(transport=spy).models() == {"qwen3:4b": "abc"}
