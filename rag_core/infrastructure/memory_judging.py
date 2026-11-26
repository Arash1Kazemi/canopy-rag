"""The in-memory judge score repository: for unit tests and quick runs. Nothing is written to disk."""


def check_group(scores):
    """The rules both adapters share: a group is one run, with no repeat number twice and at least one score."""
    scores = list(scores)
    if not scores:
        raise ValueError("no scores to store")
    if len({s.run_id for s in scores}) != 1:
        raise ValueError("one run at a time: the scores have different run ids, so nothing was saved")
    repeats = [s.repeat for s in scores]
    if len(set(repeats)) != len(repeats):
        raise ValueError("a repeat number appears twice in one run, so nothing was saved")
    return sorted(scores, key=lambda s: s.repeat)


class InMemoryJudgeRepository:
    def __init__(self):
        self._runs = {}

    def add_run(self, scores):
        group = check_group(scores)
        run_id = group[0].run_id
        if run_id in self._runs:
            raise ValueError(f"run {run_id} is already stored, so nothing was saved")
        self._runs[run_id] = group

    def run(self, run_id):
        return list(self._runs.get(run_id, ()))

    def run_ids(self):
        return list(self._runs)

    def all_scores(self):
        return [s for group in self._runs.values() for s in group]
