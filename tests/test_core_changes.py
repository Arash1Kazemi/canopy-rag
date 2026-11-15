"""Test area: Versioning, the change summary (what changed between two versions)."""
from rag_core.knowledge.changes import summarize_change


def test_a_changed_number_is_shown_as_old_to_new():
    assert summarize_change("The fleet has 120 buses.", "The fleet has 135 buses.") == \
        "1 words added, 1 removed in 1 place(s): '120' -> '135'"


def test_an_added_word_and_a_removed_word_are_named():
    assert summarize_change("a b c", "a x b c") == "1 words added, 0 removed in 1 place(s): added 'x'"
    assert summarize_change("a x b c", "a b c") == "0 words added, 1 removed in 1 place(s): removed 'x'"


def test_no_change_says_so():
    assert summarize_change("same words here", "same words here") == "no words changed"


def test_only_the_first_eight_changes_are_shown():
    old = " ".join(f"p{i} k{i}" for i in range(10))
    new = " ".join(f"p{i} q{i}" for i in range(10))
    note = summarize_change(old, new)
    assert "in 10 place(s)" in note and note.count("->") == 8 and note.endswith("; ...")


def test_a_long_change_is_cut_after_six_words():
    note = summarize_change("start end", "start " + " ".join(f"n{i}" for i in range(10)) + " end")
    assert "added 'n0 n1 n2 n3 n4 n5 ...'" in note


def test_the_same_two_texts_always_give_the_same_note():
    old, new = "one two three four five six", "one 2 three four 5 six seven"
    assert summarize_change(old, new) == summarize_change(old, new)


def test_a_change_after_a_long_run_of_a_common_word_is_still_found():
    old = " ".join(["the"] * 300 + ["bus"])
    new = " ".join(["the"] * 300 + ["train"])
    assert "'bus' -> 'train'" in summarize_change(old, new)
