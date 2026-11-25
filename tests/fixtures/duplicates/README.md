# Labelled duplicate pairs (fixtures for metrics M10 and M11)

Small Markdown texts made from the City documents, in labelled pairs. They live here, **not** in `case_study/documents/`, so the answer key and the ingestion counts do not change.

`pairs.csv` has the columns `pair_id,file_a,file_b,label,note`. The files are in this folder. The label is a human judgement about what the pair is meant to be, not the detector's score.

| Label | Meaning | Pairs |
|---|---|---|
| `exact` | Same words; only spaces and line breaks differ | 2 |
| `near` | Same content with edits: one word changed up to five sentences reworded; one is only upper case | 8 |
| `overlap` | A passage of one document copied inside a different document | 8 |
| `different` | Two different documents that share a topic or a table layout | 8 |

Files named `orig_Dxx.md` are copies of the city documents; `near_NN_b.md`, `overlap_NN_b.md` and `exact_NN_b.md` are the planted variants. The `near` pairs run from very light to heavy edits on purpose, so the baseline shows where the detector stops calling a pair near.

Run the detector on them (it saves precision and recall per label to `results/duplicates/labelled-pairs/`):

```bash
../.venv/bin/python.exe -I scripts/duplicate_experiment.py --pairs tests/fixtures/duplicates/pairs.csv
```

The numbers are baselines for M10 and M11, not targets. Do not tune the policy numbers on this set alone and then report the same set as a result.
