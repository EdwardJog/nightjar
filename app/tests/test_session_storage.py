"""Hosted saves must never reach another visitor or the local SQLite file."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from app import session_storage, storage
from app.journey import make_workspace, DEVICES


@pytest.fixture
def sessions(monkeypatch):
    monkeypatch.setenv("NIGHTJAR_STORAGE_MODE", "session")
    fake = SimpleNamespace(session_state={})
    monkeypatch.setattr(session_storage, "st", fake)
    monkeypatch.setattr(storage, "_connect", lambda: pytest.fail("Hosted save accessed SQLite"))
    return fake


def space(name="Alice", subject="a"):
    result = make_workspace(name, DEVICES[0], "Feel more rested")
    result["subject"] = subject
    return result


def test_two_visitors_save_switch_delete_and_reconnect(sessions):
    alice_session = sessions.session_state
    assert storage.save_workspace(space()) == 1
    bob_session = {}
    sessions.session_state = bob_session
    assert storage.load_workspace_snapshot() == (None, 0)
    storage.save_workspace(space("Bob", "b"))
    sessions.session_state = alice_session
    assert storage.load_workspace()["profile"]["name"] == "Alice"
    second = storage.create_separate_workspace(space("Carol", "c"), 1)
    assert second["revision"] == 2
    archived = storage.list_saved_workspaces()
    assert [x["name"] for x in archived] == ["Alice"]
    restored = storage.activate_saved_workspace(archived[0]["space_id"], 2)
    assert restored["profile"]["name"] == "Alice"
    assert storage.clear_workspace(3) == 4
    assert storage.list_saved_workspaces() == []
    sessions.session_state = bob_session
    assert storage.load_workspace()["profile"]["name"] == "Bob"
    sessions.session_state = {}
    assert storage.load_workspace_snapshot() == (None, 0)


def test_snapshots_conflicts_and_failed_save_are_atomic(sessions):
    original = space()
    snapshot = deepcopy(original)
    storage.save_workspace(original)
    assert original == snapshot
    loaded = storage.load_workspace()
    loaded["profile"]["name"] = "Unsaved"
    assert storage.load_workspace()["profile"]["name"] == "Alice"
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(original)
    loaded["profile"]["name"] = float("nan")
    with pytest.raises(storage.StorageError):
        storage.save_workspace(loaded)
    with pytest.raises(storage.StorageError):
        storage.create_separate_workspace(space(), 1)
    assert storage.load_workspace()["profile"]["name"] == "Alice"


def test_reset_retains_store_but_discards_widgets(sessions, monkeypatch):
    import streamlit
    from app.runtime import reset_interface
    monkeypatch.setattr(streamlit, "session_state", sessions.session_state)
    storage.save_workspace(space())
    sessions.session_state["upload"] = "stale"
    reset_interface()
    assert "upload" not in sessions.session_state
    assert storage.load_workspace()["profile"]["name"] == "Alice"
