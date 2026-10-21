"""Nightjar: a locally saved personal sleep experiment companion."""
from datetime import date
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # The scientific stack is imported before torch.
import streamlit as st
from app.runtime import session_mode, saving_notice, delete_label, delete_notice, reset_interface
from app.inference import load_bundle, model_fingerprint
from app.experiments import (
    SLEEP, WAKE, RATING, PERIODS,
    nightly_table, stage_summary, save_experiment, restore_experiment,
    prediction_table, export_csv, render_report,
)
from app.journey import (
    GOALS, DEVICES, HABITS, make_workspace, start_experiment,
    active_experiment, count_complete_nights, night_needs_attention, invalidate_decision,
)
from app.storage import (
    load_workspace_snapshot, save_workspace, clear_workspace, StorageError, StorageConflict,
    list_saved_workspaces, activate_saved_workspace,
)
from app.insights import describe_experiment
from app.night_views import NIGHT_VIEWS, render_stage_metrics
from app.dashboard import render_dashboard_insights
from app.upload_views import render_add_night, clear_upload_selection
from app.demo_guide import (
    DEMO_VERSION, start_practice, advance_after_save, intro as demo_intro,
    practice_upload, attach_practice_plan, guidance as render_demo_guidance, add_tracking_example,
)
from app.presentation import (
    html, hero, card, metric_cards, info_cards, minutes_text, outcome_value,
    comparison_chart, OUTCOME_NAMES, open_page_at_top,
)
from app.walkthrough import render_walkthrough_focus
from app.routine_history import keep_routine, render_history, render_saved_routine
from app.model_recovery import render_model_recovery

st.set_page_config(page_title="Nightjar · A routine worth keeping", page_icon="☾",
                   layout="wide", initial_sidebar_state="collapsed")
# One style element avoids empty Streamlit blocks adding space above navigation.
html("\n".join(Path(__file__).with_name(name).read_text(encoding="utf-8")
               for name in ("theme.css", "cards.css", "walkthrough.css")))


@st.cache_resource
def cached_bundle(fingerprint):
    """Only trusted model objects are cached, never uploaded recordings."""
    return load_bundle()


def get_bundle():
    return cached_bundle(model_fingerprint())


def current_workspace():
    return st.session_state.demo_workspace if st.session_state.get("demo") else st.session_state.workspace


def go(page):
    st.session_state.page = page
    st.rerun()


def persist(message=None, page=None):
    """Save deliberate changes atomically; keep unsaved edits if a save fails."""
    pending = st.session_state.get("pending_save_action", {})
    if message is None and page is None and pending:
        message, page = pending.get("message"), pending.get("page")
    if not st.session_state.get("demo"):
        try:
            workspace = st.session_state.workspace
            revision = save_workspace(workspace, expected_revision=st.session_state.store_revision)
            workspace["revision"] = st.session_state.store_revision = revision
            st.session_state.pop("save_error", None)
            st.session_state.pop("pending_save_action", None)
        except (StorageError, OSError, ValueError) as exc:
            st.session_state.save_error = str(exc)
            st.session_state.pending_save_action = {"message": message, "page": page}
            st.rerun()
    if message:
        st.session_state.notice = message
    page = advance_after_save(page)
    if page:
        st.session_state.page = page
    st.rerun()


def initialise():
    if "workspace" not in st.session_state:
        try:
            workspace, revision = load_workspace_snapshot()
        except (StorageError, OSError) as exc:
            st.error(f"Your saved space could not be opened: {exc}")
            st.info("Your saved file has not been replaced. Check the storage location and restart.")
            st.stop()
        st.session_state.workspace = workspace
        st.session_state.store_revision = revision
        old = st.session_state.get("experiment")
        # Preserve live data when upgrading from the earlier session-only prototype.
        if workspace is None and old and old.get("recordings"):
            workspace = make_workspace("", DEVICES[0], "Make more room for sleep")
            old.update(id=uuid4().hex, habit_id=None, phase="usual", decision=None)
            workspace.update(experiments=[old], active_experiment=old["id"], subject=old["subject"])
            st.session_state.workspace = workspace
            persist("Your earlier experiment has been kept in your new space.")
    st.session_state.setdefault("page", "Welcome")
    st.session_state.page = {"Experiment": "Routine progress", "Nights": "Night log"}.get(
        st.session_state.page, st.session_state.page)
    if st.session_state.get("demo") and st.session_state.get("demo_guide_version") != DEMO_VERSION:
        start_practice()
        st.session_state.page = "Demo guide"


def verify_saved_model(workspace):
    """Recheck the small artifact hashes even if a browser stays open during an update."""
    if workspace is None or st.session_state.get("demo"):
        return
    try:
        fingerprint = model_fingerprint()
    except (OSError, ValueError) as exc:
        st.error(f"Check the saved model files before opening your results: {exc}")
        render_model_recovery(workspace, go=go)
        st.stop()
    stale = False
    for experiment in workspace["experiments"]:
        for record in experiment["recordings"]:
            if record.get("stages") and record.get("model_fingerprint") != fingerprint:
                record.update(stages=None, quality=None, model_fingerprint=None)
                invalidate_decision(experiment, "The saved model changed.")
                stale = True
    if stale:
        persist("The saved model changed. Analyse your nights again before comparing.")


def begin_demo():
    start_practice()
    go("Demo guide")


def leave_demo(start_setup=False):
    st.session_state.demo = False
    st.session_state.pop("demo_step", None)
    if start_setup and st.session_state.workspace is None:
        st.session_state.setup_step = 1
        go("Setup")
    if start_setup:
        go("Today")
    go("Welcome")


def header(workspace):
    page = st.session_state.page
    with st.container(key="topbar"):
        brand, navigation, options = st.columns([2.1, 4.8, 1.3], vertical_alignment="center")
        with brand:
            html('<div class="brand"><span>☾</span> nightjar</div>')
        if workspace is not None:
            night_pages = ("Night log", "Night detail", "Night options", "Sleep stages", "Add night")
            with navigation:
                for column, destination in zip(st.columns(2), ("Today", "Night log")):
                    active = page in night_pages if destination == "Night log" else page not in (*night_pages, "Settings")
                    if column.button(destination, key=f"nav_{destination}", width="stretch",
                                     type="primary" if active else "secondary"):
                        go(destination)
            with options:
                if st.button("Settings", key="nav_settings", width="stretch", type="tertiary"):
                    go("Settings")
    with st.container(key="session_status"):
        if st.session_state.get("demo"):
            if st.session_state.get("demo_step") is None:
                label, replay, leave = st.columns([5, 1.4, 1.1], vertical_alignment="center")
                if replay.button("Replay practice", width="stretch"):
                    begin_demo()
            else:
                label, leave = st.columns([6.4, 1.1], vertical_alignment="center")
            label.caption("DEMO · Alex's invented nights. No EEG was analysed. Your saved data is untouched.")
            if leave.button("Exit demo", width="stretch"):
                leave_demo()
        elif workspace:
            if st.session_state.get("save_error"):
                st.error("Not saved yet. Your edits are still in this tab. " + st.session_state.save_error)
                st.caption("Another tab may have changed this space. Reloading uses its latest saved version.")
                a, b = st.columns(2)
                if a.button("Retry saving"):
                    persist()
                if b.button("Discard unsaved edits and reload"):
                    reset_interface()
                    st.rerun()
                st.stop()
            status = "Saved in this session" if session_mode() else "Saved on this computer"
            html(f'<div class="save-status">{status}</div>')
        if "notice" in st.session_state:
            st.toast(st.session_state.pop("notice"))


def demo_guide():
    render_demo_guidance(go=go)


def back_to_today():
    if st.button("← Back to Today", type="tertiary"):
        go("Today")


def open_record(record):
    st.session_state.selected_recording = record["recording"]
    go("Night detail")


def start_change(experiment):
    experiment["phase"] = "changed"
    if st.session_state.get("demo") and st.session_state.get("demo_step") == 4:
        source = active_experiment(st.session_state.demo_source)
        experiment["change_started_on"] = source["recordings"][5]["date"]
        st.session_state.demo_step = 5
    else:
        experiment["change_started_on"] = date.today().isoformat()
    persist("Your change has started. New nights will be compared with the nights before it.", "Today")


def welcome(workspace=None):
    left, right = st.columns([1.45, 1], gap="large", vertical_alignment="center")
    with left:
        html('<div class="overline">A sleep companion for EEG owners</div>')
        st.title("Less guessing. A routine worth keeping.")
        html('<p class="lede">Your recorder tells you how the night went. '
             'Nightjar helps you work out what to try next, and whether it is worth doing again.</p>')
        if workspace:
            name = workspace["profile"].get("name")
            location = "available in this browser session" if session_mode() else "saved on this computer"
            st.caption(f"Welcome back{', ' + name if name else ''}. Your space is {location}.")
        first, second = st.columns(2)
        if workspace:
            if first.button("Continue to my space", type="primary", width="stretch"):
                go("Today")
            if second.button("Explore the demo", width="stretch"):
                begin_demo()
        else:
            if first.button("Explore the demo", type="primary", width="stretch"):
                begin_demo()
            if second.button("Create my space", width="stretch"):
                st.session_state.setup_step = 1
                go("Setup")
        st.caption(saving_notice())
    with right:
        hero("THE QUESTION BEHIND THE NUMBERS", "Did a calmer evening make a difference?",
             "Compare several nights, see whether your mornings agree, and choose what stays.", dark=True)
        card("YOUR NEXT STEP", "One small change. Your own reference.",
             "No perfect sleep score to chase. Just a clearer way to learn from your nights.")
    st.write("")
    info_cards(list(zip(
        ("01", "02", "03"),
        ("Choose a small change", "Let your nights build a picture", "Make a decision you can revisit"),
        ("Pick a practical routine that fits your life.",
         "Compare recordings with your usual nights and how you felt.",
         "Keep, repeat or leave a routine. Your learning stays in your personal history."))))
    st.caption("This prototype accepts compatible EEG feature exports. Device sync is a future integration.")


def setup():
    step = st.session_state.get("setup_step", 1)
    st.caption(f"Your space · Step {step} of 2")
    if step == 1:
        st.title("Let's make this yours.")
        st.write("Just the details that help you get started.")
        with st.form("profile"):
            name = st.text_input("What should we call you? (optional)", max_chars=40,
                                 value=st.session_state.get("setup_name", ""), placeholder="First name or nickname")
            device = st.selectbox(
                "Where will your recordings come from?", DEVICES,
                index=DEVICES.index(st.session_state.get("setup_device", DEVICES[0])),
            )
            st.caption("All sources currently use the same compatible feature CSV. "
                       "Selecting a headband does not connect it or establish model compatibility.")
            if st.form_submit_button("Continue", type="primary"):
                st.session_state.update(setup_name=name, setup_device=device, setup_step=2)
                st.rerun()
        if st.button("Back"):
            go("Welcome")
    else:
        st.title("What would you most like to improve?")
        st.write("This chooses the main result on your dashboard and in your routine comparison.")
        goals = list(GOALS)
        goal = st.radio("Your goal", goals, label_visibility="collapsed",
                        index=goals.index(st.session_state.get("setup_goal", goals[0])))
        goal_previews = {
            RATING: ("Your morning restfulness", "Your 1–5 morning ratings will lead the comparison. "
                     "Nightjar will show whether you felt more rested with the change. Nights without a rating "
                     "stay in your log but cannot contribute to this result."),
            WAKE: ("Your estimated wake time during sleep", "Nightjar will compare minutes awake between "
                   "the first and last estimated sleep of each night. The main result will show whether "
                   "that time was lower with the change."),
            SLEEP: ("Your estimated sleep duration", "Nightjar will compare how much of each recording "
                    "was estimated as sleep. The main result will show whether you recorded more sleep "
                    "with the change; recording length will be shown as context."),
        }
        focus, explanation = goal_previews[GOALS[goal]]
        with st.container(border=True, key="goal_preview"):
            st.caption("WHAT THIS CHANGES IN NIGHTJAR")
            st.write("**" + focus + "**")
            st.write(explanation)
        st.caption("Your choice changes the comparison, not the sleep-stage predictions. "
                   "You can still see the other measures and choose a different focus for future routines in Settings.")
        if st.button("Create my space", type="primary"):
            st.session_state.workspace = make_workspace(
                st.session_state.get("setup_name", ""), st.session_state.get("setup_device", DEVICES[0]), goal)
            persist("Your space is ready.", "Today")
        if st.button("Back"):
            st.session_state.setup_goal = goal
            st.session_state.setup_step = 1
            st.rerun()
    st.caption(saving_notice() if session_mode() else "Recordings and check-ins save automatically here. This is one local space, shared by browsers on this computer. You can delete it in Settings.")


def habit_draft_key():
    """Keep personal and fictional routine drafts separate."""
    return "demo_chosen_habit" if st.session_state.get("demo") else "chosen_habit"


def choose_habit(workspace):
    st.caption("TODAY / CHOOSE A ROUTINE")
    st.title("What would you like to try?")
    st.write("Pick one small change. You will record your normal nights first, so you can see what changes later.")
    previous = active_experiment(workspace)
    if previous and previous["recordings"]:
        st.caption("Your current nights and results stay in Routine history. The new comparison starts "
                   "with fresh normal nights; routines you keep can be part of your usual routine.")
    selected = st.session_state.get(habit_draft_key())
    if selected is None:
        rows = list(HABITS.items())
        for start in (0, 2):
            for column, (key, habit) in zip(st.columns(2, gap="medium"), rows[start:start + 2]):
                with column:
                    with st.container(key=f"habit_option_{key}", border=True, height="stretch"):
                        card("A ROUTINE TO EXPLORE", habit["name"], habit["short"], habit["icon"])
                        if st.button("Explore this routine", key=f"habit_{key}", width="stretch"):
                            st.session_state[habit_draft_key()] = key
                            st.rerun()
    else:
        habit = HABITS[selected]
        with st.container(key="routine_plan"):
            hero("YOUR SMALL CHANGE", habit["name"], habit["action"])
            st.write(habit["why"])
            personal = st.text_input("Make it specific (optional)", max_chars=300,
                                     placeholder="For example: read with soft lighting from 9:30 pm")
            st.write("**First:** log five nights without changing anything.")
            st.write("**Then:** try this change for five nights. Nightjar will compare them with your earlier nights.")
            st.caption("Today will tell you when to start. Five nights is a guide, and missed nights are okay.")
            st.write(f"Your main question: **{workspace['profile']['goal']}**")
            if st.button("Save plan and go to Today", type="primary"):
                guided_plan = st.session_state.get("demo") and st.session_state.get("demo_step") == "routine"
                if guided_plan and selected != "wind_down":
                    st.info("For Alex's prepared story, choose A calmer last hour. You can explore the other routines too.")
                else:
                    previous = active_experiment(workspace)
                    if previous and previous.get("reviewed") and not previous.get("decision"):
                        previous.update(decision="Try a different routine", phase="complete")
                    experiment = start_experiment(workspace, selected, personal)
                    if guided_plan:
                        attach_practice_plan(workspace, experiment)
                    st.session_state.pop(habit_draft_key(), None)
                    persist("Your routine is saved. Begin by logging your normal nights.", "Today")
            if st.button("Choose a different routine", key="routine_choose_again"):
                st.session_state.pop(habit_draft_key(), None)
                st.rerun()
    st.caption("Based on [NIH healthy sleep habits]"
               "(https://www.nhlbi.nih.gov/health/sleep-deprivation/healthy-sleep-habits).")


def next_after_keeping(experiment, *, location):
    """A completed comparison starts another daily loop; it is not an account limit."""
    with st.container(border=True, key=f"kept_routine_{location}"):
        st.subheader("Routine saved. What would you like to do next?")
        st.write("Your choice and results are in **Routine history**. Ten nights is a starting point, "
                 "not a limit. Keep tracking this routine, or explore one new change.")
        tracking, change = st.columns(2)
        if tracking.button("Keep tracking", type="primary", width="stretch",
                           key=f"keep_tracking_{location}"):
            go("Add night")
        if change.button("Try another change", width="stretch", key=f"next_change_{location}"):
            st.session_state.pop(habit_draft_key(), None)
            go("Choose routine")
        st.caption("New nights update your current comparison. " + (
            "The result saved with your choice stays in history." if experiment.get("saved_comparison")
            else "Your earlier choice stays in history."))
        if st.button("View routine history", type="tertiary", key=f"kept_history_{location}"):
            go("Routine history")


def today(workspace):
    """A home dashboard: one next action, current routine, and a route into the log."""
    name = workspace["profile"]["name"]
    title, action = st.columns([4, 1.4], vertical_alignment="bottom")
    title.title("Today")
    title.caption(f"Your sleep at a glance{', ' + name if name else ''}.")
    experiment = active_experiment(workspace)
    if experiment is None:
        st.caption("Your focus: " + workspace["profile"]["goal"])
        hero("START HERE", "Choose a small change you'd like to try.",
             "First, record a few normal nights. Then try your change. Nightjar compares the two "
             "so you can see whether it is worth keeping.")
        if st.button("Choose a routine", type="primary"):
            go("Choose routine")
        return
    if action.button("＋ Log a night", key="dashboard_add", width="stretch"):
        go("Add night")
    incomplete = [r for r in experiment["recordings"] if night_needs_attention(experiment, r)]
    usual = count_complete_nights(experiment, PERIODS[0])
    changed = count_complete_nights(experiment, PERIODS[1])
    phase = experiment.get("phase", "usual")
    insight = describe_experiment(experiment)
    ready_to_review = changed >= 5 and usual > 0
    ready_to_start = phase == "usual" and usual >= 5
    if phase == "complete":
        next_after_keeping(experiment, location="today")
    elif ready_to_review:
        st.caption(f"Ready to review · {usual} nights before and {changed} nights with the change.")
        if st.button("See my comparison", type="primary"):
            go("Routine progress")
    elif ready_to_start:
        hero("YOUR STARTING PICTURE IS READY", "Try your change tonight.",
             experiment["change"] + " Your next nights will be compared with the ones already logged.")
        if st.button("Start my change tonight", type="primary", key="tour_start_change"):
            start_change(experiment)
    elif incomplete:
        hero("NEXT FOR YOU", "Finish adding your night.",
             "Your recording is saved. Add its date" +
             (" and how rested you felt" if experiment["outcome"] == RATING else "") +
             " so it can join your comparison.")
        if st.button("Finish my night", type="primary"):
            open_record(incomplete[0])
    elif phase == "usual":
        remaining = max(0, 5 - usual)
        hero("NEXT FOR YOU", "Log your normal nights first.",
             f"Keep sleeping as you normally do for {remaining} more "
             f"{'night' if remaining == 1 else 'nights'}, before trying “{experiment['title']}”. "
             "This gives you something to compare with later.")
        if st.button("Log a night", type="primary"):
            go("Add night")
    else:
        hero("TONIGHT", experiment["title"],
             experiment["change"] + " Record your night, then add it here in the morning.")
        if st.button("Log a night", type="primary"):
            go("Add night")
    if incomplete and (phase == "complete" or ready_to_start or ready_to_review):
        st.info(f"{len(incomplete)} saved {'night still needs' if len(incomplete) == 1 else 'nights still need'} "
                "a check-in or analysis. Your usable nights already support the next step above.")
        if st.button("Finish my night", key="finish_extra_night"):
            open_record(incomplete[0])
    if experiment.get("decision_history") and not experiment.get("decision"):
        st.caption("Your nights have changed since your last choice. That earlier choice remains in Routine history; "
                   "review the updated comparison whenever you are ready.")
    analysed = [r for r in experiment["recordings"] if r.get("stages")]
    latest = max(analysed, key=lambda r: r.get("date") or "") if analysed else None
    with st.container(key="dashboard_sleep_details"):
        st.subheader("Inside your latest night")
        if latest is not None:
            st.caption((latest.get("date") or "Undated recording") +
                       " · Estimates for this one recording, separate from your routine comparison below.")
            render_stage_metrics(latest["stages"], compact=True)
            if st.button("View sleep details", key="dashboard_sleep_link"):
                st.session_state.selected_recording = latest["recording"]
                st.session_state.sleep_details_parent = "Today"
                go("Sleep stages")
        else:
            st.write("Your first analysed recording will show deep sleep, REM sleep and time to first deep sleep here.")
    with st.container(key="tour_dashboard_insights"):
        render_dashboard_insights(experiment)
    routine, recent = st.columns(2, gap="large")
    with routine:
        with st.container(key="routine_overview", border=True, height="stretch"):
            st.caption("YOUR ROUTINE")
            st.subheader(experiment["title"])
            st.write(experiment["change"])
            if phase == "usual":
                progress_text = (f"{usual} of 5 nights saved before the change" if usual < 5
                                 else f"Starting picture complete · {usual} nights before the change")
                st.progress(min(usual, 5) / 5, text=progress_text)
                st.caption("Next: start the change, then record five more nights.")
            else:
                st.write(f"**{usual} nights before**  ·  **{changed} nights with the change**")
                if phase != "complete":
                    progress_text = (f"{changed} of 5 nights with the change" if changed < 5
                                     else f"Starting goal complete · {changed} nights with the change")
                    st.progress(min(changed, 5) / 5, text=progress_text)
                if usual and changed:
                    st.write(insight["headline"])
            st.caption("Your focus: " + workspace["profile"]["goal"]
                       if experiment["outcome"] == GOALS[workspace["profile"]["goal"]]
                       else "Your focus: " + OUTCOME_NAMES[experiment["outcome"]])
            if st.button("Open routine progress", key="open_routine", width="stretch"):
                go("Routine progress")
    with recent:
        with st.container(key="latest_night", border=True, height="stretch"):
            st.caption("LATEST NIGHT")
            if latest is not None:
                st.subheader(minutes_text(stage_summary(latest["stages"])[SLEEP]) + " estimated sleep")
                st.caption(latest.get("date") or "Add the night date to include it in your progress.")
                if latest.get("rating") is not None:
                    st.write(f"Morning restfulness: **{latest['rating']} / 5**")
                if st.button("Open latest night", width="stretch"):
                    open_record(latest)
            else:
                st.subheader("Your first night goes here.")
                st.write("Add your recording and a quick check-in. Nightjar will keep it in your Night log.")
            if st.button("View night log", type="tertiary", width="stretch"):
                go("Night log")
    if phase != "complete" and st.button("View routine history", type="tertiary", key="today_history"):
        go("Routine history")
    if st.session_state.get("demo") and st.session_state.get("demo_step") is None:
        st.caption("Ready to use your own recordings? Your saved space is separate from this demo.")
        label = "Return to my space" if st.session_state.workspace else "Create my own space"
        if st.button(label):
            leave_demo(start_setup=True)


def routine_progress(workspace):
    back_to_today()
    experiment = active_experiment(workspace)
    if experiment is None:
        choose_habit(workspace)
        return
    st.caption("TODAY / YOUR ROUTINE")
    st.title(experiment["title"])
    st.write(experiment["change"])
    st.caption("The nights in your Night log build this comparison automatically.")
    pending = [r for r in experiment["recordings"] if not r.get("stages")]
    insight = describe_experiment(experiment)
    primary, outcome = insight["primary"], experiment["outcome"]
    before, after = primary["usual_count"], primary["changed_count"]
    if pending:
        st.info("Some saved nights still need analysis. They are not included in the comparison.")
        if st.button("Analyse my saved night", type="primary"):
            open_record(pending[0])
        if not before or not after:
            return
    if not before or not after:
        ready_to_start = before >= 5 and experiment.get("phase") == "usual"
        if not before:
            hero("BUILD YOUR STARTING PICTURE", "Begin with your normal nights.",
                 "Log five nights without changing your routine. Then try the selected change "
                 "and log five more. Both sets of nights will appear here.")
        elif ready_to_start:
            hero("YOUR STARTING PICTURE IS READY", "Try your change tonight.",
                 experiment["change"] + " Your next nights will be compared with the ones already logged.")
        elif experiment.get("phase") == "usual":
            hero("BEFORE YOUR CHANGE", f"{before} normal {'night is' if before == 1 else 'nights are'} saved.",
                 "Keep logging until you have five, then Today will invite you to start your change.")
        else:
            hero("YOUR CHANGE HAS STARTED", "Log your first night with the change.",
                 experiment["change"] + " We will compare it with the nights before you started.")
        if ready_to_start:
            if st.button("Start my change tonight", type="primary"):
                start_change(experiment)
        elif st.button("Log a night", type="primary"):
            go("Add night")
        st.caption("Five nights is a starting guide. You can adjust the plan in Settings.")
        return
    experiment["reviewed"] = True
    hero("YOUR COMPARISON", insight["headline"], insight["body"], dark=True)
    cards = []
    for label, value, count in zip(
        ("Before the change", "With the change", "Difference"),
        (primary["usual_mean"], primary["changed_mean"], primary["difference"]), (before, after, None)):
        value_text = (f"{value:+.1f} " + ("points" if outcome == RATING else "min")
                      if count is None else outcome_value(value, outcome))
        cards.append((label, value_text, f"{count} {'night' if count == 1 else 'nights'}"
                      if count else OUTCOME_NAMES[outcome]))
    metric_cards(cards)
    comparison_chart(nightly_table(experiment), outcome)
    consistency = insight["consistency"]
    direction = {SLEEP: "more estimated sleep", WAKE: "less wake during sleep",
                 RATING: "higher morning ratings"}[outcome]
    with st.container(border=True):
        st.subheader("Is it a pattern?")
        st.write(f"**{consistency['count']} of {consistency['total']} nights** had {direction} "
                 "than the middle of your nights before the change.")
        if insight.get("paired_message"):
            st.write(insight["paired_message"])
        else:
            st.caption(insight["paired_note"])
        sensitivity = insight["sensitivity"]
        if sensitivity.get("headline"):
            st.caption(sensitivity["headline"])
    if experiment.get("decision"):
        next_after_keeping(experiment, location="progress")
    else:
        st.subheader("What happens next?")
        st.write("Keep logging if you want more nights to compare. If this routine feels worth continuing, "
                 "save it to your routine history.")
        more, keep = st.columns(2)
        if more.button("Keep logging nights", type="primary", width="stretch"):
            go("Add night")
        if keep.button("Keep this routine", width="stretch", key="tour_keep_routine"):
            keep_routine(experiment)
            persist("Routine saved in history. Keep tracking or try another change.", "Today")
    st.caption(insight["caveat"])
    if st.button("View comparison details", type="tertiary"):
        go("Comparison details")


def comparison_details(workspace):
    if st.button("← Back to routine progress", type="tertiary"):
        go("Routine progress")
    st.caption("TODAY / YOUR ROUTINE / DETAILS")
    st.title("What is behind the comparison?")
    experiment = active_experiment(workspace)
    if experiment is None:
        st.info("Choose a routine from Today first.")
        return
    insight = describe_experiment(experiment)
    primary, sensitivity = insight["primary"], insight["sensitivity"]
    st.subheader("Do unusual nights change the picture?")
    st.write(sensitivity["headline"])
    st.write("The main comparison keeps every assigned night. This check leaves out nights tagged as "
             "unusual and nights when you said you did not follow the change.")
    reduced = sensitivity["primary"]
    if primary["difference"] is not None and reduced["difference"] is not None:
        metric_cards([
            ("All nights", f"{primary['difference']:+.1f} {primary['unit']}", "With change minus before"),
            ("Without flagged nights", f"{reduced['difference']:+.1f} {primary['unit']}",
             f"{reduced['usual_count']} before · {reduced['changed_count']} with change"),
        ])
    st.subheader("Were recordings a similar length?")
    coverage = insight["recording_coverage"]
    st.write(coverage["sentence"])
    if coverage["difference"] is not None:
        st.caption(f"Average recorded length: {minutes_text(coverage['usual_mean'])} before; "
                   f"{minutes_text(coverage['changed_mean'])} with the change. {coverage['note']}")
    st.subheader("All measures")
    rows = [{"Measure": OUTCOME_NAMES[label], "Nights before": v["usual_count"],
             "Nights with change": v["changed_count"], "Average before": v["usual_mean"],
             "Average with change": v["changed_mean"], "Difference": v["difference"],
             "SD before": v["usual_sd"], "SD with change": v["changed_sd"]}
            for label, v in insight["outcomes"].items()]
    st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, width="stretch")
    st.caption("Sleep and wake are minutes; restfulness is a 1–5 rating. Every eligible night has equal "
               "weight. Missing values are omitted separately. SD shows variation between nights.")
    if experiment.get("decision_history"):
        st.subheader("Earlier choices")
        for entry in experiment["decision_history"]:
            st.write(f"{entry['decision']} · {entry['reason']}")


def add_night(workspace):
    if st.session_state.get("demo"):
        if st.session_state.get("demo_step") == 1:
            practice_upload(go=go)
        else:
            if st.button("← Back to Night log", type="tertiary"):
                go("Night log")
            st.title("Log a night")
            experiment = active_experiment(workspace)
            source = active_experiment(st.session_state.demo_source)
            if (experiment and experiment["id"] == source["id"]
                    and len(experiment["recordings"]) >= 10):
                st.write("Try tracking beyond the first ten nights. This adds one invented follow-up "
                         "to Alex's routine, then lets you check in as usual. No EEG is analysed.")
                existing = any(record.get("demo_tracking_example") for record in experiment["recordings"])
                label = "Open the example follow-up" if existing else "Add another example night"
                if st.button(label, type="primary"):
                    try:
                        record = add_tracking_example()
                        open_record(record)
                    except ValueError as exc:
                        st.info(str(exc))
            else:
                st.write("This example uses invented recordings. Replay the practice to add an example "
                         "night, or leave the demo to use your own file.")
            if (st.session_state.get("demo_step") is not None
                    and st.button("Replay practice", key="replay_from_upload", type="primary")):
                begin_demo()
            if st.button("Use my own recordings"):
                leave_demo(start_setup=True)
        return
    render_add_night(workspace, go=go, persist=persist, get_bundle=get_bundle)


def night_view(workspace, view):
    view(workspace, go=go, persist=persist, get_bundle=get_bundle)


def settings(workspace):
    back_to_today()
    st.title("Settings")
    st.caption("Adjust your profile and routine here. Your daily view stays simple.")
    profile, routine, data, about = st.tabs(("Profile", "Routine & history", "Data & privacy", "About"))
    with profile:
        if not st.session_state.get("demo"):
            st.subheader("Recording space")
            subject = workspace.get("subject")
            st.caption(f"Currently using participant {subject}." if subject is not None
                       else "Your participant is chosen when you add a recording.")
            try:
                spaces = list_saved_workspaces()
                if spaces:
                    chosen_space = st.selectbox(
                        "Other saved spaces", spaces,
                        format_func=lambda item: (
                            f"Participant {item['subject']} · {item['recordings']} recordings"
                            if item["subject"] is not None else "Earlier space · no participant chosen"),
                    )
                    if st.button("Open selected space"):
                        saved = activate_saved_workspace(
                            chosen_space["space_id"], expected_revision=st.session_state.store_revision)
                        st.session_state.workspace = saved
                        st.session_state.store_revision = saved["revision"]
                        clear_upload_selection()
                        st.session_state.pop("save_error", None)
                        st.session_state.pop(habit_draft_key(), None)
                        go("Today")
                st.caption("Choose another participant when uploading to create or reopen a separate space. "
                           "Each person's nights and insights stay together.")
            except StorageConflict as exc:
                st.session_state.save_error = str(exc)
                st.rerun()
            except (StorageError, OSError) as exc:
                st.error(f"Saved spaces could not be opened: {exc}")
        with st.form("edit_profile"):
            nickname = st.text_input("Name or nickname", value=workspace["profile"]["name"], max_chars=40)
            device = st.selectbox("Recording source", DEVICES, index=DEVICES.index(workspace["profile"]["device"]))
            goal = st.selectbox("Goal for future routines", list(GOALS),
                                index=list(GOALS).index(workspace["profile"]["goal"]))
            st.caption("The routine underway keeps its original goal. Recorder choices do not connect a device.")
            if st.form_submit_button("Save profile"):
                workspace["profile"].update(name=nickname.strip(), device=device, goal=goal)
                persist("Profile saved.")
    experiment = active_experiment(workspace)
    with routine:
        if experiment:
            st.subheader(experiment["title"])
            st.write(experiment["change"])
            if experiment.get("phase") == "usual":
                st.write("Normally, collect five nights before starting the change. "
                         "You can start earlier; your comparison will show the smaller number of nights.")
                if st.button("Start the change early"):
                    start_change(experiment)
            if experiment.get("change_started_on"):
                st.caption("Change started: " + experiment["change_started_on"] +
                           ". Dates on or after this are assigned to the change by default.")
            st.write("Want to try something else? Your current nights will stay in history.")
            if st.button("Choose a different routine"):
                st.session_state.pop(habit_draft_key(), None)
                go("Choose routine")
        st.subheader("Routine history")
        st.write("Your previous choices, nights and results stay here, even after you start another change.")
        if st.button("View routine history", key="settings_history"):
            go("Routine history")
    with data:
        if st.session_state.get("demo"):
            st.write("The demo cannot change or export your saved personal data.")
        else:
            st.subheader("Keep a copy" if session_mode() else "Optional copies")
            st.caption("Download a routine backup before leaving to keep your progress." if session_mode() else "Your progress already saves automatically. These files are optional.")
            if experiment:
                st.download_button("Routine backup", save_experiment(experiment), "nightjar_experiment.json", "application/json")
                nights = nightly_table(experiment)
                if not nights.empty:
                    st.download_button("Nightly summary", export_csv(nights), "nightjar_nights.csv", "text/csv")
                    st.download_button("Printable comparison", render_report(experiment, "See per-night model fingerprints"),
                                       "nightjar_comparison.html", "text/html")
                    predictions = prediction_table(experiment)
                    if not predictions.empty:
                        st.download_button("Stage predictions", export_csv(predictions), "nightjar_stages.csv", "text/csv")
            st.subheader("Restore a portable copy")
            uploaded = st.file_uploader("Earlier experiment JSON", type=["json"])
            if uploaded and st.button("Import as a separate experiment"):
                try:
                    restored = restore_experiment(uploaded.getvalue(), get_bundle().preprocessor["feature_columns"])
                    if workspace.get("subject") not in (None, restored["subject"]):
                        raise ValueError("This experiment belongs to a different person.")
                    restored["id"] = uuid4().hex
                    restored.setdefault("phase", "usual")
                    restored.setdefault("habit_id", None)
                    workspace["experiments"].append(restored)
                    workspace["active_experiment"] = restored["id"]
                    workspace["subject"] = restored["subject"]
                    persist("Imported your routine and choices. Analyse the nights again to rebuild estimates and comparisons.",
                            "Night log")
                except (ValueError, RecursionError) as exc:
                    st.error(f"Could not open this file: {exc}")
            st.divider()
            st.subheader("Delete session data" if session_mode() else "Delete local data")
            st.write(delete_notice())
            confirm = st.checkbox("Delete all profiles, recordings, experiments and decisions",
                                  help=delete_notice())
            if st.button(delete_label(), disabled=not confirm):
                try:
                    clear_workspace(expected_revision=st.session_state.store_revision)
                    reset_interface()
                    st.rerun()
                except (StorageError, OSError) as exc:
                    st.error(str(exc))
    with about:
        if st.button("Back to welcome"):
            if st.session_state.get("demo"):
                leave_demo()
            go("Welcome")
        if st.button("Explore the demo"):
            begin_demo()
        st.subheader("How Nightjar works")
        st.write("Your EEG feature export is analysed with the saved MLP-CRF. Its estimated stages become "
                 "sleep and wake measurements. Nights in the log then feed your routine comparison automatically.")
        st.caption("Complete recordings are processed offline using the fitted Part I preprocessing. "
                   "No raw EEG processing or live device connection is included.")
        st.write("Routine ideas follow [NIH healthy sleep habits]"
                 "(https://www.nhlbi.nih.gov/health/sleep-deprivation/healthy-sleep-habits). "
                 "Nightjar describes your observations; it does not diagnose conditions or prove that a habit caused a change.")



def main():
    initialise()
    workspace = current_workspace()
    page = st.session_state.page
    if session_mode() and page not in {"Welcome", "Setup"}:
        st.caption(saving_notice())
    # The introduction and demo can open before the saved model is checked.
    # Continuing into a personal space still validates all saved predictions.
    if page != "Welcome":
        verify_saved_model(workspace)
    header(None if page == "Welcome" else workspace)
    with st.container(key="demo_slot"):
        demo_guide()
    page = st.session_state.page
    # Replace the route as one block so controls from the previous screen
    # cannot linger while the new screen is rendered.
    with st.empty().container(key=f"page_{page.replace(' ', '_')}"):
        if page == "Welcome":
            welcome(workspace)
        elif page == "Setup" and workspace is None:
            setup()
        elif workspace is None:
            welcome()
        elif page == "Demo guide" and st.session_state.get("demo"):
            demo_intro(go=go)
        elif page == "Today":
            with st.container(key="dashboard"):
                today(workspace)
        elif page == "Choose routine":
            back_to_today()
            choose_habit(workspace)
        elif page == "Routine progress":
            routine_progress(workspace)
        elif page == "Comparison details":
            comparison_details(workspace)
        elif page == "Routine history":
            render_history(workspace, go=go)
        elif page == "Saved routine":
            render_saved_routine(workspace, go=go, persist=persist)
        elif page == "Add night":
            add_night(workspace)
        elif page in NIGHT_VIEWS:
            night_view(workspace, NIGHT_VIEWS[page])
        else:
            settings(workspace)
    html('<div class="footnote">Nightjar · Find a sleep routine worth keeping.<br>'
         'Sleep measurements are estimates. Your experience matters too.</div>')
    open_page_at_top((
        page,
        st.session_state.get("selected_recording") if page in NIGHT_VIEWS else None,
        st.session_state.get("setup_step") if page == "Setup" else None,
        st.session_state.get(habit_draft_key()) if page == "Choose routine" else None,
        st.session_state.get("demo_step") if st.session_state.get("demo") else None,
        st.session_state.get("history_routine_id") if page == "Saved routine" else None,
    ))
    render_walkthrough_focus()


if __name__ == "__main__":
    main()
