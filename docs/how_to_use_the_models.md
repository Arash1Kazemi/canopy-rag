# How to use the local models

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: steps 2 and 3 of Phase 2. Status: draft, written before the first real run. Lines marked **(to verify)** have not been tried against a real server yet, and the baseline report says which of them held.

## The idea in one paragraph

The models run in a small local server (Ollama). Our code never loads a model itself. It sends a request to `http://127.0.0.1:11500` and reads the reply. That address is this machine only, so nothing leaves the laptop. Every model is named by a row in `models/model_registry.csv`, every prompt by a row in `prompts/prompt_registry.csv`, and every setting by `baseline_runner/config.py`.

## One-time setup

You need your approval for the downloads, because they are large. Each step says what it fetches.

| Step | What it does | Download |
|---|---|---|
| 1. `scripts/setup_ollama.ps1` | Fetches the standalone Ollama zip, checks its SHA-256 against the published `sha256sum.txt`, and unpacks it into `ollama/` next to the project | `ollama-windows-amd64.zip`, about 1586 MB, from the Ollama GitHub release |
| 2. `scripts/start_ollama.ps1` | Starts the server in a window, with the models kept in `ollama-models/` on E:. The settings apply to that window only | none |
| 3. `python -m baseline_runner pull --tier 1` | Downloads the tier 1 models of the registry (about 10 GB) | the models, from the Ollama library |
| 4. `python -m baseline_runner check` | Tells you whether the server answers and which models are ready | none |

Tier 2 (about 7 GB more) is a separate `pull --tier 2`. Tier 3 models are not downloaded in the first baseline.

After step 3 nothing needs the internet. **(to verify)** The baseline report records a run with the network switched off.

## Using a model from code

```python
from baseline_runner.ollama_api import OllamaClient

client = OllamaClient()                                   # 127.0.0.1:11500
reply = client.chat("qwen3:4b", [{"role": "user", "content": prompt}], think=False)
print(reply.text, reply.stats.tokens_per_s)

vectors = client.embed("qwen3-embedding:0.6b", ["a bus", "a boat"]).vectors
```

Rules for using a model in this project:

1. **Name models through the registry.** Ask the registry for the `runtime_tag`, never type a tag in the middle of the code. A tag in one place means one place to change.
2. **Use the prompt registry.** A prompt is a file with `{{blanks}}`. `Prompts().render("P01", context=..., question=...)` fills it and raises an error if a blank is missing, instead of sending a half-empty prompt.
3. **Use the right prefix for an embedding model.** The same text embedded with the wrong prefix gives a different vector. The registry lists the prefixes under `limits`, and the prompts P05 to P11 apply them.
4. **Keep the settings fixed.** `GENERATION_OPTIONS` sets temperature 0, seed 42, a 4096 context and a reply limit. Change a setting for one run only with a new, named run.
5. **Turn thinking off** for models whose page lists a thinking mode, or their speed and answers are not comparable. The client retries without the setting if a model does not support it.
6. **Never let a prompt grow past the context.** A prompt longer than `num_ctx` may be cut or refused by the server, and a cut prompt loses its end, which is where the question is. The embedding call refuses to cut (`truncate` is false).
7. **Read the timings.** Every reply carries its own durations. The client turns them into time to first token and tokens per second, which are metrics M22 and M23.

## Adding a new model

1. Add a row to the model registry with the source page, the licence source and today's date. Write `not stated` for what the page does not say.
2. If it is an embedding model, read its card for a query or document prefix, add the prompts, and add the pair to `EMBEDDING_PROMPTS` in `config.py`.
3. Download it with `ollama pull <runtime_tag>` and run `python -m baseline_runner e1` or `e2` with `--models <model_id>`.
4. Change its `status` and fill `evaluation_notes` with a pointer to the result folder.
5. Run `python tools/run_checks.py`. It checks the row.

## Proving it runs offline

Hard rule H06 says no code calls an address outside localhost.

- The unit tests block every network connection, so a test that reaches out fails.
- The runner only talks to `OLLAMA_URL`, which is `127.0.0.1`.
- A run with the network switched off is the real proof. Switch Wi-Fi off, start the server, run `check` and one experiment. **(to verify)**
- To see which addresses the server listens on, run `netstat -ano | findstr 11500` in a terminal. **(to verify)** The expected answer is only `127.0.0.1:11500`.

## When something goes wrong

| Symptom | Likely cause | What to do |
|---|---|---|
| `cannot reach Ollama` | The server window is not running | Run `scripts/start_ollama.ps1` and leave it open |
| `model not found` | The model is not downloaded | `python -m baseline_runner pull --tier 1`, or `ollama pull <tag>` |
| A reply takes minutes | The model does not fit the GPU, so part runs on the CPU | `ollama ps` shows the GPU and CPU split. Use a smaller model or a shorter context |
| `out of memory` | Another program holds GPU memory, or the context is too large | Close other programs, lower `num_ctx`, or use a smaller model |
| Empty answer from a thinking model | The reply limit ended while the model was still thinking | Make sure thinking is off for that model |
| A strange error about thinking | The model has no thinking mode | The client already retries without it |

## What this method does not cover

It does not cover serving many users, a second computer, or models bigger than this laptop can hold. Those are later concerns, and the client is the one place to change.
