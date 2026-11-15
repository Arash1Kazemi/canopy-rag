# Unit-testing rules

Project: offline hierarchical RAG core for organizational knowledge management, issue management, and knowledge transfer.
Source: step 6 of Phase 1, objective 7 of the proposal ("unit tests for the domain logic"), and the hard rules in `metrics/hard_rules.csv`. Status: draft for supervisor review. Date: 2026-10-26.

## What this page decides

It fixes how the project is tested before there is much code: the tool, the folder layout, what a unit test covers, what it must never cover, and how a real model is replaced by a test double. A rule written now saves a rewrite in Phase 3, when the domain code starts.

## Three kinds of checking

| Kind | Checks | Tool | Runs when |
|---|---|---|---|
| Data checks | The CSV and Markdown files agree with each other | `tools/run_checks.py` | Before and after every change |
| Unit tests | Our own code follows our own rules | pytest | Before and after every change |
| Evaluation runs | How good the local models are on the answer key | the baseline runner, then the metrics | After a model, a prompt, or a chunk setting changes |

The most important rule on this page: **a unit test checks our rules, an evaluation checks the models.** A unit test must give the same result on every run, on any laptop, with the network off. A local model gives a different answer on a different run or machine, so its quality is measured by a metric, never by a unit test.

## Tool and layout

- The tool is pytest, with plain functions and `assert`.
- Tests live in a `tests/` folder next to the code they test, and a test file is named after its module: `grading.py` is tested by `tests/test_grading.py`.
- A test name is a sentence about one behavior: `test_a_node_never_gets_a_chunk_from_another_node`.
- One test checks one behavior. A test body has three parts in this order: set up, act, assert.
- A test never changes a case-study file. The case study is read-only test data.
- Three markers sort the tests, and the default run skips the last two.

| Marker | Meaning | In the default run |
|---|---|---|
| `unit` (no marker needed) | Fast, no model, no network | yes |
| `integration` | Talks to a local Ollama on localhost; skipped if it is not running | no |
| `evaluation` | Runs the answer key through real models and writes metrics | no |

## What is tested

Each row is a test area. Every hard rule belongs to at least one area, and every objective has at least one area. Metric M26 counts how many areas have at least one passing test.

| Area | What a test proves | Hard rules | Objective |
| --- | --- | --- | --- |
| Registry and layers | One root, layer equals parent layer plus 1, terminal nodes have no children | H02, H10 | O3 |
| Node isolation | Retrieval for one node never returns a chunk of another node | H01 | O3 |
| Versioning | One active version per item, and an update keeps the old versions | H03, H04 | O2 |
| Duplicates and overlaps | Exact duplicates are found, versions are not flagged as duplicates | none | O2 |
| Chunking | No text is lost, chunks respect the size limit, overlap is as set | none | O2 |
| Retrieval | The top k chunks come back in score order, and the node filter is applied | none | O1 |
| Answers and citations | Citations are parsed, a refusal uses the fixed phrase, no answer is empty | H09 | O1 |
| Grading rules | Every expected answer passes its own rule, and a wrong answer fails | none | O1 |
| Issues | Status and progress follow fixed rules, a sub-issue stays in its parent's node | H07 | O4 |
| Priorities and gaps | The ranking of issues is deterministic, and planted gaps are flagged | H08 | O5 |
| Transfer and judge decision | A package under the threshold is not sent, one at or over is sent | H05 | O6 |
| Prompt templates | Every blank is filled, a missing value is an error, the version is recorded | none | O7 |
| Offline guard | Any call to an address outside localhost fails the test | H06 | O7 |
| RFP | The draft RFP has every required section | none | O8 |

Areas for objectives that are built later (issues, priorities, transfer, RFP) get their tests in the phase that builds them. Until then their tests do not exist, and M26 shows that honestly.

## What is not unit-tested

| Not tested | Why | Measured by |
|---|---|---|
| Whether an LLM answer is right | A local model is not repeatable across machines and settings | M01 to M04 |
| Whether an embedding model finds the right chunk | It depends on the model, not on our code | M06 to M08 |
| Whether the LVM reads a scan correctly | Same reason | M13 |
| Whether the judge agrees with humans | A judge is inconsistent by nature (chapter 3 of the book) | M18 to M20 |
| Speed and memory | They depend on the laptop | M22 to M25 |

Our code around these parts is tested: how a prompt is built, how a reply is parsed, how a number is graded.

## Test doubles

A test double is a simple stand-in for a real part. We use five kinds, all with examples from the city.

| Kind | What it does | Example in this project |
|---|---|---|
| Dummy | Fills a slot and is never used | A node id passed to a function that ignores it |
| Stub | Returns a fixed answer | `StubLLM` that always says "insufficient knowledge" |
| Fake | A real but simplified version | `FakeEmbedder` that turns words into numbers by hashing, with no model |
| Spy | Records how it was called | A client that remembers which prompt was sent |
| Mock | A spy with the expected calls set up in advance | Avoid it: it ties the test to how the code works, not to what it does |

Rules for doubles:

1. The domain code never imports a model library or an HTTP client. It receives an LLM, an embedding model, or an LVM as an argument, and the argument can be real or a double.
2. Use the simplest double that makes the test honest. A stub is enough to test a threshold, and a fake is needed to test retrieval order.
3. A double lives in one place (`fakes.py`) and is tested itself, so a bug in a double does not hide a bug in the code.
4. A test that needs a real model is not a unit test. Mark it `integration` or `evaluation`.

## Offline and repeatable

- A shared fixture blocks every network connection in unit tests. This is how hard rule H06 is tested, and a test that tries the network fails with a clear message.
- Integration tests may reach `127.0.0.1` only.
- A test that needs randomness sets a fixed seed. A test that needs the time receives a fixed clock.
- A test writes only to a temporary folder that pytest creates and deletes.

## Example 1: threshold decision with a stub (H05)

```python
def test_a_package_scoring_17_is_not_sent():
    judge = StubJudge(score=17)          # the stub always returns 17
    outbox = []
    send_if_accepted(package, judge, threshold=18, send=outbox.append)
    assert outbox == []                  # nothing left the node
```

## Example 2: node isolation with a fake embedder (H01)

```python
def test_a_node_never_gets_a_chunk_from_another_node():
    index = build_index(all_chunks, embedder=FakeEmbedder())
    hits = index.search("chlorine residual", node="N6", k=5)
    assert all(hit.node == "N6" for hit in hits)
```

## A change is done when

1. `python tools/run_checks.py` passes.
2. `python -m pytest` passes (the default run).
3. A new rule has a test, and a bug has a test that fails before the fix.

## Book link

The book has no chapter on unit testing, so this page leans on it only for the boundary. Chapter 3 explains why model output and judge scores are inconsistent, which is why they are evaluated and not unit-tested. Chapter 4 says to evaluate each component on its own, which is why the code around a model is tested apart from the model.

## To confirm with the supervisor

- That pytest and the three markers are acceptable as the project standard.
- That quality of model output is measured by metrics and not by unit tests.
- The list of test areas, and that areas for later phases may stay empty until their phase.
