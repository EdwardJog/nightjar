"""Consumer journeys with isolated local saves and real saved-model inference."""
from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Block, Widget

from app.experiments import new_experiment, merge_recordings, update_plan, SLEEP, RATING
from app.experiments import save_experiment, set_diary, record_frame, PERIODS
from app.inference import predict_frame
from app.journey import active_experiment, make_workspace, start_experiment, DEVICES, count_complete_nights
from app.journey import build_demo_workspace, GOALS
from app.demo_guide import complete_example_period
from app.routine_history import keep_routine
from app.storage import load_workspace, load_workspace_snapshot, save_workspace, StorageError


ENTRY = str(Path(__file__).resolve().parents[1] / "main.py")


class JourneyAppTest(AppTest):
    """Remove Streamlit 1.51's stale test nodes after an in-script rerun.

    AppTest merges the interrupted screen's deltas into the final screen.
    When the destination has fewer controls, old widgets remain in its tree
    even though Streamlit has removed their backend state. Browsers clear them.
    Prune only those state-removed widgets, immediately after parsing the run,
    before a test can make its next edit. Active widgets and app exceptions
    remain untouched. No installed Streamlit code is changed.
    """

    def _run(self, widget_state=None, timeout=None):
        result = super()._run(widget_state=widget_state, timeout=timeout)

        def remove_stale_widgets(block):
            for index, node in list(block.children.items()):
                if isinstance(node, Block):
                    remove_stale_widgets(node)
                elif isinstance(node, Widget) and node.id not in self.session_state:
                    # Reject removal if an explicit edit somehow precedes pruning.
                    initial_value = type(node)(node.proto, node.root)._value
                    assert node._value == initial_value, "Refusing to discard a pending widget edit"
                    del block.children[index]

        remove_stale_widgets(self._tree)
        return result


@pytest.fixture(autouse=True)
def isolated_local_space(tmp_path, monkeypatch):
    # Every AppTest, including a second browser session, uses this test's store.
    # Never read or write the user's real app/.local directory.
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "nightjar"))


def button(app, label):
    return next(item for item in app.button if item.label == label)


def field(elements, label):
    return next(item for item in elements if item.label == label)


def reveal_practice_action(app, expected_target=None):
    """Follow the explanation before using its ordinary app control.

    AppTest can verify the reveal state and target; browser checks separately
    verify JavaScript focus, dimming and keyboard restrictions.
    """
    show_me = [item for item in app.button if item.label == "Show me"]
    if show_me:
        before = deepcopy(app.session_state["demo_focus"])
        assert before["mode"] == "explain" and before["target"]
        show_me[0].click().run()
        after = app.session_state["demo_focus"]
        assert after == {**before, "mode": "act"}
        assert not any(item.label == "Show me" for item in app.button)
    if expected_target is not None:
        assert app.session_state["demo_focus"]["mode"] == "act"
        assert app.session_state["demo_focus"]["target"] == expected_target


def practice_action(app, label):
    reveal_practice_action(app)
    button(app, label).click().run()


def start_practice_in_app(app):
    button(app, "Start practice").click().run()
    assert app.session_state["demo_step"] == "routine"
    assert app.session_state["page"] == "Choose routine"
    reveal_practice_action(app, ".st-key-habit_option_wind_down")
    app.button(key="habit_wind_down").click().run()
    reveal_practice_action(app, ".st-key-routine_plan")
    button(app, "Save plan and go to Today").click().run()
    assert app.session_state["page"] == "Today"
    assert app.session_state["demo_step"] == "planned"
    reveal_practice_action(app, ".st-key-dashboard_add")
    app.button(key="dashboard_add").click().run()
    assert app.session_state["demo_step"] == 1


def continue_demo_after_checkin(app):
    if "demo_step" in app.session_state and app.session_state["demo_step"] == "edit":
        assert app.session_state["page"] == "Night detail"
        reveal_practice_action(app, ".st-key-tour_edit_night")
        button(app, "Continue to my dashboard").click().run()


def fresh_app():
    """Launch at the real startup screen, including for a saved local space."""
    return JourneyAppTest(ENTRY, default_timeout=60).run()


def entered_saved_space():
    """Open a saved space through Welcome without repeating setup."""
    app = fresh_app()
    assert app.session_state["page"] == "Welcome"
    button(app, "Continue to my space").click().run()
    return app


def test_rerun_adapter_preserves_active_edits_and_app_errors(tmp_path):
    """The adapter fixes a shorter destination without hiding real failures."""
    script = tmp_path / "rerun_reproduction.py"
    script.write_text(
        "import streamlit as st\n"
        "st.session_state.setdefault('page', 'setup')\n"
        "with st.empty().container():\n"
        "    if st.session_state.page == 'setup':\n"
        "        st.title('Setup')\n"
        "        st.caption('A longer screen')\n"
        "        st.radio('Old choice', ['A', 'B'])\n"
        "        if st.button('Continue'):\n"
        "            st.session_state.page = 'home'\n"
        "            st.rerun()\n"
        "    else:\n"
        "        name = st.text_input('Active field')\n"
        "        if st.button('Submit'):\n"
        "            st.session_state['submitted'] = name\n"
        "            raise ValueError('Visible application error')\n",
        encoding="utf-8",
    )
    app = JourneyAppTest(script, default_timeout=60).run()
    button(app, "Continue").click().run()
    assert not app.radio
    assert field(app.text_input, "Active field")
    field(app.text_input, "Active field").set_value("A real pending edit")
    button(app, "Submit").click().run()
    assert app.session_state["submitted"] == "A real pending edit"
    assert len(app.exception) == 1
    assert "Visible application error" in app.exception[0].message


def create_space_and_routine(goal="Make more room for sleep"):
    app = fresh_app()
    button(app, "Create my space").click().run()
    field(app.text_input, "What should we call you? (optional)").set_value("Jo")
    button(app, "Continue").click().run()
    field(app.radio, "Your goal").set_value(goal)
    button(app, "Create my space").click().run()
    assert app.session_state["page"] == "Today"
    button(app, "Choose a routine").click().run()
    app.button(key="habit_wind_down").click().run()
    field(app.text_input, "Make it specific (optional)").set_value("Read quietly before bed")
    button(app, "Save plan and go to Today").click().run()
    assert app.session_state["page"] == "Today"
    assert not app.exception
    return app


@pytest.mark.parametrize("goal,preview", [
    ("Feel more rested", "Your morning restfulness"),
    ("Spend less time awake at night", "Your estimated wake time during sleep"),
    ("Make more room for sleep", "Your estimated sleep duration"),
])
def test_setup_goal_preview_matches_the_comparison_created(goal, preview):
    app = fresh_app()
    button(app, "Create my space").click().run()
    button(app, "Continue").click().run()
    field(app.radio, "Your goal").set_value(goal).run()
    assert any(preview in item.value for item in app.markdown)
    button(app, "Create my space").click().run()
    assert any(goal in item.value for item in app.caption)
    button(app, "Choose a routine").click().run()
    app.button(key="habit_wind_down").click().run()
    button(app, "Save plan and go to Today").click().run()
    assert active_experiment(load_workspace())["outcome"] == GOALS[goal]
    assert not app.exception


def open_night(app, recording):
    """Follow the log's card into one recording, without manipulating navigation state."""
    app.button(key="nav_Night log").click().run()
    is_demo = "demo" in app.session_state and app.session_state["demo"]
    workspace = app.session_state["demo_workspace"] if is_demo else app.session_state["workspace"]
    experiment = active_experiment(workspace)
    record = next(record for record in experiment["recordings"] if record["recording"] == recording)
    app.button(key=f"night_card_{experiment['id']}_{record['subject']}_{recording}").click().run()
    assert app.session_state["page"] == "Night detail"


def open_progress(app):
    app.button(key="nav_Today").click().run()
    button(app, "Open routine progress").click().run()
    assert app.session_state["page"] == "Routine progress"


def save_checkin(app, night_date, rating=None):
    field(app.date_input, "Night date").set_value(night_date)
    if rating is not None:
        field(app.select_slider, "How rested did you feel? (optional)").set_value(rating)
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    assert app.session_state["page"] == "Night log"


def upload_bytes(label, content):
    """AppTest has no file-upload setter; replace only the widget's return value."""
    return patch("streamlit.file_uploader",
                 side_effect=lambda actual_label, **kwargs: BytesIO(content)
                 if actual_label == label else None)


def analyse_generated_nights(app, feature_frame):
    button(app, "Log a night").click().run()
    with upload_bytes("Choose an EEG feature CSV", feature_frame.to_csv(index=False).encode()):
        app.run()
        button(app, "Analyse & add nights").click().run(timeout=60)
    assert app.session_state["page"] == "Night detail"
    assert not app.exception


def test_welcome_demo_is_explorable_without_saving_personal_data():
    # Practice is explicitly illustrative and must also work without model files.
    # Patch the call sites, not the source symbol: first-time module imports
    # must not retain a mock that would leak into later real-inference tests.
    with patch("app.night_views.predict_frame",
               side_effect=AssertionError("Demo must not run inference")) as night_predict, \
            patch("app.upload_views.predict_frame",
                  side_effect=AssertionError("Demo must not run inference")) as upload_predict, \
            patch("app.inference.model_fingerprint",
               side_effect=AssertionError("Demo must not check a model")) as fingerprint, \
            patch("app.inference.load_bundle",
                  side_effect=AssertionError("Demo must not load a model")) as load_model:
        app = fresh_app()
        assert not app.exception
        assert "A routine worth keeping" in app.title[0].value
        assert load_workspace_snapshot() == (None, 0)
        button(app, "Explore the demo").click().run()
        assert app.session_state["demo"] is True
        assert app.session_state["workspace"] is None
        assert app.session_state["demo_step"] == 0
        assert app.session_state["page"] == "Demo guide"
        assert app.session_state["demo_focus"] == {
            "mode": "explain", "token": "intro", "target": "",
        }
        assert active_experiment(app.session_state["demo_workspace"])["recordings"] == []

        # The learner adds an example, rather than only clicking through slides.
        start_practice_in_app(app)
        assert app.session_state["demo_step"] == 1
        assert app.session_state["page"] == "Add night"
        reveal_practice_action(app, ".st-key-practice_file_action")
        file_token = app.session_state["demo_focus"]["token"]
        practice_action(app, "Use example recording")
        assert app.session_state["demo_focus"]["mode"] == "explain"
        assert app.session_state["demo_focus"]["token"] != file_token
        reveal_practice_action(app, ".st-key-practice_recording_selection")
        assert field(app.selectbox, "Participant").value == "Alex (example)"
        field(app.multiselect, "Recordings to add").set_value([]).run()
        assert button(app, "Add selected night").disabled is True
        field(app.multiselect, "Recordings to add").set_value(["Night 1"]).run()
        practice_action(app, "Add selected night")
        assert app.session_state["demo_step"] == 2
        assert app.session_state["page"] == "Night detail"
        first = active_experiment(app.session_state["demo_workspace"])["recordings"][0]
        assert first["rating"] is None
        assert field(app.date_input, "Night date").value == date.fromisoformat(first["date"])
        assert field(app.date_input, "Night date").disabled is True
        assert not app.radio and not app.multiselect
        reveal_practice_action(app, ".st-key-tour_night_checkin")
        field(app.select_slider, "How rested did you feel? (optional)").set_value(1)
        button(app, "Save check-in").click().run()
        continue_demo_after_checkin(app)
        assert app.session_state["demo_step"] == 3
        assert app.session_state["page"] == "Today"
        assert len(active_experiment(app.session_state["demo_workspace"])["recordings"]) == 1
        assert not app.get("plotly_chart")

        reveal_practice_action(app, ".st-key-tour_dashboard_insights")
        practice_action(app, "Add four more example nights")
        exp = active_experiment(app.session_state["demo_workspace"])
        assert app.session_state["demo_step"] == 4
        assert len(exp["recordings"]) == 5
        assert count_complete_nights(exp, PERIODS[0]) == 5
        assert exp["recordings"][0]["rating"] == 1
        assert exp["phase"] == "usual"
        reveal_practice_action(app, ".st-key-tour_start_change")
        practice_action(app, "Start my change tonight")
        assert app.session_state["demo_step"] == 5
        source = active_experiment(app.session_state["demo_source"])
        exp = active_experiment(app.session_state["demo_workspace"])
        assert exp["phase"] == "changed"
        assert exp["change_started_on"] == source["recordings"][5]["date"]
        reveal_practice_action(app, ".st-key-tour_add_changed")
        practice_action(app, "Add five example nights with the change")
        exp = active_experiment(app.session_state["demo_workspace"])
        assert app.session_state["demo_step"] == 6
        assert len(exp["recordings"]) == 10
        assert count_complete_nights(exp, PERIODS[0]) == 5
        assert count_complete_nights(exp, PERIODS[1]) == 5
        assert all(record["model_fingerprint"] == "illustrative-demo" for record in exp["recordings"])
        reveal_practice_action(app, ".st-key-tour_dashboard_insights")

        # Known example values: wake means are 45.0 and 18.0 minutes; four of
        # five changed nights are below the earlier median of 44.0 minutes.
        dashboard = "\n".join(item.value for item in app.markdown)
        assert "-27.0 min" in dashboard
        assert "4 of 5 nights" in dashboard
        assert "HOW FEELINGS AND RECORDINGS COMPARE" in dashboard
        assert "2.4 points more restful" in dashboard
        assert len(app.get("plotly_chart")) == 1
        assert not app.dataframe and not app.expander
        assert any(item.value == "What your nights are showing" for item in app.subheader)

        practice_action(app, "Explore Alex's sleep details")
        assert app.session_state["demo_step"] == "sleep"
        reveal_practice_action(app, ".st-key-dashboard_sleep_details")
        button(app, "View sleep details").click().run()
        assert app.session_state["page"] == "Sleep stages"
        reveal_practice_action(app, ".st-key-sleep_stage_metrics")
        assert "Deep sleep" in "\n".join(item.value for item in app.markdown)
        practice_action(app, "Review Alex's routine")
        assert app.session_state["demo_step"] == 7
        assert app.session_state["page"] == "Routine progress"
        reveal_practice_action(app, ".st-key-tour_keep_routine")
        button(app, "Keep this routine").click().run()
        assert app.session_state["demo_step"] == 8
        assert app.session_state["page"] == "Today"
        assert app.session_state["demo_focus"] == {
            "mode": "explain", "token": "complete", "target": "",
        }
        assert active_experiment(app.session_state["demo_workspace"])["phase"] == "complete"
        button(app, "Explore Alex's dashboard").click().run()
        assert app.session_state["demo_step"] is None
        assert app.session_state["demo_focus"] is None
        assert app.session_state["page"] == "Today"
        assert load_workspace_snapshot() == (None, 0)
        button(app, "Exit demo").click().run()
        assert app.session_state["page"] == "Welcome"
        assert "A routine worth keeping" in app.title[0].value
        assert not app.exception
        fingerprint.assert_not_called()
        load_model.assert_not_called()
        night_predict.assert_not_called()
        upload_predict.assert_not_called()


def test_practice_can_resume_skip_and_replay_without_touching_saved_space(completed_saved_workspace):
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    practice_action(app, "Use example recording")
    practice_action(app, "Add selected night")
    app.button(key="nav_Night log").click().run()
    assert app.session_state["demo_step"] == 2
    assert app.session_state["page"] == "Night log"
    assert app.session_state["demo_focus"] is None
    button(app, "Resume practice").click().run()
    assert app.session_state["page"] == "Night detail"
    assert len(active_experiment(app.session_state["demo_workspace"])["recordings"]) == 1
    app.button(key="tour_skip").click().run()
    assert app.session_state["demo_step"] is None
    assert app.session_state["demo_focus"] is None
    assert app.session_state["page"] == "Today"
    exp = active_experiment(app.session_state["demo_workspace"])
    assert len(exp["recordings"]) == 10
    assert exp["recordings"][0]["rating"] == 2
    assert load_workspace() == completed_saved_workspace

    button(app, "Replay practice").click().run()
    assert app.session_state["demo_step"] == 0
    assert app.session_state["demo_focus"]["token"] == "intro"
    assert app.session_state["page"] == "Demo guide"
    assert active_experiment(app.session_state["demo_workspace"])["recordings"] == []
    app.button(key="tour_skip").click().run()
    records = active_experiment(app.session_state["demo_workspace"])["recordings"]
    assert len(records) == len({record["recording"] for record in records}) == 10
    assert load_workspace() == completed_saved_workspace
    assert app.session_state["workspace"] == completed_saved_workspace
    assert not app.exception


def test_skipping_an_active_highlight_clears_focus_and_replay_requires_a_new_reveal():
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    reveal_practice_action(app, ".st-key-practice_file_action")
    app.button(key="tour_skip").click().run()
    assert app.session_state["demo_step"] is None
    assert app.session_state["demo_focus"] is None
    assert not any(item.label == "Show me" for item in app.button)
    assert len(active_experiment(app.session_state["demo_workspace"])["recordings"]) == 10
    button(app, "Replay practice").click().run()
    start_practice_in_app(app)
    assert app.session_state["demo_focus"]["mode"] == "explain"
    assert active_experiment(app.session_state["demo_workspace"])["recordings"] == []
    reveal_practice_action(app, ".st-key-practice_file_action")
    assert load_workspace_snapshot() == (None, 0)
    assert not app.exception


def test_example_period_shortcuts_are_idempotent_and_preserve_the_saved_checkin():
    source = build_demo_workspace()
    original_source = deepcopy(source)
    workspace = deepcopy(source)
    exp = active_experiment(workspace)
    exp["recordings"] = [exp["recordings"][0]]
    exp["phase"] = "usual"
    exp["recordings"][0]["rating"] = 1
    state = SimpleNamespace(demo_source=source, demo_workspace=workspace, demo_step=3)
    with patch("app.demo_guide.st.session_state", state):
        complete_example_period()
        assert len(exp["recordings"]) == 5
        assert state.demo_step == 4
        five = deepcopy(exp["recordings"])
        complete_example_period()
        assert exp["recordings"] == five
        complete_example_period(changed=True)
        assert len(exp["recordings"]) == 10
        assert state.demo_step == 6
        ten = deepcopy(exp["recordings"])
        complete_example_period(changed=True)
        assert exp["recordings"] == ten
    assert exp["recordings"][0]["rating"] == 1
    assert len({record["recording"] for record in exp["recordings"]}) == 10
    assert source == original_source


def test_onboarding_habit_choice_and_automatic_return():
    app = create_space_and_routine()
    stored = load_workspace()
    assert stored["profile"]["name"] == "Jo"
    assert stored["profile"]["goal"] == "Make more room for sleep"
    experiment = active_experiment(stored)
    assert experiment["habit_id"] == "wind_down"
    assert experiment["phase"] == "usual"
    assert experiment["change"] == "Read quietly before bed"
    assert experiment["outcome"] == SLEEP
    # Returning begins at Welcome and enters the saved space without setup.
    reopened = fresh_app()
    assert reopened.session_state["workspace"] == stored
    assert reopened.session_state["page"] == "Welcome"
    assert "A routine worth keeping" in reopened.title[0].value
    assert not any(item.key and item.key.startswith("nav_") for item in reopened.button)
    assert not reopened.text_input and not reopened.radio
    button(reopened, "Continue to my space").click().run()
    assert reopened.title[0].value == "Today"
    assert button(reopened, "Log a night")
    assert {item.label for item in reopened.button if item.key and item.key.startswith("nav_")} == {
        "Today", "Night log", "Settings"}
    assert not any(item.label in ("Experiment", "Nights") for item in reopened.button)
    assert not app.exception and not reopened.exception


def test_invalid_upload_uses_real_validation_and_preserves_saved_space():
    app = create_space_and_routine()
    before = load_workspace()
    button(app, "Log a night").click().run()
    with upload_bytes("Choose an EEG feature CSV", b"wrong\n1\n"):
        app.run()
    assert any("Missing required columns" in error.value for error in app.error)
    assert load_workspace() == before
    assert active_experiment(app.session_state["workspace"])["recordings"] == []
    assert not app.exception


def test_real_analysis_checkins_decision_reopen_and_delete(feature_frame, bundle):
    app = create_space_and_routine()
    button(app, "Log a night").click().run()
    with upload_bytes("Choose an EEG feature CSV", feature_frame.to_csv(index=False).encode()):
        app.run()
        assert len(app.multiselect[0].value) == 2
        button(app, "Analyse & add nights").click().run(timeout=60)
    assert not app.exception
    experiment = active_experiment(app.session_state["workspace"])
    assert [len(record["stages"]) for record in experiment["recordings"]] == [12, 9]
    assert all(record["model_fingerprint"] == bundle.fingerprint
               for record in experiment["recordings"])
    assert load_workspace()["subject"] == "7"

    # The daily check-in has just a date and an optional rating.
    assert len(app.date_input) == 1 and len(app.select_slider) == 1
    assert not app.radio and not app.multiselect and not app.text_area
    save_checkin(app, date(2026, 1, 1), 2)
    open_night(app, "2")
    assert field(app.date_input, "Night date").value is None
    assert field(app.select_slider, "How rested did you feel? (optional)").value == "Not recorded"
    save_checkin(app, date(2026, 1, 2), 4)
    open_night(app, "2")
    button(app, "Edit night details").click().run()
    field(app.radio, "Which part of your routine?").set_value("With the change").run()
    field(app.radio, "Did you follow your plan?").set_value("Yes")
    field(app.multiselect, "Anything unusual?").set_value(["Unusual stress"])
    button(app, "Save night details").click().run()

    saved_nights = active_experiment(load_workspace())["recordings"]
    assert [night["date"] for night in saved_nights] == ["2026-01-01", "2026-01-02"]
    assert [night["rating"] for night in saved_nights] == [2, 4]
    assert saved_nights[1]["adherence"] is True
    assert saved_nights[1]["context"] == ["Unusual stress"]
    assert active_experiment(load_workspace())["phase"] == "changed"
    open_progress(app)
    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    assert not app.dataframe and not app.expander
    button(app, "View comparison details").click().run()
    assert app.session_state["page"] == "Comparison details"
    assert len(app.dataframe) == 1
    button(app, "← Back to routine progress").click().run()
    button(app, "Keep this routine").click().run()
    saved = load_workspace()
    assert active_experiment(saved)["decision"] == "Keep this routine"
    assert active_experiment(saved)["phase"] == "complete"
    assert active_experiment(saved)["reviewed"] is True

    # Returning reuses trusted predictions, rather than asking for another upload.
    with patch("app.night_views.predict_frame", side_effect=AssertionError("Unexpected recomputation")), \
            patch("app.upload_views.predict_frame", side_effect=AssertionError("Unexpected recomputation")):
        reopened = entered_saved_space()
        open_night(reopened, "2")
    assert active_experiment(reopened.session_state["workspace"])["recordings"] == saved_nights
    assert not reopened.exception
    button(reopened, "Settings").click().run()
    assert len(reopened.get("download_button")) == 4
    field(reopened.checkbox, "Delete all profiles, recordings, experiments and decisions").check()
    button(reopened, "Delete all local spaces").click().run()
    assert load_workspace() is None
    assert reopened.session_state["workspace"] is None
    assert "A routine worth keeping" in reopened.title[0].value
    assert not reopened.exception


def test_import_legacy_experiment_keeps_diaries_but_reanalyses_predictions(feature_frame, bundle):
    old = new_experiment()
    update_plan(old, "Saved experiment", "A routine change", SLEEP)
    merge_recordings(old, feature_frame, "7", bundle.preprocessor["feature_columns"])
    old["recordings"][0]["stages"] = ["W"] * 12
    old["recordings"][0]["date"] = "2026-01-01"
    old["recordings"][0]["period"] = "Usual routine"
    old["recordings"][0]["rating"] = 3
    backup = save_experiment(old)
    app = create_space_and_routine()
    original_id = active_experiment(load_workspace())["id"]
    button(app, "Settings").click().run()
    with upload_bytes("Earlier experiment JSON", backup):
        app.run()
        button(app, "Import as a separate experiment").click().run()
    imported = active_experiment(load_workspace())
    assert imported["id"] != original_id
    assert imported["title"] == "Saved experiment"
    assert len(load_workspace()["experiments"]) == 2
    assert len(imported["recordings"]) == 2
    assert imported["recordings"][0]["rating"] == 3
    assert all(record["stages"] is None for record in imported["recordings"])
    assert app.session_state["page"] == "Night log"
    open_night(app, "1")
    assert button(app, "Analyse this night")
    assert not app.exception


@pytest.fixture
def completed_saved_workspace(feature_frame, bundle):
    """Seed an already reviewed experiment to focus regression tests on edits."""
    workspace = make_workspace("Jo", DEVICES[0], "Make more room for sleep")
    experiment = start_experiment(workspace, "wind_down")
    merge_recordings(experiment, feature_frame, "7", bundle.preprocessor["feature_columns"])
    workspace["subject"] = "7"
    for i, record in enumerate(experiment["recordings"]):
        predictions, quality = predict_frame(record_frame(record), bundle)
        record.update(stages=predictions["Predicted stage"].tolist(),
                      quality=quality.iloc[0].to_dict(), model_fingerprint=bundle.fingerprint,
                      context=[], adherence=True if i else None)
        set_diary(record, f"2026-01-0{i + 1}", PERIODS[i], 2 + i * 2, "")
    experiment.update(decision="Keep this routine", phase="complete", reviewed=True)
    save_workspace(workspace)
    return load_workspace()


@pytest.mark.parametrize("edited_field", ["rating", "routine", "context"])
def test_changed_checkin_reopens_decision_but_keeps_earlier_choice(
        completed_saved_workspace, edited_field):
    app = entered_saved_space()
    open_night(app, "2")
    if edited_field == "rating":
        field(app.select_slider, "How rested did you feel? (optional)").set_value(1)
        button(app, "Save check-in").click().run()
        continue_demo_after_checkin(app)
    else:
        button(app, "Edit night details").click().run()
        if edited_field == "routine":
            field(app.radio, "Which part of your routine?").set_value("Before the change")
        else:
            field(app.multiselect, "Anything unusual?").set_value(["Travel"])
        button(app, "Save night details").click().run()
    changed = active_experiment(load_workspace())
    assert changed["decision"] is None
    assert changed["phase"] == "changed"
    assert changed["reviewed"] is False
    assert changed["decision_history"][-1]["decision"] == "Keep this routine"
    assert changed["decision_history"][-1]["reason"] == (
        "A check-in was edited." if edited_field == "rating" else "A night's routine or context was edited.")
    assert all(record["stages"] for record in changed["recordings"])
    assert not app.exception


def test_demo_enter_exit_keeps_real_workspace_and_decision(completed_saved_workspace):
    app = entered_saved_space()
    button(app, "Settings").click().run()
    button(app, "Explore the demo").click().run()
    app.button(key="tour_skip").click().run()
    assert app.session_state["demo_step"] is None
    open_progress(app)
    original_demo_id = active_experiment(app.session_state["demo_workspace"])["id"]
    button(app, "Settings").click().run()
    button(app, "Choose a different routine").click().run()
    assert active_experiment(app.session_state["demo_workspace"])["decision"] is None
    app.button(key="habit_caffeine").click().run()
    button(app, "Save plan and go to Today").click().run()
    previous_demo = next(exp for exp in app.session_state["demo_workspace"]["experiments"]
                         if exp["id"] == original_demo_id)
    assert previous_demo["decision"] == "Try a different routine"
    assert load_workspace() == completed_saved_workspace
    button(app, "Exit demo").click().run()
    assert app.session_state["workspace"] == completed_saved_workspace
    assert active_experiment(app.session_state["workspace"])["decision"] == "Keep this routine"
    assert app.session_state["page"] == "Welcome"
    assert "A routine worth keeping" in app.title[0].value
    assert not app.exception


def test_returning_welcome_demo_and_continue_preserve_the_saved_space(completed_saved_workspace):
    app = fresh_app()
    assert app.session_state["page"] == "Welcome"
    assert not any(item.key and item.key.startswith("nav_") for item in app.button)
    assert not any(item.label == "Create my space" for item in app.button)
    assert button(app, "Continue to my space")
    button(app, "Explore the demo").click().run()
    app.button(key="tour_skip").click().run()
    open_progress(app)
    button(app, "Keep this routine").click().run()
    assert load_workspace() == completed_saved_workspace
    button(app, "Exit demo").click().run()
    assert app.session_state["page"] == "Welcome"
    assert app.session_state["workspace"] == completed_saved_workspace
    button(app, "Continue to my space").click().run()
    assert app.session_state["page"] == "Today"
    assert not app.text_input and not app.radio
    button(app, "Settings").click().run()
    button(app, "Back to welcome").click().run()
    assert app.session_state["page"] == "Welcome"
    assert load_workspace() == completed_saved_workspace
    assert not app.exception


def test_old_model_results_are_cleared_on_return_and_recomputed(
        completed_saved_workspace, bundle):
    previous = completed_saved_workspace
    for record in active_experiment(previous)["recordings"]:
        record["model_fingerprint"] = "previous-model-version"
    save_workspace(previous)
    app = entered_saved_space()
    cleared = active_experiment(load_workspace())
    assert all(record["stages"] is None and record["quality"] is None
               and record["model_fingerprint"] is None for record in cleared["recordings"])
    assert [record["rating"] for record in cleared["recordings"]] == [2, 4]
    assert cleared["decision"] is None
    assert len(cleared["decision_history"]) == 1
    assert cleared["decision_history"][0]["reason"] == "The saved model changed."
    open_night(app, "1")
    selected_id = app.session_state["selected_recording"]
    button(app, "Analyse this night").click().run()
    records = active_experiment(load_workspace())["recordings"]
    analysed = next(record for record in records if record["recording"] == selected_id)
    assert analysed["stages"]
    assert analysed["model_fingerprint"] == bundle.fingerprint
    assert sum(record["stages"] is not None for record in records) == 1
    assert not app.exception


def test_model_changed_while_tab_is_open_invalidates_existing_results(completed_saved_workspace):
    app = entered_saved_space()
    assert all(record["stages"]
               for record in active_experiment(app.session_state["workspace"])["recordings"])
    with patch("app.inference.model_fingerprint", return_value="replacement-model"):
        app.run()
    saved = active_experiment(load_workspace())
    assert all(record["stages"] is None for record in saved["recordings"])
    assert saved["decision"] is None
    assert not app.exception


def test_missing_model_does_not_expose_old_results_after_another_rerun(completed_saved_workspace):
    with patch("app.inference.model_fingerprint", side_effect=ValueError("Required model file is missing")):
        app = fresh_app()
        # Welcome and the illustrative demo remain available without model files.
        assert app.session_state["page"] == "Welcome"
        assert not app.error
        button(app, "Explore the demo").click().run()
        assert app.session_state["demo"] is True
        assert not app.error
        button(app, "Exit demo").click().run()
        assert app.session_state["page"] == "Welcome"
        button(app, "Continue to my space").click().run()
        assert any("model file" in error.value for error in app.error)
        app.run()
        assert any("model file" in error.value for error in app.error)
        assert not app.title
    # Missing model files must not destroy the previously saved evidence.
    assert load_workspace() == completed_saved_workspace
    assert not app.exception


def test_save_failure_keeps_unsaved_edits_for_retry():
    app = create_space_and_routine()
    original = load_workspace()
    button(app, "Settings").click().run()
    field(app.text_input, "Name or nickname").set_value("A new nickname")
    with patch("app.storage.save_workspace", side_effect=StorageError("Temporary storage problem")):
        button(app, "Save profile").click().run()
    assert load_workspace() == original
    assert app.session_state["workspace"]["profile"]["name"] == "A new nickname"
    assert any("Not saved yet" in error.value for error in app.error)
    assert not app.exception
    button(app, "Retry saving").click().run()
    assert load_workspace()["profile"]["name"] == "A new nickname"
    assert "save_error" not in app.session_state
    assert not app.exception


def test_conflicting_tab_cannot_overwrite_and_can_reload_newer_save():
    app = create_space_and_routine()
    newer = load_workspace()
    newer["profile"]["name"] = "Saved in another tab"
    save_workspace(newer)
    button(app, "Settings").click().run()
    field(app.text_input, "Name or nickname").set_value("Stale tab edit")
    button(app, "Save profile").click().run()
    assert load_workspace()["profile"]["name"] == "Saved in another tab"
    assert app.session_state["workspace"]["profile"]["name"] == "Stale tab edit"
    assert any("another tab" in error.value for error in app.error)
    button(app, "Discard unsaved edits and reload").click().run()
    assert app.session_state["workspace"]["profile"]["name"] == "Saved in another tab"
    assert "save_error" not in app.session_state
    assert not app.exception


def test_started_change_uses_real_night_dates_for_automatic_membership(feature_frame):
    app = create_space_and_routine()
    button(app, "Settings").click().run()
    assert [tab.label for tab in app.tabs] == ["Profile", "Routine & history", "Data & privacy", "About"]
    button(app, "Start the change early").click().run()
    experiment = active_experiment(load_workspace())
    assert experiment["change_started_on"] == date.today().isoformat()
    assert experiment["phase"] == "changed"
    analyse_generated_nights(app, feature_frame)
    save_checkin(app, date.today() - timedelta(days=1))
    open_night(app, "2")
    save_checkin(app, date.today())
    experiment = active_experiment(load_workspace())
    assert [record["period"] for record in experiment["recordings"]] == list(PERIODS)
    assert all(record["rating"] is None for record in experiment["recordings"])
    assert count_complete_nights(experiment, PERIODS[0]) == 1
    assert count_complete_nights(experiment, PERIODS[1]) == 1
    assert not app.exception


def test_restfulness_goal_can_save_without_rating_but_still_requests_it(feature_frame):
    app = create_space_and_routine(goal="Feel more rested")
    analyse_generated_nights(app, feature_frame)
    save_checkin(app, date.today() - timedelta(days=1))
    saved = active_experiment(load_workspace())
    assert saved["outcome"] == RATING
    assert saved["recordings"][0]["rating"] is None
    assert count_complete_nights(saved, PERIODS[0]) == 0
    app.button(key="nav_Today").click().run()
    dashboard = "\n".join(item.value for item in app.markdown)
    assert "Your sleep estimates are ready" in dashboard
    assert "Estimated sleep" in dashboard
    assert not app.get("plotly_chart")  # One dated night is not drawn as a trend.
    assert active_experiment(app.session_state["workspace"])["outcome"] == RATING
    button(app, "Finish my night").click().run()
    assert app.session_state["selected_recording"] == "1"
    field(app.select_slider, "How rested did you feel? (optional)").set_value(3)
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    saved = active_experiment(load_workspace())
    assert saved["recordings"][0]["rating"] == 3
    assert count_complete_nights(saved, PERIODS[0]) == 1
    assert not app.exception


def test_sleep_stage_detail_is_optional_and_returns_to_same_night(completed_saved_workspace):
    app = entered_saved_space()
    open_night(app, "2")
    assert len(app.date_input) == 1
    assert not app.radio and not app.multiselect and not app.text_area
    assert not app.get("plotly_chart")
    button(app, "Sleep stages").click().run()
    assert app.session_state["page"] == "Sleep stages"
    assert len(app.get("plotly_chart")) == 1
    assert not app.date_input and not app.select_slider
    button(app, "Back to night").click().run()
    assert app.session_state["page"] == "Night detail"
    assert app.session_state["selected_recording"] == "2"
    assert field(app.date_input, "Night date").value == date(2026, 1, 2)
    assert load_workspace() == completed_saved_workspace
    assert not app.exception


def test_duplicate_night_date_is_rejected_without_reopening_decision(completed_saved_workspace):
    app = entered_saved_space()
    open_night(app, "2")
    field(app.date_input, "Night date").set_value(date(2026, 1, 1))
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    assert any("already uses this date" in error.value for error in app.error)
    assert load_workspace() == completed_saved_workspace
    assert active_experiment(app.session_state["workspace"])["decision"] == "Keep this routine"
    assert app.session_state["page"] == "Night detail"
    assert not app.exception


def test_setup_back_preserves_recorder_and_goal_choices():
    """Going back to check a name must not silently change earlier answers."""
    app = fresh_app()
    button(app, "Create my space").click().run()
    field(app.text_input, "What should we call you? (optional)").set_value("Sam")
    field(app.selectbox, "Where will your recordings come from?").set_value(DEVICES[-1])
    button(app, "Continue").click().run()
    chosen_goal = field(app.radio, "Your goal").options[-1]
    field(app.radio, "Your goal").set_value(chosen_goal).run()
    button(app, "Back").click().run()
    assert field(app.text_input, "What should we call you? (optional)").value == "Sam"
    assert field(app.selectbox, "Where will your recordings come from?").value == DEVICES[-1]
    button(app, "Continue").click().run()
    assert field(app.radio, "Your goal").value == chosen_goal
    button(app, "Create my space").click().run()
    assert load_workspace()["profile"] == {
        "name": "Sam", "device": DEVICES[-1], "goal": chosen_goal,
    }
    assert not app.exception


def test_practice_membership_edit_cannot_strand_the_start_change_step():
    """Exploring optional edits must leave the practice's next action usable."""
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    practice_action(app, "Use example recording")
    practice_action(app, "Add selected night")
    button(app, "Edit night details").click().run()
    field(app.radio, "Which part of your routine?").set_value("With the change").run()
    button(app, "Save night details").click().run()
    practice_action(app, "Save check-in")
    continue_demo_after_checkin(app)
    practice_action(app, "Add four more example nights")
    # Editing membership already started the changed phase. Practice must
    # honour it rather than ask for an unavailable Start action or undo it.
    assert app.session_state["demo_step"] == 5
    exp = active_experiment(app.session_state["demo_workspace"])
    assert count_complete_nights(exp, PERIODS[0]) == 4
    assert count_complete_nights(exp, PERIODS[1]) == 1
    practice_action(app, "Add five example nights with the change")
    exp = active_experiment(app.session_state["demo_workspace"])
    assert app.session_state["demo_step"] == 6
    assert count_complete_nights(exp, PERIODS[0]) == 4
    assert count_complete_nights(exp, PERIODS[1]) == 6
    assert not app.exception


def test_practice_removal_does_not_claim_a_successful_checkin():
    """Removing the example is not equivalent to finishing its check-in."""
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    practice_action(app, "Use example recording")
    practice_action(app, "Add selected night")
    button(app, "Edit night details").click().run()
    field(app.checkbox, "Remove this recording and its check-in").check().run()
    button(app, "Remove night").click().run()
    exp = active_experiment(app.session_state["demo_workspace"])
    # Stage 3 explicitly says "Your first night is logged"; it cannot be
    # entered as a side effect of another action that also returns to Night log.
    assert not (app.session_state["demo_step"] == 3 and not exp["recordings"])
    assert app.session_state["demo_step"] == 1
    assert app.session_state["page"] == "Add night"
    practice_action(app, "Add selected night")
    practice_action(app, "Save check-in")
    continue_demo_after_checkin(app)
    assert app.session_state["demo_step"] == 3
    assert len(active_experiment(app.session_state["demo_workspace"])["recordings"]) == 1
    assert not app.exception


def test_comparison_and_night_back_routes_preserve_the_active_routine(
        completed_saved_workspace):
    app = entered_saved_space()
    original_id = active_experiment(app.session_state["workspace"])["id"]
    open_progress(app)
    button(app, "View comparison details").click().run()
    assert app.session_state["page"] == "Comparison details"
    button(app, "← Back to routine progress").click().run()
    assert app.session_state["page"] == "Routine progress"
    button(app, "← Back to Today").click().run()
    assert app.session_state["page"] == "Today"
    open_night(app, "2")
    button(app, "Edit night details").click().run()
    button(app, "Back to night").click().run()
    assert app.session_state["selected_recording"] == "2"
    button(app, "Back to night log").click().run()
    assert app.session_state["page"] == "Night log"
    app.button(key="nav_settings").click().run()
    assert [tab.label for tab in app.tabs] == [
        "Profile", "Routine & history", "Data & privacy", "About",
    ]
    button(app, "Back to welcome").click().run()
    button(app, "Continue to my space").click().run()
    assert active_experiment(app.session_state["workspace"])["id"] == original_id
    assert load_workspace() == completed_saved_workspace
    assert not app.exception


def test_retrying_initial_save_finishes_setup_on_today():
    """A recovered save should complete the action that originally failed."""
    app = fresh_app()
    button(app, "Create my space").click().run()
    button(app, "Continue").click().run()
    with patch("app.storage.save_workspace", side_effect=StorageError("Temporary storage problem")):
        button(app, "Create my space").click().run()
    assert any("Not saved yet" in item.value for item in app.error)
    assert load_workspace_snapshot() == (None, 0)
    button(app, "Retry saving").click().run()
    assert app.session_state["page"] == "Today"
    assert app.title[0].value == "Today"
    assert button(app, "Choose a routine")
    assert load_workspace()["profile"] == app.session_state["workspace"]["profile"]
    assert not app.exception


@pytest.mark.parametrize("entry", ["Today", "Settings"])
def test_back_from_another_routine_keeps_the_existing_routine(
        completed_saved_workspace, entry):
    """Browsing a potential replacement does not abandon the current routine."""
    app = entered_saved_space()
    original = deepcopy(app.session_state["workspace"])
    if entry == "Settings":
        app.button(key="nav_settings").click().run()
        button(app, "Choose a different routine").click().run()
    else:
        button(app, "Try another change").click().run()
    assert app.session_state["page"] == "Choose routine"
    app.button(key="habit_wake_time").click().run()
    button(app, "← Back to Today").click().run()
    assert app.session_state["page"] == "Today"
    assert active_experiment(app.session_state["workspace"])["id"] == original["active_experiment"]
    assert len(app.session_state["workspace"]["experiments"]) == len(original["experiments"])
    assert load_workspace() == completed_saved_workspace
    assert not app.exception


def test_post_keep_tracking_new_routine_and_history_preserve_previous_results(completed_saved_workspace):
    saved = load_workspace()
    previous = active_experiment(saved)
    keep_routine(previous)
    save_workspace(saved)
    previous_id = previous["id"]
    comparison = deepcopy(previous["saved_comparison"])
    app = entered_saved_space()
    assert button(app, "Keep tracking") and button(app, "Try another change")
    button(app, "Keep tracking").click().run()
    assert app.session_state["page"] == "Add night"
    assert active_experiment(app.session_state["workspace"])["id"] == previous_id
    app.button(key="nav_Today").click().run()

    # Starting a new plan leaves all earlier nights and the saved choice intact.
    button(app, "Try another change").click().run()
    app.button(key="habit_wake_time").click().run()
    button(app, "Save plan and go to Today").click().run()
    newer = active_experiment(app.session_state["workspace"])
    newer_id = newer["id"]
    assert newer_id != previous_id and not newer["recordings"]
    persisted = deepcopy(load_workspace())
    button(app, "View routine history").click().run()
    app.button(key=f"history_view_{previous_id}").click().run()
    assert app.session_state["page"] == "Saved routine"
    assert any(item.value == "When you chose to keep it" for item in app.subheader)
    assert active_experiment(app.session_state["workspace"])["id"] == newer_id
    assert load_workspace() == persisted
    old = next(e for e in persisted["experiments"] if e["id"] == previous_id)
    assert old["saved_comparison"] == comparison

    # Returning to an old routine requires an explicit choice; it keeps the new one.
    button(app, "Make this my current routine").click().run()
    assert app.session_state["page"] == "Today"
    assert active_experiment(load_workspace())["id"] == previous_id
    assert len(load_workspace()["experiments"]) == 2
    assert not app.exception


@pytest.mark.parametrize("phase", ["usual", "changed"])
def test_unfinished_extra_night_does_not_hide_ready_next_step(completed_saved_workspace, phase):
    saved = load_workspace()
    experiment = active_experiment(saved)
    source = deepcopy(experiment["recordings"][0])
    experiment.update(phase=phase, decision=None)
    experiment["recordings"] = []
    for i in range(5 if phase == "usual" else 10):
        record = deepcopy(source)
        record.update(recording=str(i + 1), date=f"2026-01-{i + 1:02d}",
                      period=PERIODS[int(i >= 5)], rating=None)
        experiment["recordings"].append(record)
    pending = deepcopy(source)
    pending.update(recording="11", date=None, period=None, rating=None, stages=None)
    experiment["recordings"].append(pending)
    save_workspace(saved)
    app = entered_saved_space()
    next_label = "Start my change tonight" if phase == "usual" else "See my comparison"
    assert button(app, next_label)
    assert button(app, "Finish my night")
    button(app, next_label).click().run()
    assert not app.exception
    if phase == "changed":
        assert button(app, "Keep this routine")
    else:
        assert active_experiment(load_workspace())["phase"] == "changed"


def practice_ready_to_start():
    app = fresh_app()
    button(app, "Explore the demo").click().run()
    start_practice_in_app(app)
    practice_action(app, "Use example recording")
    practice_action(app, "Add selected night")
    practice_action(app, "Save check-in")
    continue_demo_after_checkin(app)
    practice_action(app, "Add four more example nights")
    assert app.session_state["demo_step"] == 4
    return app


def test_practice_restores_a_removed_starting_night_without_losing_other_edits():
    app = practice_ready_to_start()
    open_night(app, "2")
    field(app.select_slider, "How rested did you feel? (optional)").set_value(5)
    button(app, "Save check-in").click().run()
    continue_demo_after_checkin(app)
    before = deepcopy(active_experiment(app.session_state["demo_workspace"])["recordings"][1:])
    open_night(app, "1")
    button(app, "Edit night details").click().run()
    field(app.checkbox, "Remove this recording and its check-in").check().run()
    button(app, "Remove night").click().run()
    app.button(key="nav_Today").click().run()
    assert app.session_state["demo_step"] == 4
    assert app.session_state["demo_focus"] is None
    button(app, "Restore starting example nights").click().run()
    exp = active_experiment(app.session_state["demo_workspace"])
    assert len(exp["recordings"]) == 5
    assert exp["recordings"][1:] == before
    practice_action(app, "Start my change tonight")
    assert app.session_state["demo_step"] == 5
    assert not app.exception


def test_practice_resumes_its_original_routine_after_exploring_another():
    app = practice_ready_to_start()
    original_id = active_experiment(app.session_state["demo_workspace"])["id"]
    app.button(key="nav_settings").click().run()
    button(app, "Choose a different routine").click().run()
    app.button(key="habit_caffeine").click().run()
    button(app, "Save plan and go to Today").click().run()
    new_routine = active_experiment(app.session_state["demo_workspace"])
    new_id = new_routine["id"]
    assert new_id != original_id and not new_routine["recordings"]
    assert app.session_state["demo_step"] == 4
    assert app.session_state["demo_focus"] is None
    button(app, "Resume practice").click().run()
    workspace = app.session_state["demo_workspace"]
    assert active_experiment(workspace)["id"] == original_id
    assert len(active_experiment(workspace)["recordings"]) == 5
    assert not next(exp for exp in workspace["experiments"] if exp["id"] == new_id)["recordings"]
    practice_action(app, "Start my change tonight")
    assert app.session_state["demo_step"] == 5
    assert load_workspace_snapshot() == (None, 0)
    assert not app.exception
