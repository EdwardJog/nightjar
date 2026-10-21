"""Participant spaces stay separate through switches, failures and deletion."""
from copy import deepcopy
import sqlite3

import pytest

from app import storage
from app.journey import make_workspace, start_experiment, active_experiment, DEVICES


@pytest.fixture
def saved_person(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "spaces"))
    workspace = make_workspace("Jo", DEVICES[0], "Feel more rested")
    experiment = start_experiment(workspace, "wind_down", "Read quietly")
    workspace["subject"] = experiment["subject"] = "7"
    experiment["recordings"] = [{
        "subject": "7", "recording": "1", "stages": ["W", "N2"],
        "date": "2026-01-01", "rating": 4, "data": [[7, 1, 1], [7, 1, 2]],
        "model_fingerprint": "trusted-model",
    }]
    experiment.update(decision="Keep this routine", phase="complete")
    storage.save_workspace(workspace)
    return storage.load_workspace()


def empty_person(subject="8"):
    workspace = make_workspace("Jo", DEVICES[0], "Feel more rested")
    experiment = start_experiment(workspace, "wind_down", "Read quietly")
    workspace["subject"] = experiment["subject"] = subject
    return workspace


def test_separate_space_and_switch_back_preserve_both_people(saved_person):
    original = deepcopy(saved_person)
    new = storage.create_separate_workspace(empty_person(), expected_revision=1)
    assert new["revision"] == 2 and new["subject"] == "8"
    assert active_experiment(new)["recordings"] == []
    archived = storage.list_saved_workspaces()
    assert len(archived) == 1
    assert archived[0]["subject"] == "7" and archived[0]["recordings"] == 1
    assert "payload" not in archived[0] and "data" not in archived[0]
    active_experiment(new)["recordings"] = [{
        "subject": "8", "recording": "1", "stages": ["N3"], "data": [[8, 1, 1]],
    }]
    assert storage.save_workspace(new) == 3

    restored = storage.activate_saved_workspace(archived[0]["space_id"], expected_revision=3)
    assert restored["revision"] == 4 and restored["subject"] == "7"
    assert restored["experiments"] == original["experiments"]
    assert restored["profile"] == original["profile"]
    other = storage.list_saved_workspaces()
    assert len(other) == 1 and other[0]["subject"] == "8"
    restored_other = storage.activate_saved_workspace(other[0]["space_id"], expected_revision=4)
    assert active_experiment(restored_other)["recordings"][0]["stages"] == ["N3"]
    assert restored_other["space_id"] == new["space_id"]


def test_global_revision_blocks_stale_tabs_and_duplicate_participant_spaces(saved_person):
    active = storage.create_separate_workspace(empty_person(), expected_revision=1)
    original_id = storage.list_saved_workspaces()[0]["space_id"]
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(saved_person)
    with pytest.raises(storage.StorageConflict):
        storage.create_separate_workspace(empty_person("9"), expected_revision=1)
    with pytest.raises(storage.StorageConflict):
        storage.activate_saved_workspace(original_id, expected_revision=1)
    with pytest.raises(storage.StorageError, match="already has"):
        storage.create_separate_workspace(empty_person("7"), expected_revision=2)
    assert storage.load_workspace() == active
    assert len(storage.list_saved_workspaces()) == 1


def test_failed_switch_rolls_back_archive_and_active_payload(saved_person):
    path = storage.get_store_path()
    with sqlite3.connect(path) as connection:
        connection.execute("""
            CREATE TRIGGER reject_switch BEFORE UPDATE ON workspace
            BEGIN SELECT RAISE(ABORT, 'test failure'); END
        """)
    with pytest.raises(storage.StorageError, match="previous space is intact"):
        storage.create_separate_workspace(empty_person(), expected_revision=1)
    assert storage.load_workspace() == saved_person
    assert storage.list_saved_workspaces() == []


def test_corrupt_archived_payload_does_not_replace_active_space(saved_person):
    active = storage.create_separate_workspace(empty_person(), expected_revision=1)
    archived_id = storage.list_saved_workspaces()[0]["space_id"]
    with sqlite3.connect(storage.get_store_path()) as connection:
        connection.execute("UPDATE saved_workspaces SET payload = ? WHERE space_id = ?",
                           ("{broken", archived_id))
    with pytest.raises(storage.StorageError, match="JSON"):
        storage.activate_saved_workspace(archived_id, expected_revision=2)
    assert storage.load_workspace() == active
    assert len(storage.list_saved_workspaces()) == 1


def test_clear_removes_all_spaces_and_prevents_old_tabs_restoring_them(saved_person):
    other = storage.create_separate_workspace(empty_person(), expected_revision=1)
    with pytest.raises(storage.StorageConflict):
        storage.clear_workspace(expected_revision=1)
    assert storage.clear_workspace(expected_revision=2) == 3
    assert storage.load_workspace_snapshot() == (None, 3)
    assert storage.list_saved_workspaces() == []
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(other)
    with sqlite3.connect(storage.get_store_path()) as connection:
        assert connection.execute("SELECT COUNT(*) FROM saved_workspaces").fetchone()[0] == 0
        assert connection.execute("SELECT payload FROM workspace").fetchone()[0] is None


def test_new_space_cannot_carry_another_participants_recordings(saved_person):
    invalid = empty_person()
    active_experiment(invalid)["recordings"] = deepcopy(active_experiment(saved_person)["recordings"])
    with pytest.raises(storage.StorageError, match="without recordings"):
        storage.create_separate_workspace(invalid, expected_revision=1)
    assert storage.load_workspace() == saved_person
    assert storage.list_saved_workspaces() == []
