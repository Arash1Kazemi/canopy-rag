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
