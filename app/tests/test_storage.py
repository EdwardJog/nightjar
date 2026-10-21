"""Persistence tests use their own temporary database, never personal saves."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Barrier

import numpy as np
import pytest

from app import storage


@pytest.fixture
def local_store(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path))
    return storage.get_store_path()


@pytest.fixture
def workspace():
    return {
        "schema_version": 2,
        "profile": {"name": "Jo", "device": "Compatible CSV", "goal": "Feel more rested"},
        "active_experiment": "one",
        "experiments": [{
            "schema_version": 1, "id": "one", "habit_id": "wind_down",
            "title": "A quieter evening", "change": "Read before bed",
            "outcome": "Morning restfulness (1-5)", "outcome_history": [],
            "reviewed": False, "phase": "usual", "subject": "person-7",
            "recordings": [{
                "subject": "person-7", "recording": "night-1",
                "columns": ["Subject_ID", "Recording_ID", "Epoch_ID", "feature"],
                "data": [["person-7", "night-1", 1, 0.12345678901234567]],
                "date": "2026-10-19", "period": "Usual routine", "rating": 3,
                "notes": "Read a book", "stages": ["N2"],
                "quality": {"Epochs": np.int64(1)}, "model_fingerprint": "model-example",
            }],
        }],
        "revision": 0,
    }


def test_round_trip_and_numpy_scalars_keep_internal_predictions(local_store, workspace):
    assert storage.load_workspace_snapshot() == (None, 0)
    original = deepcopy(workspace)
    revision = storage.save_workspace(workspace)
    assert revision == 1
    assert workspace == original
    loaded = storage.load_workspace()
    assert loaded["revision"] == 1
    assert loaded["updated_at"]
    record = loaded["experiments"][0]["recordings"][0]
    assert record["data"] == workspace["experiments"][0]["recordings"][0]["data"]
    assert record["stages"] == ["N2"]
    assert record["model_fingerprint"] == "model-example"
    assert type(record["quality"]["Epochs"]) is int
    loaded["profile"]["name"] = "Joanna"
    assert storage.save_workspace(loaded) == 2
    assert storage.load_workspace()["profile"]["name"] == "Joanna"


def test_stale_tab_and_simultaneous_first_save_do_not_overwrite(local_store, workspace):
    storage.save_workspace(workspace)
    tab_a = storage.load_workspace()
    tab_b = storage.load_workspace()
    tab_a["profile"]["name"] = "Latest change"
    storage.save_workspace(tab_a)
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(tab_b)
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(workspace, expected_revision=0)
    assert storage.load_workspace()["profile"]["name"] == "Latest change"


def test_concurrent_first_save_has_exactly_one_winner(local_store, workspace):
    barrier = Barrier(2)

    def save_from_tab():
        barrier.wait(timeout=5)
        try:
            return storage.save_workspace(workspace)
        except storage.StorageConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(save_from_tab)
        second = executor.submit(save_from_tab)
        results = [first.result(timeout=10), second.result(timeout=10)]
    assert sorted(results, key=str) == [1, "conflict"]
    assert storage.load_workspace()["revision"] == 1


def test_invalid_values_and_sql_failure_leave_previous_save_intact(local_store, workspace):
    storage.save_workspace(workspace)
    valid = storage.load_workspace()
    invalid = deepcopy(valid)
    invalid["experiments"][0]["recordings"][0]["data"][0][-1] = float("nan")
    with pytest.raises(storage.StorageError, match="could not be saved"):
        storage.save_workspace(invalid)
    assert storage.load_workspace() == valid

    # Fail inside the database transaction, after acquiring its write lock.
    with sqlite3.connect(local_store) as connection:
        connection.execute("""
            CREATE TRIGGER reject_save BEFORE UPDATE ON workspace
            BEGIN SELECT RAISE(ABORT, 'test failure'); END
        """)
    valid["profile"]["name"] = "Must not be saved"
    with pytest.raises(storage.StorageError, match="previous save is intact"):
        storage.save_workspace(valid)
    assert storage.load_workspace()["profile"]["name"] == "Jo"
    assert storage.load_workspace()["revision"] == 1


@pytest.mark.parametrize("payload", [
    "{broken json",
    '{"schema_version":2,"profile":{},"experiments":[],"revision":NaN}',
    json.dumps({"schema_version": 999, "profile": {}, "experiments": []}),
])
def test_corrupt_save_is_reported_not_silently_replaced(local_store, workspace, payload):
    storage.save_workspace(workspace)
    with sqlite3.connect(local_store) as connection:
        connection.execute("UPDATE workspace SET payload = ? WHERE id = 1", (payload,))
    with pytest.raises(storage.StorageError):
        storage.load_workspace()
    with pytest.raises(storage.StorageError):
        storage.save_workspace(workspace, expected_revision=1)
    with sqlite3.connect(local_store) as connection:
        assert connection.execute("SELECT payload FROM workspace").fetchone()[0] == payload


def test_clear_keeps_revision_and_stops_old_tabs_restoring_deleted_data(local_store, workspace):
    storage.save_workspace(workspace)
    old_tab = storage.load_workspace()
    with pytest.raises(storage.StorageConflict):
        storage.clear_workspace(expected_revision=0)
    assert storage.clear_workspace(expected_revision=1) == 2
    assert local_store.exists()
    assert storage.load_workspace_snapshot() == (None, 2)
    assert storage.load_workspace() is None
    with sqlite3.connect(local_store) as connection:
        assert connection.execute("SELECT payload FROM workspace").fetchone()[0] is None
    with pytest.raises(storage.StorageConflict):
        storage.save_workspace(old_tab)
    assert storage.save_workspace(workspace, expected_revision=2) == 3


def test_invalid_container_and_size_limit_do_not_create_save(local_store, workspace, monkeypatch):
    invalid = deepcopy(workspace)
    invalid["active_experiment"] = "missing"
    with pytest.raises(storage.StorageError, match="active experiment"):
        storage.save_workspace(invalid)
    monkeypatch.setattr(storage, "MAX_WORKSPACE_BYTES", 50)
    with pytest.raises(storage.StorageError, match="too large"):
        storage.save_workspace(workspace)
    assert storage.load_workspace_snapshot() == (None, 0)
