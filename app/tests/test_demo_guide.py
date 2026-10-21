"""Practice-only regressions for rereading, recovery and session isolation."""
from copy import deepcopy
from datetime import date
from unittest.mock import patch

import pytest

from app.demo_guide import add_tracking_example
from app.experiments import PERIODS
from app.journey import DEVICES, active_experiment, build_demo_workspace, make_workspace
from app.routine_history import keep_routine
from app.storage import load_workspace, save_workspace
from app.tests.test_interface import (
    button, field, fresh_app, practice_action, reveal_practice_action,
    start_practice_in_app, continue_demo_after_checkin,
)


@pytest.fixture(autouse=True)
def isolated_practice_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "practice"))


def open_practice_checkin():
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    practice_action(app, "Use example recording")
    practice_action(app, "Add selected night")
    reveal_practice_action(app, ".st-key-tour_night_checkin")
    return app


def test_rereading_preserves_the_current_rating_then_saves_it_normally():
    app = open_practice_checkin()
    field(app.select_slider, "How rested did you feel? (optional)").set_value(4).run()
    before = deepcopy(app.session_state["demo_workspace"])
    token = app.session_state["demo_focus"]["token"]
    button(app, "Read this step again").click().run()
    assert app.session_state["demo_step"] == 2
    assert app.session_state["demo_focus"] == {
        "mode": "explain", "token": token, "target": ".st-key-tour_night_checkin",
    }
    assert field(app.select_slider, "How rested did you feel? (optional)").value == 4
    assert app.session_state["demo_workspace"] == before
    reveal_practice_action(app, ".st-key-tour_night_checkin")
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    assert app.session_state["demo_step"] == 3
    night = active_experiment(app.session_state["demo_workspace"])["recordings"][0]
    assert night["rating"] == 4
    assert load_workspace() is None
    assert not app.exception, app.exception[0].stack_trace if app.exception else ""


def test_rereading_a_time_jump_does_not_add_nights_or_advance_practice():
    app = open_practice_checkin()
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    before = deepcopy(app.session_state["demo_workspace"])
    for _ in range(2):
        reveal_practice_action(app, ".st-key-tour_dashboard_insights")
        assert button(app, "Add four more example nights")
        button(app, "Read this step again").click().run()
        assert app.session_state["demo_step"] == 3
        assert app.session_state["demo_focus"]["mode"] == "explain"
        assert not any(item.label == "Add four more example nights" for item in app.button)
        assert app.session_state["demo_workspace"] == before
    practice_action(app, "Add four more example nights")
    assert app.session_state["demo_step"] == 4
    records = active_experiment(app.session_state["demo_workspace"])["recordings"]
    assert len(records) == len({night["recording"] for night in records}) == 5
    assert not app.exception


def test_exit_during_a_reopened_explanation_keeps_the_personal_space():
    real = make_workspace("Actual person", DEVICES[0], "Feel more rested")
    save_workspace(real)
    saved = load_workspace()
    app = open_practice_checkin()
    button(app, "Read this step again").click().run()
    assert app.session_state["demo_focus"]["mode"] == "explain"
    button(app, "Exit demo").click().run()
    assert app.session_state["page"] == "Welcome"
    assert app.session_state["demo_focus"] is None
    assert app.session_state["workspace"] == saved
    assert load_workspace() == saved
    assert not app.exception


def test_missing_comparison_period_has_an_explicit_fictional_reset():
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    app.button(key="tour_skip").click().run()
    # Reproduce the state after removing every changed-period example.
    # Night removal itself is exercised by the existing interface suite.
    experiment = active_experiment(app.session_state["demo_workspace"])
    experiment["recordings"] = [night for night in experiment["recordings"]
                                if night["period"] == PERIODS[0]]
    app.session_state["demo_step"] = 7
    app.session_state["page"] = "Routine progress"
    app.run()
    assert app.session_state["demo_focus"] is None
    assert not any(item.label == "Keep this routine" for item in app.button)
    button(app, "Restore example comparison").click().run()
    restored = active_experiment(app.session_state["demo_workspace"])
    assert app.session_state["demo_step"] == 6
    assert app.session_state["page"] == "Today"
    assert len(restored["recordings"]) == 10
    assert sum(night["period"] == PERIODS[0] for night in restored["recordings"]) == 5
    assert sum(night["period"] == PERIODS[1] for night in restored["recordings"]) == 5
    assert load_workspace() is None
    assert not app.exception


class DemoState(dict):
    """The session-state protocol used by the demo's small data helpers."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


def test_tracking_example_is_repeat_safe_and_preserves_the_saved_result():
    source = build_demo_workspace()
    workspace = deepcopy(source)
    experiment = active_experiment(workspace)
    keep_routine(experiment)
    saved_result = deepcopy(experiment["saved_comparison"])
    source_before = deepcopy(source)
    previous_dates = [night["date"] for night in experiment["recordings"]]
    state = DemoState(demo=True, demo_source=source, demo_workspace=workspace)
    with patch("app.demo_guide.st.session_state", state):
        night = add_tracking_example()
        assert add_tracking_example() is night
    assert len(experiment["recordings"]) == 11
    assert len({night["recording"] for night in experiment["recordings"]}) == 11
    assert max(previous_dates) < night["date"] <= date.today().isoformat()
    assert night["rating"] is None and night["adherence"] is None
    assert night["period"] == PERIODS[1]
    assert night["model_fingerprint"] == "illustrative-demo"
    assert "invented" in night["notes"]
    assert night["data"] == night["columns"] == []
    assert experiment["decision"] is None
    assert experiment["decision_history"][-1]["comparison"] == saved_result
    assert len(experiment["decision_history"]) == 1
    assert source == source_before


def test_tracking_example_rejects_a_future_date_without_changing_the_demo():
    source = build_demo_workspace()
    workspace = deepcopy(source)
    active_experiment(workspace)["recordings"][-1]["date"] = date.today().isoformat()
    before = deepcopy(workspace)
    state = DemoState(demo=True, demo_source=source, demo_workspace=workspace)
    with patch("app.demo_guide.st.session_state", state):
        with pytest.raises(ValueError, match="no later example date"):
            add_tracking_example()
    assert workspace == before


def test_tracking_example_is_unavailable_in_a_personal_session():
    with patch("app.demo_guide.st.session_state", DemoState(demo=False)):
        with pytest.raises(ValueError, match="only in the demo"):
            add_tracking_example()


@pytest.mark.parametrize("stages,note", [
    (["W", "N2", "N3", "REM"], "0.5 min"),
    (["N2", "N3"], "recording starts during estimated sleep"),
    (["W", "W"], "No sleep was estimated"),
])
def test_dashboard_stage_preview_opens_exact_latest_night_and_returns(stages, note):
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    button(app, "Skip intro and see Alex's status").click().run()
    workspace = app.session_state["demo_workspace"]
    latest = max(active_experiment(workspace)["recordings"], key=lambda r: r["date"])
    latest["stages"] = stages
    app.run()
    text = "\n".join(item.value for item in app.markdown)
    assert all(label in text for label in ("Deep sleep", "REM sleep", "First deep sleep", note))
    button(app, "View sleep details").click().run()
    assert app.session_state["selected_recording"] == latest["recording"]
    assert app.session_state["page"] == "Sleep stages"
    button(app, "Back to Today").click().run()
    assert app.session_state["page"] == "Today"
    button(app, "Open latest night").click().run()
    button(app, "Sleep stages").click().run()
    button(app, "Back to night").click().run()
    assert app.session_state["page"] == "Night detail"
    assert load_workspace() is None
    assert not app.exception


def test_alex_story_leads_to_a_deliberate_routine_choice_before_upload():
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    assert any("Meet Alex" in item.value for item in app.markdown)
    assert any("messages right up to bedtime" in item.value for item in app.markdown)
    button(app, "Start practice").click().run()
    assert app.session_state["page"] == "Choose routine"
    assert app.session_state["demo_focus"]["target"] == ".st-key-habit_option_wind_down"
    assert len([item for item in app.button if item.label == "Explore this routine"]) == 4
    assert not any(item.label == "Use example recording" for item in app.button)
    assert not active_experiment(app.session_state["demo_workspace"])["recordings"]
    reveal_practice_action(app)
    app.button(key="habit_wind_down").click().run()
    reveal_practice_action(app, ".st-key-routine_plan")
    field(app.text_input, "Make it specific (optional)").set_value("Read quietly from 9:30 pm")
    button(app, "Save plan and go to Today").click().run()
    assert app.session_state["page"] == "Today"
    assert app.session_state["demo_step"] == "planned"
    workspace = app.session_state["demo_workspace"]
    assert len(workspace["experiments"]) == 1
    assert active_experiment(workspace)["habit_id"] == "wind_down"
    assert active_experiment(workspace)["change"] == "Read quietly from 9:30 pm"
    assert active_experiment(workspace)["id"] == active_experiment(app.session_state["demo_source"])["id"]
    reveal_practice_action(app, ".st-key-dashboard_add")
    app.button(key="dashboard_add").click().run()
    assert app.session_state["page"] == "Add night"
    assert app.session_state["demo_step"] == 1
    assert load_workspace() is None
    assert not app.exception


def test_demo_can_explore_alternatives_without_changing_the_story_or_personal_draft():
    app = fresh_app()
    app.session_state["chosen_habit"] = "coffee"
    button(app, "Explore the demo").click().run()
    button(app, "Start practice").click().run()
    reveal_practice_action(app)
    alternative = next(item for item in app.button if (item.key or "").startswith("habit_") and item.key != "habit_wind_down")
    alternative.click().run()
    reveal_practice_action(app, ".st-key-routine_choose_again")
    before = deepcopy(app.session_state["demo_workspace"])
    button(app, "Save plan and go to Today").click().run()
    assert app.session_state["demo_workspace"] == before
    button(app, "Choose a different routine").click().run()
    assert len([item for item in app.button if item.label == "Explore this routine"]) == 4
    assert app.session_state["chosen_habit"] == "coffee"
    assert load_workspace() is None
    assert not app.exception


def test_edit_hint_supports_real_optional_edits_and_returns_to_practice():
    app = open_practice_checkin()
    button(app, "Save check-in").click().run()
    assert app.session_state["demo_step"] == "edit"
    assert app.session_state["page"] == "Night detail"
    reveal_practice_action(app, ".st-key-tour_edit_night")
    button(app, "Edit night details").click().run()
    reveal_practice_action(app, ".st-key-page_Night_options")
    field(app.text_area, "A note for future you").set_value("A late call interrupted the evening")
    field(app.multiselect, "Anything unusual?").set_value(["Unusual stress"])
    button(app, "Save night details").click().run()
    assert app.session_state["page"] == "Night detail"
    assert app.session_state["demo_step"] == "edit"
    night = active_experiment(app.session_state["demo_workspace"])["recordings"][0]
    assert night["notes"] == "A late call interrupted the evening"
    assert night["context"] == ["Unusual stress"]
    assert any(item.label == "Continue to my dashboard" for item in app.button)
    assert not any(item.label == "Show me" for item in app.button)
    continue_demo_after_checkin(app)
    assert app.session_state["demo_step"] == 3
    assert app.session_state["page"] == "Today"
    assert load_workspace() is None
    assert not app.exception
