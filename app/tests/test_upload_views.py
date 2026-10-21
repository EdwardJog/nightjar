"""Real upload selection and separate participant spaces, using generated data."""
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from app.experiments import merge_recordings, record_frame
from app.inference import predict_frame
from app.journey import make_workspace, start_experiment, active_experiment, DEVICES
from app.storage import (
    save_workspace, load_workspace, list_saved_workspaces, activate_saved_workspace,
    create_separate_workspace,
)
from app.tests.test_interface import JourneyAppTest, button, field, ENTRY


@pytest.fixture
def upload_app(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "upload_store"))
    workspace = make_workspace("Jo", DEVICES[0], "Make more room for sleep")
    start_experiment(workspace, "wind_down", "Read quietly")
    save_workspace(workspace)
    script = tmp_path / "upload_app.py"
    script.write_text(
        "import streamlit as st\n"
        "from app.upload_views import render_add_night\n"
        "from app.inference import load_bundle\n"
        "from app.storage import load_workspace_snapshot, save_workspace\n"
        "if 'workspace' not in st.session_state:\n"
        "    workspace, revision = load_workspace_snapshot()\n"
        "    st.session_state.workspace = workspace\n"
        "    st.session_state.store_revision = revision\n"
        "st.session_state.setdefault('page', 'Add night')\n"
        "def go(page):\n"
        "    st.session_state.page = page\n"
        "    st.rerun()\n"
        "def persist(message=None, page=None):\n"
        "    revision = save_workspace(st.session_state.workspace, st.session_state.store_revision)\n"
        "    st.session_state.workspace['revision'] = revision\n"
        "    st.session_state.store_revision = revision\n"
        "    go(page or st.session_state.page)\n"
        "if st.session_state.page == 'Add night':\n"
        "    render_add_night(st.session_state.workspace, go=go, persist=persist, get_bundle=load_bundle)\n"
        "else:\n"
        "    st.title('Night detail')\n",
        encoding="utf-8",
    )
    return script


def uploaded(frame):
    return patch("streamlit.file_uploader", return_value=BytesIO(frame.to_csv(index=False).encode()))


def two_people(feature_frame):
    other = feature_frame.copy()
    other["Subject_ID"] = "8"
    other["Row_ID"] = "person-8-" + other["Row_ID"].astype(str)
    return pd.concat([feature_frame, other], ignore_index=True)


def save_person_seven(feature_frame, bundle):
    workspace = load_workspace()
    experiment = active_experiment(workspace)
    merge_recordings(experiment, feature_frame, "7", bundle.preprocessor["feature_columns"])
    workspace["subject"] = "7"
    for record in experiment["recordings"]:
        predictions, quality = predict_frame(record_frame(record), bundle)
        record.update(stages=predictions["Predicted stage"].tolist(),
                      quality=quality.iloc[0].to_dict(), model_fingerprint=bundle.fingerprint)
    experiment.update(phase="complete", decision="Keep this routine", change_started_on="2026-01-01")
    save_workspace(workspace)
    return load_workspace()


def test_single_participant_is_visible_and_file_help_is_combined(upload_app, feature_frame, bundle):
    with uploaded(feature_frame) as uploader:
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        chooser = field(app.selectbox, "Which participant is you?")
        assert chooser.value == "7" and chooser.options == ["7"]
        guides = app.get("popover")
        assert len(guides) == 1
        assert guides[0].proto.popover.label == "File requirements"
        help_text = guides[0].proto.popover.help
        assert all(text in help_text for text in ("Subject_ID", "Recording_ID", "Epoch_ID", "59", "30 seconds"))
        assert uploader.call_args.kwargs.get("help") is None
        assert len(guides[0].get("download_button")) == 1
        assert len(app.get("download_button")) == 1
        button(app, "Analyse & add nights").click().run()
    saved = active_experiment(load_workspace())
    assert [len(record["stages"]) for record in saved["recordings"]] == [12, 9]
    assert all(record["subject"] == "7" and record["model_fingerprint"] == bundle.fingerprint
               for record in saved["recordings"])
    assert not app.exception


def test_unassigned_space_can_choose_another_person_before_analysis(upload_app, feature_frame):
    with uploaded(two_people(feature_frame)):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        field(app.selectbox, "Which participant is you?").set_value("8").run()
        button(app, "Analyse & add nights").click().run()
    saved = load_workspace()
    assert saved["subject"] == "8"
    assert all(record["subject"] == "8" for record in active_experiment(saved)["recordings"])
    assert list_saved_workspaces() == []
    assert not app.exception


def test_other_participant_requires_explicit_separate_space_then_can_return(
        upload_app, feature_frame, bundle):
    original = save_person_seven(feature_frame, bundle)
    with uploaded(two_people(feature_frame)):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        assert field(app.selectbox, "Which participant is you?").value == "7"
        field(app.selectbox, "Which participant is you?").set_value("8").run()
        assert not any(item.label == "Analyse & add nights" for item in app.button)
        assert load_workspace() == original
        button(app, "Use a separate space").click().run()
        new = load_workspace()
        assert new["subject"] == "8" and new["profile"] == original["profile"]
        fresh_routine = active_experiment(new)
        assert fresh_routine["change"] == active_experiment(original)["change"]
        assert fresh_routine["outcome"] == active_experiment(original)["outcome"]
        assert fresh_routine["phase"] == "usual" and fresh_routine["recordings"] == []
        assert fresh_routine["decision"] is None and "change_started_on" not in fresh_routine
        assert field(app.selectbox, "Which participant is you?").value == "8"
        button(app, "Analyse & add nights").click().run()
    person_eight = load_workspace()
    assert all(record["subject"] == "8" for record in active_experiment(person_eight)["recordings"])
    previous = list_saved_workspaces()[0]
    restored = activate_saved_workspace(previous["space_id"], person_eight["revision"])
    assert restored["experiments"] == original["experiments"]

    # Choosing an already-saved participant opens their space, not a duplicate.
    with uploaded(two_people(feature_frame)):
        returned = JourneyAppTest(upload_app, default_timeout=60).run()
        field(returned.selectbox, "Which participant is you?").set_value("8").run()
        button(returned, "Open this participant's saved space").click().run()
    assert load_workspace()["experiments"] == person_eight["experiments"]
    assert len(list_saved_workspaces()) == 1
    assert not app.exception and not returned.exception


def test_analysis_failure_does_not_save_partial_nights(upload_app, feature_frame, bundle):
    original = load_workspace()
    first_result = predict_frame(feature_frame.loc[feature_frame.Recording_ID == "1"], bundle)
    with uploaded(feature_frame):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        before_memory = deepcopy(app.session_state["workspace"])
        with patch("app.upload_views.predict_frame", side_effect=[first_result, RuntimeError("Analysis failed")]):
            button(app, "Analyse & add nights").click().run()
    assert any("Analysis failed" in error.value for error in app.error)
    assert load_workspace() == original
    assert app.session_state["workspace"] == before_memory
    assert not app.exception


def test_removing_then_reuploading_same_file_clears_and_rebuilds_selection(upload_app, feature_frame):
    with uploaded(feature_frame):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        assert app.session_state["pending_frame"].shape[0] == len(feature_frame)
    with patch("streamlit.file_uploader", return_value=None):
        app.run()
        assert "pending_frame" not in app.session_state
        assert "upload_digest" not in app.session_state
        assert not app.selectbox and not app.multiselect
    with uploaded(feature_frame):
        app.run()
        assert field(app.selectbox, "Which participant is you?").value == "7"
        button(app, "Analyse & add nights").click().run()
    assert len(active_experiment(load_workspace())["recordings"]) == 2
    assert not app.exception


def test_stale_upload_switch_offers_reload_without_losing_other_tabs_save(
        upload_app, feature_frame, bundle):
    save_person_seven(feature_frame, bundle)
    app = JourneyAppTest(ENTRY, default_timeout=60).run()
    button(app, "Continue to my space").click().run()
    app.button(key="dashboard_add").click().run()
    with uploaded(two_people(feature_frame)):
        app.run()
        field(app.selectbox, "Which participant is you?").set_value("8").run()
        newer = load_workspace()
        newer["profile"]["name"] = "Saved in another tab"
        save_workspace(newer)
        button(app, "Use a separate space").click().run()
        assert any("another tab" in error.value for error in app.error)
        assert load_workspace()["profile"]["name"] == "Saved in another tab"
        assert list_saved_workspaces() == []
        button(app, "Discard unsaved edits and reload").click().run()
    assert app.session_state["page"] == "Welcome"
    assert app.session_state["workspace"]["profile"]["name"] == "Saved in another tab"
    assert "save_error" not in app.session_state
    assert not app.exception


def test_settings_restore_clears_previous_upload_and_keeps_each_persons_profile(
        upload_app, feature_frame, bundle):
    original = save_person_seven(feature_frame, bundle)
    other = make_workspace("Other nickname", DEVICES[0], "Make more room for sleep")
    experiment = start_experiment(other, "wind_down")
    other["subject"] = experiment["subject"] = "8"
    create_separate_workspace(other, expected_revision=original["revision"])
    app = JourneyAppTest(ENTRY, default_timeout=60).run()
    button(app, "Continue to my space").click().run()
    button(app, "Log a night").click().run()
    with uploaded(two_people(feature_frame)):
        app.run()
        assert field(app.selectbox, "Which participant is you?").value == "8"
        assert "pending_frame" in app.session_state
        button(app, "Settings").click().run()
        button(app, "Open selected space").click().run()
    assert app.session_state["page"] == "Today"
    assert app.session_state["workspace"]["subject"] == "7"
    assert app.session_state["workspace"]["profile"]["name"] == "Jo"
    assert active_experiment(load_workspace())["recordings"] == active_experiment(original)["recordings"]
    assert "pending_frame" not in app.session_state and "upload_digest" not in app.session_state
    assert not any(str(key).startswith(("upload_participant_", "upload_recordings_"))
                   for key in app.session_state._state.filtered_state)
    app.button(key="dashboard_add").click().run()
    assert not app.selectbox and not app.multiselect
    button(app, "Settings").click().run()
    button(app, "Open selected space").click().run()
    assert app.session_state["workspace"]["profile"]["name"] == "Other nickname"
    assert active_experiment(load_workspace())["recordings"] == []
    assert not app.exception


def test_stale_settings_switch_can_reload_the_latest_space(upload_app, feature_frame, bundle):
    original = save_person_seven(feature_frame, bundle)
    other = make_workspace("Other nickname", DEVICES[0], "Make more room for sleep")
    experiment = start_experiment(other, "wind_down")
    other["subject"] = experiment["subject"] = "8"
    create_separate_workspace(other, expected_revision=original["revision"])
    app = JourneyAppTest(ENTRY, default_timeout=60).run()
    button(app, "Continue to my space").click().run()
    button(app, "Settings").click().run()
    newer = load_workspace()
    newer["profile"]["name"] = "Latest saved nickname"
    save_workspace(newer)
    button(app, "Open selected space").click().run()
    assert any("another tab" in error.value for error in app.error)
    assert load_workspace()["subject"] == "8"
    assert list_saved_workspaces()[0]["subject"] == "7"
    button(app, "Discard unsaved edits and reload").click().run()
    assert app.session_state["page"] == "Welcome"
    assert app.session_state["workspace"]["profile"]["name"] == "Latest saved nickname"
    assert "save_error" not in app.session_state
    assert not app.exception


def test_repeated_upload_preserves_kept_choice_and_does_not_run_inference(
        upload_app, feature_frame, bundle):
    original = save_person_seven(feature_frame, bundle)
    with uploaded(feature_frame):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        with patch("app.upload_views.predict_frame", side_effect=AssertionError("Unexpected inference")):
            button(app, "Analyse & add nights").click().run()
    saved = load_workspace()
    assert saved["experiments"] == original["experiments"]
    assert active_experiment(saved)["decision"] == "Keep this routine"
    assert len(active_experiment(saved)["recordings"]) == 2
    assert app.session_state["page"] == "Night detail"
    assert not app.error and not app.exception


def test_replacement_needs_confirmation_and_reanalyses_only_changed_night(
        upload_app, feature_frame, bundle):
    original = save_person_seven(feature_frame, bundle)
    changed = feature_frame.copy()
    changed.loc[0, bundle.preprocessor["feature_columns"][0]] = 80
    with uploaded(changed):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
        button(app, "Analyse & add nights").click().run()
        assert any("different data" in error.value for error in app.error)
        assert load_workspace() == original
        field(app.checkbox, "Replace matching recordings if their measurements changed").check().run()
        with patch("app.upload_views.predict_frame", wraps=predict_frame) as predict:
            button(app, "Analyse & add nights").click().run()
        assert predict.call_count == 1
    saved = active_experiment(load_workspace())
    assert len(saved["recordings"]) == 2
    assert saved["recordings"][1] == active_experiment(original)["recordings"][1]
    assert saved["recordings"][0]["model_fingerprint"] == bundle.fingerprint
    assert saved["decision"] is None
    assert saved["decision_history"][-1]["decision"] == "Keep this routine"
    assert not app.exception


def test_malformed_upload_shows_error_and_keeps_saved_space(upload_app, feature_frame):
    original = load_workspace()
    lines = feature_frame.to_csv(index=False).splitlines()
    lines[1] += ",unexpected-field"
    with patch("streamlit.file_uploader", return_value=BytesIO("\n".join(lines).encode())):
        app = JourneyAppTest(upload_app, default_timeout=60).run()
    assert any("fields" in error.value for error in app.error)
    assert not app.selectbox
    assert not app.exception
    assert load_workspace() == original
