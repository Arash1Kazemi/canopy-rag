# Model registry: structure

The glossary defines the model registry as "a record of the local models in use: their task, limits, and evaluation notes." This page fixes its columns and rules. The data is in `models/model_registry.csv`, and `run_checks.py` enforces the rules below.

## One row per model

| Column | Meaning | Allowed values or format |
| --- | --- | --- |
| model_id | Stable id, never reused | lowercase letters, digits, dots and dashes |
| task | What the model is used for | embedding, llm, lvm |
| runtime_tag | The exact name the local runtime uses to start it | text, such as `qwen3:4b` |
| parameters | Size of the model | text, such as 4B |
| quantization | How the numbers are stored | text, or `not stated` when the source does not say |
| download_gb | Size of the download | a number, in GB, from the source page |
| context_tokens | The longest input the source page lists | a whole number |
| input | What the model accepts | text, or text and image |
| license | The licence, from the model card | text, or `not stated` or `not checked` |
| languages | Languages the source lists | text, or `not checked` |
| thinking_listed | The source page lists a thinking mode | yes or no |
| status | Where the model is in the review | candidate, shortlisted, baseline, rejected |
| tier | The download order | 1 first, 2 second, 3 not downloaded in the first baseline |
| fit_estimate | Whether it fits in the free GPU memory | fits GPU or needs CPU offload |
| limits | Known limits from the source, such as needed prompt prefixes | text |
| evaluation_notes | What our own runs showed | text, empty until the model is run |
| source_url | The page the facts come from | an https address |
| license_source | The page the licence comes from | an https address |
| verified_on | The date the facts were read | YYYY-MM-DD |

## Rules

1. A fact comes from a source page or it is marked `not stated` or `not checked`. We never fill a cell from memory.
2. `fit_estimate` follows one rule from chapter 7 of the book: weights plus about 20 percent, so `download_gb` times 1.2. If that is at most 2.9 GB, the row says `fits GPU`. The 2.9 GB is the free GPU memory of this laptop (4096 MiB minus the 1168 MiB used by Windows when we measured). It is a rough guide, because a longer context needs more memory.
3. `status` changes only after a run. `shortlisted` becomes `baseline` for the model used in the baseline, and `rejected` needs a reason in `evaluation_notes`.
4. Every task has at least one shortlisted model.
5. `evaluation_notes` points to a result file in `results/` and never holds a number without it.

## What the registry is not

It is not the prompt registry (`prompts/prompt_registry.csv`), which lists versioned prompts, and it is not a record of results. Results live in the `results/` folder, one file per run, so a registry row never changes meaning.
