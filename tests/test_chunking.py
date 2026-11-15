import pytest

from baseline_runner.chunking import make_chunks, words_windows
from baseline_runner.corpus import load_files


def numbered_text(n):
    return " ".join(f"w{i}" for i in range(n))


def test_a_short_text_is_one_chunk():
    assert words_windows(numbered_text(30), 80, 15) == [numbered_text(30)]


def test_an_empty_text_has_no_chunks():
    assert words_windows("   ", 80, 15) == []


def test_no_word_is_lost_and_the_last_window_reaches_the_end():
    text = numbered_text(250)
    windows = words_windows(text, 80, 15)
    covered = {w for window in windows for w in window.split()}
    assert covered == set(text.split())
    assert windows[0].startswith("w0 ")
    assert windows[-1].endswith("w249")


def test_neighbouring_windows_share_exactly_the_overlap():
    windows = words_windows(numbered_text(250), 80, 15)
    for before, after in zip(windows, windows[1:]):
        assert before.split()[-15:] == after.split()[:15]


def test_a_window_is_never_longer_than_the_size():
    assert all(len(w.split()) <= 80 for w in words_windows(numbered_text(1000), 80, 15))


def test_bad_settings_are_refused():
    for size, overlap in ((0, 0), (10, 10), (10, -1), (-5, 0)):
        with pytest.raises(ValueError):
            words_windows("a b c", size, overlap)


def test_the_file_setting_makes_one_chunk_per_file():
    files = load_files()
    chunks = make_chunks(files, "file")
    assert len(chunks) == len(files) == 22
    assert {c.stem for c in chunks} == {f.stem for f in files}


def test_chunks_keep_their_node_and_have_unique_ids():
    files = load_files()
    chunks = make_chunks(files, "words80")
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    node_of_stem = {f.stem: f.node_id for f in files}
    assert all(c.node_id == node_of_stem[c.stem] for c in chunks)
    assert {c.stem for c in chunks} == set(node_of_stem)
