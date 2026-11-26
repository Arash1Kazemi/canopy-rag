# Operator guide (what you run yourself, step by step)

This is the runbook for the real runs. You type the commands, and each step says what it does, what you should see, and what to do if it fails. Do the steps in order. Every command goes in PowerShell.

Paths used below:

- Project: `E:\UNI\Semesterr 7\AI-Engineering\UNI-Project`
- Ollama program: `E:\UNI\Semesterr 7\AI-Engineering\ollama\ollama.exe`
- Downloaded models: `E:\UNI\Semesterr 7\AI-Engineering\ollama-models`
- Python: `E:\UNI\Semesterr 7\AI-Engineering\.venv\bin\python.exe`

## The two windows

You always use two PowerShell windows. They do not share settings, so each new window needs its own setup lines.

| Window | Job | Stays open? |
|---|---|---|
| Window 1: server | Runs the model server | Yes, the whole time |
| Window 2: work | Downloads models, runs tests and experiments | You can close it any time |

## Part 1: start of every session

**Window 1.** Start the server:

```powershell
& "E:\UNI\Semesterr 7\AI-Engineering\UNI-Project\scripts\start_ollama.ps1"
```

You should see `Listening on 127.0.0.1:11500` and your `NVIDIA GeForce RTX 3050`. Leave it open.

- If it says `forbidden by its access permissions`, Windows reserved the port after a restart. Check the reserved ranges with `netsh interface ipv4 show excludedportrange protocol=tcp`. If 11500 is inside a range, tell me, and we pick another port. It must be changed in three places: the script, `baseline_runner/config.py`, and the lines below.
- If it says the address is already in use, the server is already running in another window. Use that one.

**Window 2.** Set up the window (every new window, every time):

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11500"
$env:OLLAMA_MODELS = "E:\UNI\Semesterr 7\AI-Engineering\ollama-models"
$ollama = "E:\UNI\Semesterr 7\AI-Engineering\ollama\ollama.exe"
$py = "E:\UNI\Semesterr 7\AI-Engineering\.venv\bin\python.exe"
$env:OLLAMA_EXE = $ollama
cd "E:\UNI\Semesterr 7\AI-Engineering\UNI-Project"
```

What these do: the first tells the `ollama` command which server to talk to. The second tells it where the models are stored. The next two are shortcuts, so later commands are short. `OLLAMA_EXE` lets the runner record `ollama ps`, the GPU and CPU split of a model. The `cd` moves into the folder the runner needs.

## Part 2: download the models

Only the models you do not have yet. Look at what you have:

```powershell
& $ollama list
```

The seven tier 1 models, in the order that is most useful. After each group you can already run some experiments.

| Group | Command | Size | What it enables |
|---|---|---|---|
| 1 | `& $ollama pull nomic-embed-text:v1.5` | 0.27 GB | (done) |
| 2 | `& $ollama pull embeddinggemma:300m` and `& $ollama pull qwen3-embedding:0.6b` | 1.3 GB | E1: compare embedding models |
| 3 | `& $ollama pull qwen3:4b` | 2.5 GB | E2, E3, E5, E6: the answering tests |
| 4 | `& $ollama pull phi4-mini:3.8b` | 2.5 GB | A second LLM to compare |
| 5 | `& $ollama pull qwen3-vl:2b` and `& $ollama pull glm-ocr:q8_0` | 3.7 GB | E4: reading the scanned page |

Notes:

- On `pull`, you should see `pulling ...` bars, then `verifying sha256 digest`, then `success`.
- If a pull stops (network, sleep, Ctrl+C), run the same command again. It continues where it stopped.
- Your speed was about 0.5 MB per second, so the whole set takes hours. Start a pull before you go to lunch.
- Disk: models go to drive E:, which has about 50 GB free.

Tier 2 (`qwen3:1.7b`, `llama3.2:3b`, `qwen3.5:2b`, `bge-m3:567m`) is optional and was not approved yet. Skip it.

## Part 3: check that everything works

In Window 2:

```powershell
& $py -m baseline_runner check
```

You should see `server version: 0.40.11`, a line `ready` for each downloaded shortlisted model, and `missing` for the tier 2 ones (that is fine). Also run:

```powershell
& $py -m pytest
```

Expected: `63 passed` (the 2 tests that need a server are skipped by default). To also run those 2 against your server:

```powershell
& $py -m pytest -m integration
```

And from the project folder, the data and page checks:

```powershell
& $py -I "E:\UNI\Semesterr 7\AI-Engineering\UNI-Project\tools\run_checks.py"
```

Expected: `6 of 6 validators passed`.

## Part 4: prepare the scanned page

```powershell
& "E:\UNI\Semesterr 7\AI-Engineering\UNI-Project\scripts\render_d19.ps1"
```

This draws the minutes D19 as two pictures: a clean one and a turned, blurred one. It uses only Windows and downloads nothing. It lists `d19_clean.png` and `d19_degraded.png` in `results\inputs`. Open them and look: they should be readable pages of text.

## Part 5: run the experiments

Every command makes a folder `results\<run id>` with CSV files and `meta.json`. Always give a run id, so you can find it. Open the CSV files with Excel or VS Code. Run them in this order.

A model name here is the registry id (for example `qwen3-4b`), not the tag.

**E1: which embedding model finds the right documents?**

```powershell
& $py -m baseline_runner e1 --run-id e1-first
```

Open `results\e1-first\e1_summary.csv`. Columns: `M06_hit`, `M07_precision`, `M08_recall`, for each model, chunk setting and k. Choose the model with the best `M08_recall` at k of 3 and chunks `words80`. If two are within one question of each other, prefer the multilingual one. Write down the winner. Call it `<winner>` below. The ids are `nomic-embed-text`, `embeddinggemma-300m`, `qwen3-embedding-0.6b`.

**E2: how well does each LLM answer when retrieval cannot fail?**

```powershell
& $py -m baseline_runner e2 --models qwen3-4b,phi4-mini --run-id e2-first
```

Open `e2_summary.csv` and `e2_rows.csv`. The rows file has every answer next to its grading.

**E3: the whole path**

```powershell
& $py -m baseline_runner e3 --embedding <winner> --models qwen3-4b,phi4-mini --run-id e3-first
```

Compare `M01` here with `M01` in E2. The gap is the cost of retrieval mistakes. Look at `M03` (refusals) and `M12` (the duplicate).

**E4: reading the scanned page** (needs `qwen3-vl:2b` and `glm-ocr:q8_0`)

```powershell
& $py -m baseline_runner e4 --run-id e4-first
```

Open `e4_rows.csv`. `M13` is the share of the seven facts found, `missing` lists the ones not found, and `text` is what the model read.

**E5: the judge probe**

```powershell
& $py -m baseline_runner e5 --models qwen3-4b,phi4-mini --run-id e5-first
```

It asks 52 questions twice per model and setting, so it takes a while. Read `accuracy` and `M20_repeatability` in `e5_summary.csv`.

**E6: speed and memory with more context**

```powershell
& $py -m baseline_runner e6 --embedding <winner> --models qwen3-4b,phi4-mini --run-id e6-first
```

Open `e6_summary.csv`: see how `M24_median`, `M23`, and the memory columns change with `k`. The `ollama_ps` column shows how much of the model is on the GPU and how much on the CPU.

While a model runs, you can watch it in a third window:

```powershell
& $ollama ps
nvidia-smi
```

`PROCESSOR` shows, for example, `100% GPU` or `40%/60% CPU/GPU`. A model that does not fully fit the GPU is slower.

### Good habits while running

1. Close big programs (browsers with many tabs, games), because Windows already uses about 1.2 GB of the GPU memory.
2. Do not change anything in the prompts or settings during a run.
3. One experiment at a time. Wait for the `results in ...` line.
4. If a command fails halfway, read the last lines of the error and tell me. The files already written stay in the results folder.

## Part 6: finish

1. Read every wrong answer in `e3_rows.csv`: filter the `correct` column for `False`. Decide for each: a model mistake, or a grading rule bug? Write short notes in a text file. The plan says a human reads every failure.
2. Tell me when the runs are done. I will read the results, write `baseline_report.md`, fill the baseline values and their sources in `metrics.csv`, update the registry notes, and write the final report.
3. Stop the server: go to Window 1 and press Ctrl+C. Close both windows.

## Proving it works offline (H06)

After the models are downloaded, the experiments do not need the internet.

1. Start the server and run `check` (Part 1 and Part 3) once as usual.
2. Turn Wi-Fi off. Run one short experiment: `& $py -m baseline_runner e2 --models qwen3-4b --run-id offline-test`.
3. Compare the answers with `e2-first`. They should be the same, because the settings are fixed.
4. Write down whether it worked. If the server refuses to start without a connection, that is an important finding, and I want to know.

## Prepared runs (not run yet)

Status for every run in this section: prepared, not run (2026-11-26). Nothing here has been run by the agent. Each part says what the code already supports and what needs a change first. Do the parts in order, and do not start a part until the one before it is done.

### A. Rerun the baseline with `qwen3:4b-instruct`

Status: prepared, not run (2026-11-25). Needs a change first: the runner has no registry row for this tag (see below).

The tag `qwen3:4b` is the thinking fine-tune and was rejected (`models/model_registry.csv`). The instruct tag is a separate model, so it gets its own registry id, and the run gets its own label.

1. Download it (Window 2, while online). Check the size in the output first:

```powershell
& $ollama pull qwen3:4b-instruct
& $ollama list
```

You should see `qwen3:4b-instruct` in the list. If the pull says `pull model manifest: file does not exist`, the tag name is wrong. Tell me and do not guess another one.

2. Needs a change: add one row to `models/model_registry.csv` with `model_id` `qwen3-4b-instruct` and `runtime_tag` `qwen3:4b-instruct`, and set `thinking_listed` to the value you read from the server. Without this row the runner stops with `unknown model ids` (for `--models`) or fails in `thinking_off` (it reads the registry). I (or a tutor session) make that change, then the checks must still say `6 of 6`.

3. Run it as its own labelled run, once the row exists (Window 2):

```powershell
& $py -m baseline_runner e2 --models qwen3-4b-instruct --run-id e2-qwen3-4b-instruct
```

Compare `results\e2-qwen3-4b-instruct\e2_summary.csv` with the `qwen3-4b` row of `results\e2-first\e2_summary.csv`. Do not overwrite `e2-first`: the run id is the label. The `llm` column in the CSV files shows which model answered.

### B. Offline run with Wi-Fi off

Status: prepared, not run (2026-11-25). The code already supports it: the runner talks only to `127.0.0.1:11500` (`baseline_runner/config.py`). No change needed. Uses `phi4-mini`, so it works now and can be compared with `e2-first`.

1. Start the server (Part 1) and run `check` (Part 3) while online.
2. Turn off Wi-Fi: Settings, Network and internet, Wi-Fi, switch it Off. If you use a network cable, unplug it.
3. Verify that the internet is gone and the local server is still there (Window 2):

```powershell
Test-NetConnection -ComputerName 1.1.1.1 -Port 443
Test-NetConnection -ComputerName 127.0.0.1 -Port 11500
```

Expected: the first line says `TcpTestSucceeded : False`, the second says `TcpTestSucceeded : True`. If the first says True, you are still online: do not start the run, tell me.

4. Run it:

```powershell
& $py -m baseline_runner e2 --models phi4-mini --run-id e2-phi4-mini-offline
```

5. Turn Wi-Fi back on. Compare `results\e2-phi4-mini-offline\e2_rows.csv` with the `phi4-mini` rows of `results\e2-first\e2_rows.csv`. The answers should match, because the settings are fixed (`seed` 42, temperature 0). If the server refuses to start or the run fails without a connection, that is an important finding: write down the error and tell me.

### C. Record `ollama ps` and `nvidia-smi` during a run

Status: prepared, not run (2026-11-25). The code already supports it: `scripts/save_ollama_ps.py` (no change needed). Run it in a third window while an experiment runs in Window 2.

Window 3, set up the same way as Window 2 (Part 1), then start the sampler. The example takes 20 snapshots, 30 seconds apart, into the folder of the run that is running in Window 2:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11500"
$env:OLLAMA_EXE = "E:\UNI\Semesterr 7\AI-Engineering\ollama\ollama.exe"
$py = "E:\UNI\Semesterr 7\AI-Engineering\.venv\bin\python.exe"
cd "E:\UNI\Semesterr 7\AI-Engineering\UNI-Project"
& $py scripts\save_ollama_ps.py --out results\e6-first --every 30 --count 20
```

- Each snapshot is one file, `results\e6-first\ollama_ps_<UTC time>.txt`, with the `ollama ps` table and the `nvidia-smi` output. Open a few and look at `PROCESSOR`.
- If `nvidia-smi` is not found, the file says `not available`. The run is not stopped. Run `where.exe nvidia-smi` to find it.
- Ctrl+C stops the sampler early; the files already written stay.
- Use the run id of the run in Window 2, so the files sit next to its CSV files.

### D. Experiment E3: `words80` against `sections80`

Status: prepared, not run (2026-11-25). The switch now exists: `--chunks sections80` cuts the documents with the core's `sections80` policy (`baseline_runner/chunking.py`, tested in `tests/test_experiments_chunking.py`), and `--chunks` refuses a name it does not know.

The baseline already exists: `results\e3-first` is `words80` with `k` 3 and the embedding `qwen3-embedding-0.6b`. For a fair comparison, run both settings on the same day, changing only the chunk setting:

```powershell
& $py -m baseline_runner e3 --embedding qwen3-embedding-0.6b --chunks words80 --k 3 --models phi4-mini --run-id e3-words80
```

```powershell
& $py -m baseline_runner e3 --embedding qwen3-embedding-0.6b --chunks sections80 --k 3 --models phi4-mini --run-id e3-sections80
```

Compare `results\e3-sections80\e3_summary.csv` with the `phi4-mini` row of `results\e3-first\e3_summary.csv`. Look at `M01`, `M02`, `M03` and `M12`. Also look at `M24_median`, because `sections80` may make the chunks shorter. Add `--models qwen3-4b-instruct` to both runs only after part A is done. Keep `--k 3` and the embedding the same in both runs; otherwise the comparison is not fair.

### E. Measure M15: sub-issue suggestions for I01

Status: prepared, not run (2026-11-26). The code is ready (`rag_core/workflows/issues.py`, prompt P12 in `prompts/suggest_sub_issues_v1.txt`). It needs the Ollama server (Part 1) and the chat model from Part 2. Nothing is saved to the database by this step.

```powershell
& $py -m rag_core suggest-sub-issues --issue I01 --out results/issues/m15_I01_suggestions.csv
```

Then read the CSV and match each suggestion by hand against I02, I03 and I04 (the sub-issues that already exist). Count the matches. That count is the M15 baseline, with the run date and the model tag as its source. Do not write a target. To keep a suggestion, use `accept-sub-issues` (it saves the chosen ones in one transaction).

### F. Phase 8 evaluation

Status: prepared, not run (2026-11-26). The code is ready and tested with fakes (`rag_core/cli_rag.py`, `rag_core/evaluation.py`, `tests/test_core_cli_rag.py`). It needs the server (Part 1) and two models you already have from Phase 2: `qwen3-embedding:0.6b` and `phi4-mini:3.8b`. Run it in Window 2 (set up as in Part 1). Nothing is downloaded. Book: chapter 6 (retrieval and RAG) and chapter 5 for the prompt.

Every command exits with 0 when it worked (a refusal is a result, not an error). It exits with 2 and one printed line when it cannot run: the server is not running, a model is not pulled, there is no index yet, or the results folder already holds a run. Add `--fake-models` to any of them to test the pipeline with no model at all.

1. Index the case study into its own database file. It ingests the Markdown files, embeds the 33 chunks of active versions and stores the vectors:

```powershell
& $py -m rag_core index --db results\phase8\knowledge.sqlite --embedding qwen3-embedding-0.6b
```

Expected: `indexed 33 chunks of active versions: 33 embedded now`. Run it again: it must say `0 embedded now` and `33 already indexed`.

2. Ask the three planted problems, one at a time. Read the retrieved list first (scores, files, `in context` or `left out`), then the answer, then the citations:

```powershell
& $py -m rag_core ask --db results\phase8\knowledge.sqlite --node N6 "What is the allowed chlorine residual in drinking water?" --k 5
& $py -m rag_core ask --db results\phase8\knowledge.sqlite --node N2 "What is the allowed chlorine residual in drinking water?"
& $py -m rag_core ask --db results\phase8\knowledge.sqlite --node N4 "How many buses does the Transit Agency have now?"
& $py -m rag_core ask --db results\phase8\knowledge.sqlite --node N6 "Which route is the busiest?"
& $py -m rag_core ask --db results\phase8\knowledge.sqlite --node N6 "Which route is the busiest?" --prompt P13
```

What to look for: the first (Q22 at N6) must be `Refused: yes` and no file of N2 (`D07`, `D08`) may be in the list. The second is the same question at N2, so you can see the answer does exist there. The third (D10) must say 135 and cite `D10_bus_fleet_inventory_v2`, never `v1`. The fourth and fifth (Q06) should name both Route 12 (D11) and Route 7 (D16); the Phase 2 baseline failed this one, and P13 adds a rule for it. Add `--show-chunks` to see the text that was retrieved.

3. Run the 26 questions with the same settings as the Phase 2 baseline (qwen3-embedding-0.6b, phi4-mini, `words80`, k=3, prompt P01):

```powershell
& $py -m rag_core evaluate --run-id phase8-core-p01 --embedding qwen3-embedding-0.6b --llm phi4-mini --prompt P01 --k 3
```

It writes `results\phase8-core-p01\` in the same format as `results\e3-first\` (`e3_rows.csv`, `e3_summary.csv`, `meta.json`, which also records `ollama ps`), plus `comparison.csv`, `comparison.md` and its own `knowledge.sqlite`. The comparison table is printed at the end. It will not write into a folder that already holds a run, so a new try needs a new `--run-id`.

4. Optional, after step 3: the same run with prompt P13 (v2: a conflict rule and "cite only files shown"). Change only the prompt:

```powershell
& $py -m rag_core evaluate --run-id phase8-core-p13 --embedding qwen3-embedding-0.6b --llm phi4-mini --prompt P13 --k 3
```

5. Optional cross-check: the Phase 2 runner with the core as its engine. The default engine is unchanged, so `e3-first` stays reproducible:

```powershell
& $py -m baseline_runner e3 --embedding qwen3-embedding-0.6b --chunks words80 --k 3 --models phi4-mini --engine core --run-id e3-core
```

What to compare (open `comparison.md`, then the rows file):

- `M01` to `M04` and `M09` against the baseline row. The baseline (regraded) is M01 0.913, M02 0.870, M03 1.000, M04 0.000, M09 1.000. Do not write a target.
- Three differences are on purpose (decision A49): the core indexes only active versions (no `D10 v1`, no `D12` copy), it checks every citation against the chunks it gave the model, and an answer with no valid citation becomes a refusal (A44). So `M02` and `M04` can move even if the model's answers do not change. In `e3_rows.csv` look at the `refusal_reason` column: `no_valid_citation` is that rule at work, and `invalid_citations` lists what the model wrote and the core removed.
- `Q03` (the duplicate): the baseline scored M12 0.000 on it. The core has only one D12 file, so the answer cannot cite the copy; if `M12` rises, say that this is the reason (the planted problem is handled before retrieval), not a better model.
- `Q06`: does the answer name both routes, with P01 and with P13? Compare the two runs on this question first, then on all 26: a prompt is promoted only if nothing else gets worse (A47).
- `M06` to `M08`: retrieval alone. The baseline is M06 1.0, M07 0.573, M08 1.0. If they drop, the core's chunks or filter differ from the baseline's.
- `M22` to `M24`: speed. Compare with 0.21 s, 37.5 tokens per second and 0.70 s median. `M05` is `not measured`: the judge comes in Phase 10.

Then tell me the folder names. The evaluation report for `docs/` (the table, the questions that changed and why) is written from the saved files, not from memory.

## Real files (DOCX and PDF) and `--ocr`

The case study keeps Markdown as the source. `scripts/make_real_files.py` makes the real files the manifest names (D04 and D13 as DOCX, D02 and D17 as text PDF, D19 as an image-only PDF):

```powershell
& $py -I scripts/make_real_files.py
& $py -I scripts/make_real_files.py --check
```

The first command makes the files and checks them. `--check` only checks the files that are there. Then ingest them. D19 has no text layer, so it needs the vision model (Ollama running, `glm-ocr:q8_0` pulled):

```powershell
& $py -m rag_core ingest-case-study --ocr
```

Add `--markdown` to read the Markdown files only. Note: `data/project.sqlite` is stale (its manifest has no `real_file` column), so the command prints a note and reads Markdown. Set `$env:RAG_DATA_DB` to a new file path to read the real files.

## Troubleshooting

| What you see | Meaning | What to do |
|---|---|---|
| `cannot reach Ollama at http://127.0.0.1:11500` | Window 1 is not running | Start Part 1 again |
| `model ... not found` | That model is not downloaded | `& $ollama list`, then `pull` it |
| The command says `ollama` is not recognized | The `$ollama` shortcut is missing in this window | Run the setup lines of Part 1 again |
| Python says `No module named baseline_runner` | You are not in the right folder, or you used `-I` | `cd` into the project folder (`UNI-Project`) and run without `-I` |
| Very slow replies | The model does not fit the GPU | Check `& $ollama ps`, close other programs |
| `out of memory` | GPU memory is full | Close programs, or run the smaller model |
| A thinking model gives an empty answer | The reply limit ended during thinking | Tell me. The runner already turns thinking off |
| A pull is stuck at 0 KB/s | The connection dropped | Ctrl+C and run it again |

## What each result means

See `study_notes/06_running_and_limits.md`. The experiment plan and its reasons are in `docs/prompt_test_plan.md`.
