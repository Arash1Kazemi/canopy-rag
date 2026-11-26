"""Test area: Answers and citations (context assembly for the answer prompt, Phase 8C)."""
import pytest

from rag_core.knowledge.model import KnowledgeChunk, KnowledgeItemId, SourceLocation, VersionTag
from rag_core.rag.context import ContextHit, assemble_context, context_budget, estimate_tokens
from rag_core.shared.kernel import DomainError


def hit(n, words=20, stem="D10_bus_fleet_inventory_v2", score=None, text=None, **kw):
    return ContextHit(f"D10@2#{n}", text if text is not None else " ".join(f"w{n}x{i}" for i in range(words)), stem, score, **kw)


def test_the_context_is_filled_in_rank_order_in_the_baseline_format():
    ctx = assemble_context([hit(1, text="Fleet is 135 buses."), hit(2, stem="D13_maintenance_schedule_2025", text="Service every 10000 km.")], 1000)
    assert ctx.text == "[D10_bus_fleet_inventory_v2] Fleet is 135 buses.\n\n[D13_maintenance_schedule_2025] Service every 10000 km."
    assert ctx.chunk_ids == ("D10@2#1", "D10@2#2")
    assert ctx.stems == ("D10_bus_fleet_inventory_v2", "D13_maintenance_schedule_2025")
    assert ctx.omitted == ()


def test_the_budget_is_respected_and_a_chunk_is_never_cut():
    hits = [hit(n, words=20) for n in range(1, 6)]
    one = estimate_tokens(hits[0].entry())
    ctx = assemble_context(hits, one * 2 + 1)
    assert ctx.chunk_ids == ("D10@2#1", "D10@2#2")
    assert ctx.estimated_tokens <= ctx.budget_tokens
    assert [(o.chunk_id, o.reason) for o in ctx.omitted] == [(f"D10@2#{n}", "over_budget") for n in (3, 4, 5)]
    for h in ctx.given:                                   # each given chunk is in the text whole
        assert h.text in ctx.text
    for n in (3, 4, 5):                                   # and no part of an omitted chunk is
        assert f"w{n}x0" not in ctx.text


def test_a_big_chunk_ends_the_filling_so_a_lower_chunk_never_replaces_it():
    ctx = assemble_context([hit(1, words=5), hit(2, words=200), hit(3, words=5)], 60)
    assert ctx.chunk_ids == ("D10@2#1",)
    assert [o.reason for o in ctx.omitted] == ["over_budget", "over_budget"]


def test_a_zero_budget_gives_an_empty_context():
    ctx = assemble_context([hit(1)], 0)
    assert ctx.is_empty and ctx.text == "" and ctx.omitted[0].reason == "over_budget"


def test_blank_repeated_and_low_score_hits_are_left_out_and_recorded():
    hits = [hit(1, text="   "), hit(2, text="Real text.", score=0.9), hit(2, text="Real text.", score=0.9),
            hit(3, text="Weak.", score=0.1)]
    ctx = assemble_context(hits, 1000, min_score=0.5)
    assert ctx.chunk_ids == ("D10@2#2",)
    assert [(o.chunk_id, o.reason) for o in ctx.omitted] == [("D10@2#1", "blank"), ("D10@2#2", "repeated"), ("D10@2#3", "below_min_score")]


def test_there_is_no_score_filter_unless_one_is_given():
    assert assemble_context([hit(1, score=-5.0)], 1000).chunk_ids == ("D10@2#1",)


def test_no_hits_give_an_empty_context():
    ctx = assemble_context([], 1000)
    assert ctx.is_empty and ctx.stems == () and ctx.text == ""


def test_the_budget_leaves_room_for_the_reply_and_the_fixed_prompt_text():
    fixed = "word " * 100
    assert context_budget(4096, 256, fixed) == 4096 - 256 - estimate_tokens(fixed)
    assert context_budget(4096, 256) == 3840
    assert context_budget(100, 256, fixed) == 0


def test_the_token_estimate_errs_high_and_grows_with_the_text():
    text = "The fleet has 135 buses."
    assert estimate_tokens(text) >= len(text.split())
    assert estimate_tokens(text + " More words here.") > estimate_tokens(text)
    assert estimate_tokens("D10_bus_fleet_inventory_v2" * 3) >= 25      # one long id is many tokens, not one word


def test_a_hit_is_made_from_a_chunk_with_its_pages_and_headings():
    loc = SourceLocation(KnowledgeItemId("D19"), VersionTag("1"), "N6/D19_meeting_minutes_2025-06-18.pdf", 0, 40, 1, 2, ("Minutes",))
    chunk = KnowledgeChunk("D19@1#2", "N6", 2, "Decision text.", loc)
    h = ContextHit.of_chunk(chunk, 0.77)
    assert (h.chunk_id, h.source_stem, h.score, h.page_start, h.page_end, h.heading_path) == ("D19@1#2", "D19_meeting_minutes_2025-06-18", 0.77, 1, 2, ("Minutes",))
    assert h.citation().render_long() == "[D19_meeting_minutes_2025-06-18, pp. 1-2, Minutes, chunk D19@1#2]"


def test_a_hit_needs_a_chunk_id_and_a_clean_stem():
    with pytest.raises(DomainError):
        ContextHit("", "text", "D10_x")
    with pytest.raises(DomainError):
        ContextHit("D10@2#1", "text", "D10 bad stem")
