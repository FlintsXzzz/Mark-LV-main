"""core/undo.py — the shared undo stack.

The contract an action relies on: push a label plus a reverse callable, and
`undo_last()` reverses the most recent one. These cover ordering, the depth
cap, and the failure paths that decide whether a mistake can be recovered.
"""
import threading

import pytest

from core.undo import (
    MAX_DEPTH,
    can_undo,
    clear,
    history,
    peek,
    push_undo,
    undo_last,
)


@pytest.fixture(autouse=True)
def clean_stack():
    clear()
    yield
    clear()


def test_empty_stack_reports_nothing_and_does_not_raise():
    assert can_undo() is False
    assert peek() == ""
    assert history() == []
    assert "nothing to undo" in undo_last().lower()


def test_undo_reverses_the_most_recent_action_first():
    order = []
    push_undo("first", lambda: order.append("first") or "ok")
    push_undo("second", lambda: order.append("second") or "ok")

    undo_last()
    undo_last()

    assert order == ["second", "first"]


def test_history_is_newest_first():
    push_undo("alpha", lambda: "")
    push_undo("beta", lambda: "")

    assert history() == ["beta", "alpha"]


def test_peek_matches_what_undo_last_will_reverse():
    push_undo("only", lambda: "")

    assert peek() == "only"
    assert can_undo() is True


def test_detail_from_the_undo_callable_is_spoken_back():
    push_undo("volume → 40%", lambda: "restored to 80%")

    out = undo_last()

    assert "volume → 40%" in out
    assert "restored to 80%" in out


def test_depth_cap_drops_the_oldest_not_the_newest():
    for i in range(MAX_DEPTH + 5):
        push_undo(f"op{i}", lambda: "")

    hist = history()

    assert len(hist) == MAX_DEPTH
    assert hist[0] == f"op{MAX_DEPTH + 4}", "the newest entry was dropped"
    assert "op0" not in hist, "the oldest entry should have been evicted first"


def test_failing_undo_is_reported_and_the_entry_is_consumed():
    """A retry loop against a world that moved on would be worse than a message."""
    def boom():
        raise RuntimeError("file already gone")

    push_undo("restore file", boom)

    out = undo_last()

    assert "could not undo" in out.lower()
    assert "file already gone" in out
    assert can_undo() is False, "a failed undo must not be offered again"


def test_non_callable_undo_is_ignored_rather_than_stored():
    push_undo("bad", "not a function")          # type: ignore[arg-type]

    assert can_undo() is False


def test_empty_detail_does_not_leave_a_stray_space():
    push_undo("did a thing", lambda: "")

    assert not undo_last().endswith(" ") 


def test_long_labels_are_truncated():
    push_undo("x" * 500, lambda: "")

    assert len(peek()) <= 120


def test_concurrent_pushes_do_not_lose_entries():
    def worker(n):
        for i in range(25):
            push_undo(f"t{n}-{i}", lambda: "")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(history()) == MAX_DEPTH


def test_clear_empties_the_stack():
    push_undo("something", lambda: "")

    clear()

    assert can_undo() is False
    assert history() == []
