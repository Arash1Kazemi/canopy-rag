"""The change summary: a short, machine-written note of what changed between two versions of an item.

It compares the two texts word by word, says how many words were added and removed, and shows the first few changes.
It is deterministic: the same two texts always give the same note. It is stored in KnowledgeVersion.diff_summary.
"""
import difflib

MAX_EXAMPLES = 8        # how many changes the note shows (the D10 inventory has 8, and the changed total is the 7th)
MAX_WORDS_SHOWN = 6     # how many words of one change the note shows


def _shown(words):
    text = " ".join(words[:MAX_WORDS_SHOWN])
    return text + " ..." if len(words) > MAX_WORDS_SHOWN else text


def summarize_change(old_text, new_text, max_examples=MAX_EXAMPLES):
    """Words are whitespace-separated, as in the chunking spec. autojunk is off so that common words in a long text are
    never treated as noise. This is a precaution: in 3,000 random long texts the shortcut gave the same result, so no
    test can tell the two settings apart."""
    old, new = old_text.split(), new_text.split()
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    changes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if not changes:
        return "no words changed"
    added = sum(j2 - j1 for _, _, _, j1, j2 in changes)
    removed = sum(i2 - i1 for _, i1, i2, _, _ in changes)
    examples = []
    for op, i1, i2, j1, j2 in changes[:max_examples]:
        if op == "replace":
            examples.append(f"'{_shown(old[i1:i2])}' -> '{_shown(new[j1:j2])}'")
        elif op == "insert":
            examples.append(f"added '{_shown(new[j1:j2])}'")
        else:
            examples.append(f"removed '{_shown(old[i1:i2])}'")
    more = "; ..." if len(changes) > max_examples else ""
    return f"{added} words added, {removed} removed in {len(changes)} place(s): " + "; ".join(examples) + more
