"""core/confirm.py — the confirmation gate.

The module's claim is that the *model* cannot forge confirmation. These tests
hold that claim to account: in every case the irreversible callable must only
run when a human pressed CONFIRM, and never when the interface is absent.
"""
import threading

import pytest

from core import confirm


@pytest.fixture(autouse=True)
def clean_state():
    """Every test starts with no pending confirmation and no bound UI."""
    confirm._pending = None
    confirm._show_cb = None
    confirm._hide_cb = None
    confirm._log_cb = None
    yield
    confirm._pending = None
    confirm._show_cb = None
    confirm._hide_cb = None
    confirm._log_cb = None


def bind_recorder():
    """Bind stub UI callbacks and return the events they record."""
    events = []
    confirm.bind(lambda t, d: events.append(("show", t)),
                 lambda: events.append(("hide", "")),
                 lambda m: events.append(("log", m)))
    return events


def confirmed_action(record, label):
    """A zero-argument action that records itself and signals when it has run.

    resolve() dispatches onto a worker thread, so waiting on this event is what
    makes the tests deterministic — a fixed sleep would pass on a fast machine
    and flake on a loaded one, and a test that cannot prove the action ran
    would happily pass whether or not it did.
    """
    done = threading.Event()

    def run():
        record.append(label)
        done.set()
        return "ok"

    run.done = done
    return run


def await_action(run, timeout=5.0):
    """Block until the dispatched action has actually executed."""
    assert run.done.wait(timeout), "the confirmed action never ran"


def test_request_without_ui_refuses_and_does_not_run():
    """Headless: the action must be refused, never silently performed."""
    ran = []
    msg = confirm.request("shutdown", "Shut down", "really", lambda: ran.append(1))

    assert ran == [], "irreversible action ran with no interface bound"
    assert "cannot confirm" in msg.lower()


def test_request_only_parks_the_action_and_asks_the_model_to_prompt():
    """request() must not execute the work — that is the whole design."""
    bind_recorder()
    ran = []

    msg = confirm.request("delete", "Delete file", "permanent",
                          lambda: ran.append(1))

    assert ran == []
    assert "CONFIRMATION_PENDING" in msg
    assert confirm.pending_title() == "Delete file"


def test_confirm_runs_the_action_and_cancel_does_not():
    bind_recorder()
    ran = []
    action = confirmed_action(ran, 1)
    confirm.request("x", "Delete file", "detail", action)

    confirm.resolve(True)
    await_action(action)

    assert ran == [1]


def test_cancel_leaves_the_action_untouched():
    bind_recorder()
    ran = []
    action = confirmed_action(ran, 1)
    confirm.request("x", "Delete file", "detail", action)

    confirm.resolve(False)
    assert not action.done.wait(0.3), "a cancelled action must not run"
    assert ran == []


def test_a_second_confirmation_overwrites_the_first():
    """Two banners must not stack: the module holds a single pending slot."""
    bind_recorder()
    first, second = [], []
    confirm.request("a", "First", "", lambda: first.append(1))
    action = confirmed_action(second, 1)
    confirm.request("b", "Second", "", action)

    confirm.resolve(True)
    await_action(action)

    assert first == []
    assert second == [1]


def test_expired_confirmation_never_runs_the_action():
    """The 90s timeout must actually gate execution, not just the label."""
    bind_recorder()
    ran = []
    action = confirmed_action(ran, 1)
    confirm.request("x", "Shut down", "detail", action)

    # Backdate the pending entry past the timeout.
    confirm._pending.at -= confirm.TIMEOUT_SECONDS + 1

    confirm.resolve(True)
    assert not action.done.wait(0.3), "an expired confirmation still ran the action"

    assert ran == [], "an expired confirmation still performed the action"


def test_pending_title_is_blank_once_expired():
    """A dead banner must not keep reporting itself as awaiting a decision."""
    bind_recorder()
    confirm.request("x", "Shut down", "detail", lambda: None)
    confirm._pending.at -= confirm.TIMEOUT_SECONDS + 1

    assert confirm.pending_title() == ""


def test_action_is_run_off_the_calling_thread():
    """Shutting down from inside a Qt button handler would freeze the UI."""
    bind_recorder()
    where = []
    done = threading.Event()

    def record_thread():
        where.append(threading.current_thread())
        done.set()

    confirm.request("x", "Shut down", "", record_thread)

    confirm.resolve(True)
    assert done.wait(5.0), "the action never ran"

    assert where[0] is not threading.current_thread()


def test_failing_action_is_caught_and_reported_not_raised():
    """A crash in the confirmed work must not take down the resolve() caller."""
    events = bind_recorder()
    done = threading.Event()

    def boom():
        done.set()
        raise RuntimeError("no such device")

    confirm.request("x", "Do thing", "", boom)
    confirm.resolve(True)
    assert done.wait(5.0), "the action never ran"

    logs = [msg for kind, msg in events if kind == "log"]
    assert any("failed" in m.lower() for m in logs), events


def test_resolve_without_anything_pending_is_a_no_op():
    bind_recorder()
    confirm.resolve(True)               # must not raise
    confirm.resolve(False)


def test_ui_failure_refuses_the_action_and_releases_the_slot():
    """If the banner cannot be shown, the user can never confirm — so refuse."""
    ran = []

    def broken_show(title, detail):
        raise RuntimeError("HUD is gone")

    confirm.bind(broken_show, lambda: None)
    msg = confirm.request("x", "Delete file", "detail", lambda: ran.append(1))

    assert ran == []
    assert "could not ask for confirmation" in msg.lower()
    assert confirm.pending_title() == ""