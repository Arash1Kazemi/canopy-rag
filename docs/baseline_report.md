# Offline model baseline report

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: the runs of 2026-10-28 in `results/`, the plan in `docs/prompt_test_plan.md`, and the metrics in `metrics/metrics.csv`. Status: first baseline, for supervisor review.

## 1. Summary

All six experiments ran fully offline on the laptop (Ryzen 7 6800H, 15.3 GB RAM, RTX 3050 Laptop 4 GB), with Ollama 0.40.11 and the seven tier 1 models.

| Part | Baseline choice | Main result |
|---|---|---|
| Embedding model | `qwen3-embedding:0.6b` | Finds every answer-key source in the top 3 chunks (recall 1.00) |
| LLM | `phi4-mini:3.8b` | 21 of 23 answerable questions correct, all 3 refusals correct, 0.7 s per question |
| LVM | `glm-ocr:q8_0` | Reads all 7 facts of the scanned minutes, clean or degraded, but takes about a minute per page |
| Hard rule H01 | holds | 0 chunks from another node in any real run |

Two planted problems fail as expected: the model picks one route instead of reporting the conflict (Q06), and it cites the duplicate file twice (Q03). These are the problems Phases 5 and 12 are meant to solve, so the baseline shows they are real.

One model result is **not valid**: `qwen3:4b`. Ollama's metadata shows this tag is the "Thinking" fine-tune, which always writes its reasoning first. Our setting to switch thinking off had no effect, so its answers are reasoning cut off at the reply limit. It is excluded from the baseline and must be rerun with the tag `qwen3:4b-instruct`.

## 2. Setup

| Setting | Value |
|---|---|
| Runtime | Ollama 0.40.11, standalone zip, checksum verified, server on `127.0.0.1:11500` |
| Generation | temperature 0, seed 42, context 4096 tokens, reply limit 256 tokens (1024 for a page) |
| Chunks | `words80` (80 words, 15 overlap), 35 chunks, with `file` (22 chunks) for comparison |
| Prompts | P01 version 1 frozen before the run, and the embedding prefixes from the model cards |
| Model digests | recorded in `meta.json` of every run |

Port note: Ollama's default port 11434 was reserved by Windows after a restart (range 11379 to 11478), so the server uses 11500.

## 3. E1: retrieval

With the `words80` chunks:

| Embedding model | Hit at k=1 | Hit at k=3 | Precision at k=3 | Recall at k=3 |
|---|---:|---:|---:|---:|
| `nomic-embed-text` | 0.91 | 1.00 | 0.53 | 1.00 |
| `embeddinggemma:300m` | 0.96 | 1.00 | 0.59 | 1.00 |
| `qwen3-embedding:0.6b` | 0.91 | 1.00 | 0.57 | 1.00 |

- All three find every answer-key source at k=3. The plan's rule (best recall at k=3, then prefer multilingual) leaves a tie between `embeddinggemma` and `qwen3-embedding`. We chose `qwen3-embedding` for its longer context. `embeddinggemma` is one question better at k=1, which is within noise for 23 questions.
- Precision at k=3 cannot reach 1 for questions with one source file, because 3 chunks are returned. It is a ceiling, not a weakness.
- `words80` beats one chunk per file at k=1 for every model (for example 0.91 against 0.87 for `nomic-embed-text`).
- Indexing all chunks takes under 2.2 seconds with any model.

The case study is too small to separate these models. A larger set of documents is needed before the embedding choice is final.

## 4. E2 and E3: answers

After the grading fixes of section 8:

| | E2: right files given | E3: real retrieval |
|---|---:|---:|
| M01 answer correctness | 0.96 (22 of 23) | 0.91 (21 of 23) |
| M02 citation validity | 0.96 | 0.87 |
| M03 correct refusal | (not asked) | 1.00 (3 of 3) |
| M04 false refusal | 0.00 | 0.00 |
| M09 version handling | 1.00 | 1.00 |
| M12 duplicate cited once | 1.00 | 0.00 |
| M14 terminal node accuracy | 1.00 | 1.00 |
| M22 time to first token, median | 0.14 s | 0.21 s |
| M23 generation speed, median | 37.9 tokens/s | 37.5 tokens/s |
| M24 question latency, median and 90th percentile | 0.64 s, 1.46 s | 0.70 s, 1.52 s |

All values are for `phi4-mini`.

What the failures are, read one by one:

| Question | What happened | Kind |
|---|---|---|
| Q06 (both runs) | Answers "Route 12" only, and does not report the conflict | Model limit: the planted contradiction |
| Q03 (E3) | Retrieval returns the file and its copy, and the model cites both | The planted duplicate: retrieval brings both, so the cost of retrieval here is exactly the duplicate |
| Q04, Q08 (E3) | Right answer, no citation ("18", "Route 7") | Model does not always follow the citation rule on very short answers |
| Q13 (E3) | Right answer, also cites D17, which mentions the same data check | Strict citation rule: debatable, counted as a failure |

The model refused all three questions it should refuse (Q22 node boundary, Q23 and Q24 unanswerable), and it never refused an answerable one. It used version 2 of the fleet inventory for "now" and version 1 for "January", even though both versions were in the index.

## 5. E4: reading the scanned minutes

| LVM | Page | Facts found | Time |
|---|---|---:|---:|
| `glm-ocr:q8_0` | clean | 7 of 7 | 73 s |
| `glm-ocr:q8_0` | turned and blurred | 7 of 7 | 60 s |
| `qwen3-vl:2b` | clean | 5 of 7 | 20 s |
| `qwen3-vl:2b` | turned and blurred | 7 of 7 | 11 s |

`glm-ocr` copied the page exactly in both cases. `qwen3-vl` read everything it returned correctly, but on the clean page it stopped early, in the middle of the "Actions" lines, which is why two dates are missing. Its result on the harder page was perfect, so this is unreliability, not a reading limit. A drawn page is easier than a real scan, so the real test comes in Phase 4.

## 6. E5: judge probe

| Judge | Setting | Accuracy | M20 repeatability | Accuracy on the 2 blind spots |
|---|---|---:|---:|---:|
| `phi4-mini` | fixed | 0.98 | 1.00 | 1.00 |
| `phi4-mini` | sampled | 0.98 | 1.00 | 1.00 |
| `qwen3:4b` | fixed | 1.00 | 0.98 | 1.00 |
| `qwen3:4b` | sampled | 1.00 | 1.00 | 1.00 |

Both judges separate right from wrong answers almost perfectly, and both catch the two reversed answers that the string rule wrongly accepts (load "rose from 71% to 94%", and the swapped water figures). This is the easiest case for a judge, because the reference is the expected answer itself. It shows that a small local judge is worth testing on real transfer packages (Phase 11). It does not show that it is ready to accept or reject them.

## 7. E6: speed and memory as the prompt grows

For `phi4-mini` on Q06, Q12 and Q25:

| Chunks | Prompt tokens, max | Time to first token | Speed | Latency median |
|---:|---:|---:|---:|---:|
| 1 | 249 | 0.14 s | 35.9 tokens/s | 2.7 s |
| 3 | 498 | 0.27 s | 35.9 tokens/s | 3.7 s |
| 6 | 816 | 0.44 s | 34.4 tokens/s | 4.1 s |
| 12 | 1442 | 0.80 s | 30.0 tokens/s | 2.6 s |

The time to first token grows with the prompt, as expected: about six times longer for 12 chunks than for 1. Generation slows by about 16 percent. GPU memory in use stayed between 3.2 and 3.4 GB of the 4 GB, including about 1.2 GB that Windows uses. Even at 12 chunks the prompt is well under the 4096-token context, so this laptop is not near its limit for a question. The latency medians are over only three questions and move with answer length, so they are noisy.

## 8. Corrections made while reading the results

The plan says a human reads every failure, and each one is either a model error or a grading-rule bug. Four were rule bugs, fixed in `metrics/key_facts.csv` and regraded with the new `regrade` command. The original files are kept, and the regraded ones sit next to them.

| Question | The answer that failed | Why the rule was wrong | New rule |
|---|---|---|---|
| Q07 | "Shorter waits at peak hours" | The question asks what, not what share | `shorter wait` or `58` |
| Q08 | "Route 7" | The question asks which route, not how many complaints | `route 7` only |
| Q17 | "35 … not yet been reached" | The measured 39 is extra detail | `35` and "not reached" |
| Q19 | "11.4 million cubic metres … 12%" | The same loss, as the document gives it in volume | `22` or `11.4`, and `12` |

With these fixes M01 for `phi4-mini` with real retrieval went from 0.74 to 0.91. This shows how much a grading rule can move a metric, which is why both numbers are reported.

## 9. Problems found in the setup, and what we did

| Problem | Effect | Status |
|---|---|---|
| `qwen3:4b` is the Thinking fine-tune | Its answers are reasoning, cut at 256 tokens; its numbers are not valid | Marked rejected in the registry. Rerun with `qwen3:4b-instruct` |
| Port 11434 reserved by Windows after a restart | The server would not start | Moved to port 11500 in the script, the code and the docs |
| The Ollama installer was tried and removed during the runs | `pull` failed with "upgrade in progress" and "could not locate ollama app" until it was gone | Resolved. The user PATH still lists the removed install folder, which is harmless |
| `ollama ps` was not recorded in E6 | The GPU and CPU split of each model is unknown | The runner looks for `ollama` on the PATH. The operator guide now sets `OLLAMA_EXE` |
| The RAM reading is far too low (44 to 63 MB) | M25 for system memory is not trustworthy | Only GPU memory is reported as the baseline |
| The offline test (H06) was not done yet | "Runs with the network off" is not yet proven | Next step in the operator guide |

## 10. Baseline values now in metrics.csv

M01 0.913, M02 0.870, M03 1.000, M04 0.000, M06 1.000, M07 0.572, M08 1.000, M09 1.000, M12 0.000, M13 1.000, M14 1.000, M20 1.000, M22 0.21 s, M23 37.5 tokens/s, M24 0.70 s median and 1.52 s at the 90th percentile, M25 3255 MB of GPU memory in use. Each has its source run in `baseline_source`. No target was set.

## 11. What these results do not show

- 26 questions on short documents. One question is about 4 percentage points, and the embedding models could not be separated.
- One run per setting. At temperature 0 runs repeat well, but this was not measured beyond the judge probe.
- Models and grading were checked against the same questions that are reported. Four grading rules were changed after reading the answers, in the open, but new unseen questions are still needed before the design is final.
- A drawn page, not a real scan.

## 12. Next steps

1. Rerun E2, E3, E5 and E6 with `qwen3:4b-instruct`, so there is a fair second LLM.
2. Run the offline test of the operator guide, with Wi-Fi off.
3. Rerun E6 with `OLLAMA_EXE` set, to record the GPU and CPU split.
4. Take this report and the baselines to the supervisor and agree the targets.
5. Write new questions that no prompt was tuned on, before the Phase 3 design is final.
