"""Hands-on practice using invented nights and the normal app's save actions."""
from copy import deepcopy
from datetime import date, timedelta
import streamlit as st
from app.runtime import session_mode, saving_notice

from app.experiments import PERIODS
from app.journey import (
    active_experiment, build_demo_workspace, count_complete_nights, invalidate_decision,
)
from app.presentation import html, info_cards

DEMO_VERSION = 7
PRACTICE_PAGES = {
    0: "Demo guide", 1: "Add night", 2: "Night detail", 3: "Today",
    4: "Today", 5: "Today", 6: "Today", 7: "Routine progress", 8: "Today",
    "routine": "Choose routine", "planned": "Today", "edit": "Night detail", "sleep": "Today",
}


def start_practice():
    """Keep a full example separate from the nights the learner has added."""
    source = build_demo_workspace()
    workspace = deepcopy(source)
    experiment = active_experiment(workspace)
    experiment.update(recordings=[], phase="usual", decision=None)
    st.session_state.pop("demo_chosen_habit", None)
    st.session_state.update(
        demo=True, demo_source=source, demo_workspace=workspace,
        demo_step=0, demo_guide_version=DEMO_VERSION, demo_example_loaded=False,
        demo_ready_token=None, demo_focus=None,
    )


def show_completed_example():
    """Skipping is explicit and replaces only fictional practice data."""
    st.session_state.demo_workspace = deepcopy(st.session_state.demo_source)
    st.session_state.demo_step = None
    st.session_state.demo_focus = None


def add_tracking_example():
    """Add at most one invented follow-up to Alex's original routine.

    The caller opens the returned night for its normal check-in. This never
    analyses a recording, writes storage or supplies a morning rating.
    """
    if not st.session_state.get("demo"):
        raise ValueError("The prepared follow-up is available only in the demo.")
    source = active_experiment(st.session_state.demo_source)
    experiment = active_experiment(st.session_state.demo_workspace)
    if not experiment or experiment["id"] != source["id"]:
        raise ValueError("Open Alex's original routine before adding its example follow-up.")
    existing = next((night for night in experiment["recordings"]
                     if night.get("demo_tracking_example")), None)
    if existing is not None:
        return existing
    original_ids = {night["recording"] for night in source["recordings"]}
    if not original_ids.issubset({night["recording"] for night in experiment["recordings"]}):
        raise ValueError("Finish the ten-night example before adding a follow-up.")
    last_date = max(date.fromisoformat(night["date"])
                    for night in experiment["recordings"] if night.get("date"))
    next_date = last_date + timedelta(days=1)
    if next_date > date.today():
        raise ValueError("There is no later example date available today. Open an existing night instead.")
    identity = 11
    while str(identity) in {night["recording"] for night in experiment["recordings"]}:
        identity += 1
    night = deepcopy(source["recordings"][-1])
    night.update(
        recording=str(identity), date=next_date.isoformat(), rating=None,
        adherence=None, context=[], period=PERIODS[1], demo_tracking_example=True,
        notes="An invented follow-up night for practice. No EEG was analysed.",
    )
    experiment["recordings"].append(night)
    invalidate_decision(experiment, "An invented follow-up night was added.")
    experiment["phase"] = "changed"
    return night


def advance_after_save(page):
    """Advance only after the app's real check-in or decision save succeeds."""
    if not st.session_state.get("demo"):
        return page
    step = st.session_state.get("demo_step")
    experiment = active_experiment(st.session_state.demo_workspace)
    source = active_experiment(st.session_state.demo_source)
    if not experiment or experiment["id"] != source["id"]:
        return page
    # Removing a night uses the same destination as saving its check-in.
    # Return to the chooser if all starting examples were removed, rather
    # than claiming a check-in happened or leaving an impossible next step.
    if step in (2, "edit", 3, 4) and page == "Night log" and (
            not experiment or not experiment["recordings"]):
        st.session_state.demo_step = 1
        st.session_state.pop("selected_recording", None)
        st.session_state.notice = "Example night removed. Add it again to continue the practice."
        return "Add night"
    if step == 2 and page == "Night log":
        st.session_state.demo_step = "edit"
        return "Night detail"
    if step in (6, 7) and experiment.get("decision") == "Keep this routine":
        st.session_state.demo_step = 8
    return page


def complete_example_period(changed=False):
    """A repeat-safe time jump; never append a second copy of an example night."""
    source = active_experiment(st.session_state.demo_source)
    experiment = active_experiment(st.session_state.demo_workspace)
    saved = {r["recording"]: r for r in experiment["recordings"]}
    limit = 10 if changed else 5
    experiment["recordings"] = [
        deepcopy(saved.get(r["recording"], r)) for r in source["recordings"][:limit]
    ]
    # Optional night details can start the changed phase during practice.
    # Respect that deliberate edit and skip the now-redundant "start" action.
    # The normal comparison still displays the resulting actual period counts.
    st.session_state.demo_step = (
        6 if changed else 5 if experiment.get("phase") == "changed" else 4
    )


def intro(*, go):
    st.title("What does Nightjar do?")
    st.write("It helps you find out whether one small change is worth keeping. "
             "Your recordings show how you slept; your morning check-ins show how you felt.")
    st.write("**Try it with Alex:** they want to spend less time awake at night. "
             "You will log a night, try quieter evenings, then read the comparison.")
    st.caption("No file or personal details needed. All example nights are invented.")
    info_cards(list(zip(
        ("01", "02", "03"),
        ("Record normal nights", "Try one change", "See what changed"),
        ("Build a picture of your sleep before changing anything.",
         "Keep recording while you try a manageable routine.",
         "Compare several nights and decide what feels worth continuing."),
    )))


def practice_upload(*, go):
    """Teach file → participant → recording selection without pretending to analyse EEG."""
    st.title("Add your first night")
    st.write("In your own space, choose a compatible EEG feature CSV. Nightjar analyses each "
             "recording and turns it into a night in your log.")
    st.caption("For practice, use the prepared example below. No file is sent and no EEG is analysed.")
    if not st.session_state.get("demo_example_loaded"):
        with st.container(border=True, key="practice_file_action"):
            st.write("**Alex's example recording**")
            st.caption("A prepared fictional night. You do not need to download anything.")
            if st.button("Use example recording", type="primary"):
                st.session_state.demo_example_loaded = True
                st.rerun()
        return
    with st.container(key="practice_recording_selection"):
        st.success("Example recording ready.")
        st.selectbox("Participant", ["Alex (example)"], key="practice_participant",
                     help="An export may contain several people. Choose one; their nights stay in a separate space.")
        st.multiselect("Recordings to add", ["Night 1"], default=["Night 1"], key="practice_recordings")
        if st.button("Add selected night", type="primary", disabled=not st.session_state.practice_recordings):
            record = deepcopy(active_experiment(st.session_state.demo_source)["recordings"][0])
            record["rating"] = None
            experiment = active_experiment(st.session_state.demo_workspace)
            experiment["recordings"] = [record]
            st.session_state.selected_recording = record["recording"]
            st.session_state.demo_step = 2
            go("Night detail")


def attach_practice_plan(workspace, experiment):
    """Attach the normal newly saved plan to the prepared fictional nights."""
    source_id = active_experiment(st.session_state.demo_source)["id"]
    # Replace the empty template, keeping its identity for resume and time jumps.
    workspace["experiments"] = [item for item in workspace["experiments"] if item["id"] != source_id]
    experiment["id"] = source_id
    workspace["active_experiment"] = source_id
    st.session_state.demo_step = "planned"


def _set_practice_reveal(token):
    """Switch the guide before the page renders, retaining unsaved widget edits."""
    st.session_state.demo_ready_token = token


def _explain_then_reveal(step, title, explanation, target, *, next_action):
    """Pause at a readable explanation, then reveal and focus the actual control."""
    token = f"{step}:{bool(st.session_state.get('demo_example_loaded'))}"
    ready = st.session_state.get("demo_ready_token") == token
    st.session_state.demo_focus = {
        "mode": "act" if ready else "explain", "token": token, "target": target,
    }
    html(f'<h3 id="practice-heading" tabindex="-1">{title}</h3>')
    st.write(next_action if ready else explanation)
    if not ready:
        st.button("Show me", type="primary", key="guide_go",
                  on_click=_set_practice_reveal, args=(token,))
    else:
        # A callback lets all lower-page widgets render on this pass. An early
        # st.rerun here would discard their unsaved values during cleanup.
        st.button("Read this step again", type="tertiary", key="guide_reread",
                  on_click=_set_practice_reveal, args=(None,))
    return ready


def guidance(*, go):
    # Reset on every render, including detours, skip and exit. The browser
    # removes dimming and keyboard restrictions whenever this value is None.
    st.session_state.demo_focus = None
    if not st.session_state.get("demo"):
        return
    step = st.session_state.get("demo_step")
    if step is None:
        return
    experiment = active_experiment(st.session_state.demo_workspace)
    source = active_experiment(st.session_state.demo_source)
    original = next((item for item in st.session_state.demo_workspace["experiments"]
                     if item["id"] == source["id"]), None)
    # A free-navigation visit to Settings may open a different example routine.
    # Resume the original practice explicitly; never put its generated nights
    # into a newly chosen routine.
    different_routine = not experiment or experiment["id"] != source["id"]
    if not different_routine and step == 4 and experiment.get("phase") == "changed":
        st.session_state.demo_step = step = 5
    if step == "planned" and st.session_state.page == "Add night":
        st.session_state.demo_step = step = 1
    number = {0: 1, "routine": 2, "planned": 2, 1: 3, 2: 4, "edit": 5, 3: 6, 4: 6, 5: 7, 6: 8, "sleep": 9, 7: 10, 8: 10}[step]
    with st.container(key="guided_demo", border=True):
        with st.container(key="guide_heading"):
            label, skip = st.columns([3, 2], vertical_alignment="center")
            label.caption(f"GUIDED PRACTICE · {number} OF 10")
            if skip.button("Skip intro and see Alex's status", key="tour_skip",
                           type="secondary", width="stretch"):
                show_completed_example()
                go("Today")
        expected = PRACTICE_PAGES[step]
        if different_routine:
            st.write("Practice follows Alex's original routine. Return to it to continue; "
                     "the other example routine will stay in history.")
            if original is not None:
                if st.button("Resume practice", type="primary"):
                    st.session_state.demo_workspace["active_experiment"] = original["id"]
                    go(expected)
            elif st.button("Restart practice", type="primary"):
                start_practice()
                go("Demo guide")
            return
        allowed_detail = (step == "edit" and st.session_state.page == "Night options") or (
            step == "sleep" and st.session_state.page == "Sleep stages")
        if st.session_state.page != expected and not allowed_detail:
            st.write("Your practice progress is kept. Return to the next action when you're ready.")
            if st.button("Resume practice", type="primary"):
                go(expected)
            return
        if step in (6, "sleep", 7) and (
                not count_complete_nights(experiment, PERIODS[0])
                or not count_complete_nights(experiment, PERIODS[1])):
            st.write("The comparison needs example nights before and with the change.")
            st.caption("Restore the prepared ten-night comparison to continue. "
                       "This replaces edits to the fictional nights; personal data is untouched.")
            if st.button("Restore example comparison", type="primary"):
                show_completed_example()
                st.session_state.demo_step = 6
                go("Today")
            return
        if step == 0:
            st.session_state.demo_focus = {"mode": "explain", "token": "intro", "target": ""}
            html('<h3 id="practice-heading" tabindex="-1">Meet Alex</h3>')
            st.write("Alex often finishes a busy day answering messages right up to bedtime. "
                     "They notice stretches awake during the night and wonder whether quieter evenings "
                     "would make a difference. They already have an EEG recorder, but the numbers alone "
                     "have not helped them decide what to change.")
            st.write("Help Alex choose one routine, log their nights, and decide what feels worth keeping.")
            st.caption("About three minutes. Alex and all example nights are fictional. No EEG is analysed.")
            if st.button("Start practice", type="primary"):
                st.session_state.demo_step = "routine"
                go("Choose routine")
        elif step == "routine":
            selected = st.session_state.get("demo_chosen_habit")
            if selected is None:
                _explain_then_reveal(
                    step, "Choose one change to explore",
                    "These are the same four choices you will see in your own space. Alex wants to try "
                    "quieter evenings. Open **A calmer last hour** using **Explore this routine**.",
                    ".st-key-habit_option_wind_down",
                    next_action="Choose **Explore this routine** on the **A calmer last hour** card.")
            elif selected == "wind_down":
                _explain_then_reveal(
                    "routine_plan", "Save the plan before logging nights",
                    "This is the same plan screen you will use yourself. You can make the change specific, "
                    "then press **Save plan and go to Today**. Alex will record normal nights first.",
                    ".st-key-routine_plan",
                    next_action="Review the plan, optionally make it specific, then **Save plan and go to Today**.")
            else:
                _explain_then_reveal(
                    "routine_other", "You can explore all four choices",
                    "This prepared story follows Alex's calmer evenings. Use **Choose a different routine**, "
                    "then open **A calmer last hour** to continue. In your own space, any of the four can be saved.",
                    ".st-key-routine_choose_again",
                    next_action="Use **Choose a different routine**, then explore **A calmer last hour**.")
        elif step == "planned":
            _explain_then_reveal(
                step, "Your saved plan starts on Today",
                "Today is your home base. The plan is saved, but Alex has not changed anything yet. "
                "Use **Log a night** to add the first normal night.",
                ".st-key-dashboard_add",
                next_action="Press **Log a night** at the top of Today to add Alex's first recording.")
        elif step == 1:
            if not st.session_state.get("demo_example_loaded"):
                ready = _explain_then_reveal(
                    step, "Start with a recording",
                    "Usually, you upload your recorder's compatible feature CSV. "
                    "For practice, press **Use example recording** in the highlighted box.",
                    ".st-key-practice_file_action",
                    next_action="Press **Use example recording** in the highlighted box.")
            else:
                ready = _explain_then_reveal(
                    step, "Choose whose night to add",
                    "An export can contain several people and nights. Alex and Night 1 are selected. "
                    "Press **Add selected night** to put it in the log.",
                    ".st-key-practice_recording_selection",
                    next_action="Alex and Night 1 are selected. Press **Add selected night**.")
        elif step == 2:
            _explain_then_reveal(
                step, "Add the part a recording cannot tell us",
                "How did the morning feel? Try **2 out of 5**, or leave it unrecorded, "
                "then press **Save check-in**. Alex's example date is already filled in.",
                ".st-key-tour_night_checkin",
                next_action="Choose an optional restfulness rating, then press **Save check-in**.")
        elif step == "edit":
            if not experiment["recordings"]:
                st.session_state.demo_step = 1
                go("Add night")
            if st.session_state.page == "Night options":
                _explain_then_reveal(
                    "edit_options", "The extra details live here",
                    "Correct which part of the routine a night belongs to, add a note, or flag something unusual. "
                    "These details are optional. Unusual nights stay in the main comparison.",
                    ".st-key-page_Night_options",
                    next_action="Explore the options, then **Save night details**, or use **Back to night**.")
            else:
                # Returning from the optional editor should offer Continue,
                # not replay the explanation the visitor just acted on.
                loaded = bool(st.session_state.get("demo_example_loaded"))
                if st.session_state.get("demo_ready_token") == f"edit_options:{loaded}":
                    st.session_state.demo_ready_token = f"edit:{loaded}"
                ready = _explain_then_reveal(
                    step, "Need to change the details of a night?",
                    "**Edit night details** is where you can correct the routine period, note whether you followed "
                    "the change, or record something unusual. You can revisit it later from the Night log.",
                    ".st-key-tour_edit_night",
                    next_action="You can open **Edit night details** now, or continue to the dashboard.")
                if ready and st.button("Continue to my dashboard", type="primary"):
                    st.session_state.demo_step = 3
                    go("Today")
        elif step == 3:
            ready = _explain_then_reveal(
                step, "Your night now appears on Today",
                "The dashboard updates from your night log automatically. "
                "This first night starts Alex's usual-routine picture. In real life, keep logging each morning.",
                ".st-key-tour_dashboard_insights",
                next_action="See the first night below, then **add four more example nights** to continue.")
            if ready and st.button("Add four more example nights", type="primary"):
                complete_example_period()
                go("Today")
        elif step == 4:
            usual = count_complete_nights(experiment, PERIODS[0])
            if usual < 5:
                st.write(f"**{usual} starting example nights remain.** Restore the missing "
                         "invented nights to continue this part of the practice.")
                st.caption("Your edits to the remaining nights are kept.")
                if st.button("Restore starting example nights", type="primary"):
                    complete_example_period()
                    go("Today")
                return
            _explain_then_reveal(
                step, "Now try the change",
                "Five starting nights give Alex a picture to compare with. "
                "Press **Start my change tonight** to begin a calmer last hour before bed.",
                ".st-key-tour_start_change",
                next_action="Press **Start my change tonight** in the highlighted section.")
        elif step == 5:
            ready = _explain_then_reveal(
                step, "Keep logging while you try it",
                "Alex's next nights count as **With the change**. You would add a recording and "
                "a check-in each morning. Here, jump ahead with five invented nights.",
                ".st-key-tour_add_changed",
                next_action="Press **Add five example nights with the change** to see the comparison.")
            if ready and st.button("Add five example nights with the change", type="primary",
                                   key="tour_add_changed"):
                complete_example_period(changed=True)
                go("Today")
        elif step == 6:
            ready = _explain_then_reveal(
                step, "Read the pattern, not just one night",
                "Compare the average wake time before and with the change. "
                "Look at the night-by-night pattern and morning ratings too. "
                "One unusual night remains in the comparison.",
                ".st-key-tour_dashboard_insights",
                next_action="Read the comparison, then **Explore Alex's sleep details** to see the other measurements.")
            if ready and st.button("Explore Alex's sleep details", type="primary"):
                st.session_state.demo_step = "sleep"
                go("Today")
        elif step == "sleep":
            if st.session_state.page == "Sleep stages":
                ready = _explain_then_reveal(
                    "sleep_detail", "See what happened inside one night",
                    "These cards show estimated deep sleep, REM sleep and time from first sleep to first deep sleep. "
                    "The timeline below shows when stages occurred. This is one night's detail, not the before-and-after comparison.",
                    ".st-key-sleep_stage_metrics",
                    next_action="Read the cards and timeline below, then **Review Alex's routine** to finish the practice.")
                if ready and st.button("Review Alex's routine", type="primary"):
                    st.session_state.demo_step = 7
                    go("Routine progress")
            else:
                _explain_then_reveal(
                    step, "Your dashboard also shows sleep details",
                    "Inside your latest night shows deep sleep, REM sleep and time to first deep sleep. "
                    "You can find these here every morning. Press **View sleep details** to open the stage timeline.",
                    ".st-key-dashboard_sleep_details",
                    next_action="Press **View sleep details** below the three cards.")
        elif step == 7:
            _explain_then_reveal(
                step, "Save what feels worth keeping",
                "For this example, press **Keep this routine** to save Alex's choice. "
                "With your own nights, you can keep logging if the pattern is not yet clear.",
                ".st-key-tour_keep_routine",
                next_action="Press **Keep this routine** to keep Alex's result in the example history.")
        else:
            st.session_state.demo_focus = {"mode": "explain", "token": "complete", "target": ""}
            st.success("Practice complete. Alex's choice and comparison are in the example's routine history.")
            st.write("From the dashboard, you can keep tracking this routine, try another change, "
                     "or revisit the saved result in history.")
            st.caption(saving_notice() if session_mode() else "This example lasts for this session. In your own space, nights and choices save automatically.")
            if st.button("Explore Alex's dashboard", type="primary"):
                st.session_state.demo_step = None
                go("Today")
