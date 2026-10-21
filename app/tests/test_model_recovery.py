"""Missing model files must not lock the user out of their own saved data."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from app.experiments import save_experiment
from app.journey import DEVICES, make_workspace, start_experiment
from app.storage import (
    StorageError, create_separate_workspace, list_saved_workspaces, load_workspace,
    load_workspace_snapshot, save_workspace,
)


@pytest.fixture
def recovery_app(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "model_recovery_store"))
    workspace = make_workspace("Jo", DEVICES[0], "Make more room for sleep")
    experiment = start_experiment(workspace, "wind_down")
    workspace["subject"] = experiment["subject"] = "7"
    experiment["recordings"] = [{
        "subject": "7", "recording": "1", "columns": ["Subject_ID", "Recording_ID", "Epoch_ID", "signal"],
        "data": [["7", "1", 1, 0.25]], "date": "2026-01-01",
        "period": "Usual routine", "rating": 3, "notes": "",
        "stages": ["N2"], "quality": {"Epochs": 1}, "model_fingerprint": "old-model",
    }]
    save_workspace(workspace)
    script = tmp_path / "recovery_app.py"
    script.write_text(
        "import streamlit as st\n"
        "from app.model_recovery import render_model_recovery\n"
        "from app.storage import load_workspace_snapshot\n"
        "if 'workspace' not in st.session_state:\n"
        "    workspace, revision = load_workspace_snapshot()\n"
        "    st.session_state.workspace = workspace\n"
        "    st.session_state.store_revision = revision\n"
        "st.session_state.setdefault('page', 'Recovery')\n"
        "st.session_state['runs'] = st.session_state.get('runs', 0) + 1\n"
        "def go(page):\n"
        "    st.session_state.page = page\n"
        "    st.rerun()\n"
        "with st.empty().container():\n"
        "    if st.session_state.page == 'Recovery':\n"
        "        st.error('Required model file is missing.')\n"
        "        render_model_recovery(st.session_state.workspace, go=go)\n"
        "    else:\n"
        "        st.title('Welcome')\n",
        encoding="utf-8",
    )
    return script


def test_retry_backup_and_welcome_do_not_need_inference_or_change_data(recovery_app):
    original = load_workspace()
    with patch("app.inference.load_bundle", side_effect=AssertionError("No model needed")), \
            patch("app.inference.predict_frame", side_effect=AssertionError("No decoding")), \
            patch("app.model_recovery.save_experiment", wraps=save_experiment) as backup:
        app = AppTest(recovery_app, default_timeout=60).run()
        assert backup.call_args.args[0] == original["experiments"][0]
        content = json.loads(save_experiment(backup.call_args.args[0]))
        assert content["recordings"][0]["stages"] is None
        assert content["recordings"][0]["model_fingerprint"] is None
        assert len(app.get("download_button")) == 1
        assert app.button(key="recovery_delete").disabled
        before_runs = app.session_state["runs"]
        app.button(key="recovery_retry").click().run()
        assert app.session_state["runs"] > before_runs
        app.button(key="recovery_welcome").click().run()
    assert app.session_state["page"] == "Welcome"
    assert load_workspace() == original
    assert not app.exception


def test_confirmed_deletion_removes_active_and_other_spaces_without_model(recovery_app):
    other = make_workspace("Other person", DEVICES[0], "Feel more rested")
    experiment = start_experiment(other, "wind_down")
    other["subject"] = experiment["subject"] = "8"
    create_separate_workspace(other, expected_revision=1)
    assert len(list_saved_workspaces()) == 1
    app = AppTest(recovery_app, default_timeout=60).run()
    app.checkbox(key="recovery_delete_confirm").check().run()
    app.button(key="recovery_delete").click().run()
    assert app.session_state["page"] == "Welcome"
    assert load_workspace_snapshot() == (None, 3)
    assert list_saved_workspaces() == []
    assert not app.exception


def test_stale_tab_cannot_delete_newer_data_and_can_reload(recovery_app):
    app = AppTest(recovery_app, default_timeout=60).run()
    newer = load_workspace()
    newer["profile"]["name"] = "Saved in another tab"
    save_workspace(newer)
    current = deepcopy(load_workspace())
    app.checkbox(key="recovery_delete_confirm").check().run()
    app.button(key="recovery_delete").click().run()
    assert any("another tab" in error.value for error in app.error)
    assert load_workspace() == current
    app.button(key="recovery_reload").click().run()
    assert app.session_state["workspace"] == current
    assert app.session_state["store_revision"] == current["revision"]
    assert app.session_state["page"] == "Welcome"
    assert "model_recovery_error" not in app.session_state
    assert not app.exception


def test_storage_failure_keeps_data_and_allows_retry(recovery_app):
    app = AppTest(recovery_app, default_timeout=60).run()
    original = load_workspace()
    app.checkbox(key="recovery_delete_confirm").check().run()
    with patch("app.model_recovery.clear_workspace", side_effect=StorageError("Disk is unavailable")):
        app.button(key="recovery_delete").click().run()
    assert load_workspace() == original
    assert any("Disk is unavailable" in error.value for error in app.error)
    app.button(key="recovery_delete").click().run()
    assert load_workspace_snapshot() == (None, 2)
    assert app.session_state["page"] == "Welcome"
    assert not app.exception
