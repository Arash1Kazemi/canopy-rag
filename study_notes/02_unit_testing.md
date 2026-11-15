# Note 2: the unit-testing method

Where we are: step 6. Book: no chapter on unit testing. Chapters 3 and 4 explain the boundary: why model output is evaluated, not unit-tested.
File made in this step: `docs/unit_testing_rules.md`. Live examples: the tests in `tests/`.

## In one minute

A unit test checks that our own code follows our own rules, and it gives the same result on every run, on any laptop, with the network off. A model's answer is not our rule, so it is measured by a metric instead. Test doubles, which are simple stand-ins for the real model, let us test everything around a model without running one.

## 1. Three kinds of checking

Analogy: a car. A unit test is the workshop checking that the brakes and lights work, the same way every time. An evaluation is the driving test: how well this car drives on this road, and it can vary. A data check is the paperwork: the papers must match the car.

| Kind | Checks | Tool |
|---|---|---|
| Data check | The files agree with each other | `python tools/run_checks.py` |
| Unit test | Our code follows our rules | `python -m pytest` |
| Evaluation | How good the models are | the baseline runner |

## 2. What a unit test looks like

Three parts: set up, act, assert (check). One test, one behavior.

```python
def test_a_package_scoring_17_is_not_sent():
    judge = StubJudge(score=17)          # set up: a stand-in that always says 17
    outbox = []
    send_if_accepted(package, judge, threshold=18, send=outbox.append)   # act
    assert outbox == []                  # assert: nothing was sent
```

pytest finds files named `test_*.py` and functions named `test_*`. `assert` is plain Python. If the condition is false, the test fails and pytest shows both sides.

Useful pytest ideas, in words:

- **Fixture**: setup that pytest hands to a test. `tmp_path` gives a fresh temporary folder that is deleted afterwards.
- **Marker**: a label on a test. We use `integration` (needs a local server) and `evaluation` (runs real models). The default run skips both, so the default run is fast and needs nothing.
- **Autouse fixture**: one that every test gets. Ours (`tests/conftest.py`) blocks the network, which is how hard rule H06 (works offline) is tested.

## 3. Test doubles

A test double replaces a real part in a test. Analogy: a crash-test dummy. You test the car's airbags with a dummy, not with a person.

| Kind | What it does | In this project |
|---|---|---|
| Dummy | Fills a slot, never used | A node id the function ignores |
| Stub | Returns a fixed answer | `StubJudge(score=17)` |
| Fake | A real but simple version | `FakeEmbedder`: counts words into hashed slots, no model |
| Spy | Records how it was called | The `Spy` transport in `test_ollama_api.py` that stores what was sent |
| Mock | A spy with pre-set expectations | We avoid it: it checks how the code works, so a harmless rewrite breaks the test |

The key design rule: **the domain code never imports a model or an HTTP library.** It receives the model as an argument. Then a test can pass a double, and the real run can pass the real thing. This is why `OllamaClient` takes a `transport` argument, and why `FakeClient` has the same methods as `OllamaClient`.

## 4. A realistic example from this project

Hard rule H01: a node answers only from its own documents. We test it with the real case study files and a fake embedder:

```python
def test_a_node_never_gets_a_chunk_from_another_node():
    index = build(make_chunks(load_files(), "words80"))
    for node in ("N0", "N1", "N2", "N3", "N4", "N5", "N6"):
        hits = search(index, FakeEmbedder().vector("chlorine residual in drinking water"), node, k=100)
        assert all(chunk.node_id == node for chunk, _ in hits)
```

Notice what it does not test: whether the real embedding model finds the chlorine document (that is metric M06). It tests our filter, which must hold whatever the model does.

A second example found a real bug. The test that runs the whole pipeline with fakes crashed on question Q12, because the file name `D19_meeting_minutes_2025-06-18` has a hyphen and our pattern for reading file names stopped at it. A real run would have crashed on the same question after an hour of downloads. That is the value of a test written before the real thing.

## 5. What is not unit-tested, and why

An LLM answer, an embedding result, an OCR result, a judge score, a speed. They vary with the model, the settings, the hardware. A test that asserts "the answer contains 135" would pass on one run and fail on the next, and then everybody learns to ignore failing tests. So these are measured (metrics M01 to M25) and compared across runs. We do test the code around them: that the prompt is built correctly, that the reply is parsed, that a number is graded the same way every time.

## 6. Common mistakes

1. Asserting on a model's words in a unit test.
2. Using a mock and testing the internals instead of the behavior.
3. Tests that depend on the order they run in, or on files left by an earlier test.
4. A test that quietly uses the network or the real clock.
5. Writing the test after a bug, and not checking that it fails before the fix. A test that never failed proves nothing.
6. Chasing a coverage percentage. We track test areas instead (metric M26): is there at least one test for each rule that matters?

## 7. Check yourself

1. Is "the LLM says Insufficient knowledge for Q23" a unit test or an evaluation? Why?
2. What is the difference between a stub and a fake? Give one from this project.
3. Why does the conftest block the network for unit tests?
4. You change the grading rule for Q17. Which checks should you run?

Answers:

1. An evaluation. It depends on the model. The unit test is "if the model says Insufficient knowledge, the grader marks a refusal question correct".
2. A stub returns a fixed answer (`StubJudge`). A fake does the real job in a simple way (`FakeEmbedder` really embeds, with no model).
3. To prove hard rule H06: a test that tries to reach out fails loudly, so the system cannot depend on the internet without us knowing.
4. `python tools/run_checks.py` (key facts must match the expected answer) and `python -m pytest` (the test that each expected answer passes its own rule).
