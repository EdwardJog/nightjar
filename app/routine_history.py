"""Saved comparison summaries and history views that do not switch routines."""
from copy import deepcopy
from datetime import datetime, timezone

import streamlit as st

from app.experiments import RATING, nightly_table
from app.insights import describe_experiment
from app.presentation import OUTCOME_NAMES, comparison_chart, metric_cards, outcome_value


def keep_routine(experiment):
    """Capture the evidence behind a choice; later nights cannot rewrite it."""
    if experiment.get("decision") == "Keep this routine" and experiment.get("saved_comparison"):
        return
    insight = describe_experiment(experiment)
    primary = insight["primary"]
    if not primary["usual_count"] or not primary["changed_count"]:
        raise ValueError("Add a dated night with your chosen measure to both periods before keeping a routine.")
    experiment["saved_comparison"] = {
        "saved_on": datetime.now(timezone.utc).isoformat(),
        "outcome": experiment["outcome"],
        "headline": insight["headline"],
        "primary": deepcopy(primary),
        "model_fingerprints": sorted({
            record["model_fingerprint"] for record in experiment["recordings"]
            if record.get("model_fingerprint")
        }),
    }
    experiment.update(decision="Keep this routine", phase="complete")


def comparison_cards(primary, outcome):
    """Use the same compact metrics for current and saved comparisons."""
    values = [
        ("Before the change", outcome_value(primary["usual_mean"], outcome),
         f"{primary['usual_count']} nights"),
        ("With the change", outcome_value(primary["changed_mean"], outcome),
         f"{primary['changed_count']} nights"),
    ]
    difference = primary["difference"]
    if difference is not None:
        values.append(("Difference", f"{difference:+.1f} " + ("points" if outcome == RATING else "min"),
                       OUTCOME_NAMES[outcome]))
    metric_cards(values)


def render_history(workspace, *, go):
    if st.button("← Back to Today", type="tertiary"):
        go("Today")
    st.caption("TODAY / ROUTINE HISTORY")
    st.title("Your routines and results")
    st.write("Your earlier routines stay here when you try another change. Opening results does not change your current routine.")
    if not workspace["experiments"]:
        st.info("Your first routine and its nights will appear here.")
        return
    for experiment in reversed(workspace["experiments"]):
        with st.container(border=True):
            current = experiment["id"] == workspace["active_experiment"]
            st.caption("CURRENT ROUTINE" if current else "EARLIER ROUTINE")
            st.subheader(experiment["title"])
            dates = sorted(record["date"] for record in experiment["recordings"] if record.get("date"))
            period = f" · {dates[0]} to {dates[-1]}" if dates else ""
            st.caption(f"{len(experiment['recordings'])} recordings{period}")
            st.write(experiment.get("decision") or (
                "New information since your last choice" if experiment.get("decision_history")
                else "Still exploring"))
            saved = experiment.get("saved_comparison")
            if saved:
                st.write(saved["headline"])
            if st.button("View results", key=f"history_view_{experiment['id']}"):
                st.session_state.history_routine_id = experiment["id"]
                go("Saved routine")


def render_saved_routine(workspace, *, go, persist):
    """Viewing past evidence is read-only; resuming it is an explicit action."""
    if st.button("← Back to routine history", type="tertiary"):
        go("Routine history")
    identity = st.session_state.get("history_routine_id")
    experiment = next((item for item in workspace["experiments"] if item["id"] == identity), None)
    if experiment is None:
        st.info("Choose a routine from your history to see its results.")
        if st.button("View routine history"):
            go("Routine history")
        return
    st.caption("TODAY / ROUTINE HISTORY / RESULTS")
    st.title(experiment["title"])
    st.write(experiment["change"])
    saved = experiment.get("saved_comparison")
    if saved:
        st.subheader("When you chose to keep it")
        st.caption("Saved on " + saved["saved_on"][:10] + ". This comparison stays as it was when you made the choice.")
        st.write(saved["headline"])
        comparison_cards(saved["primary"], saved["outcome"])
    elif experiment.get("decision"):
        st.success("Saved choice: " + experiment["decision"])
        st.caption("Only the choice was saved at the time. The results below use the nights currently in this routine.")

    st.subheader("Results from the nights saved now")
    insight = describe_experiment(experiment)
    st.write(insight["headline"])
    st.caption("New nights and edits update these results. Each eligible night counts equally.")
    comparison_cards(insight["primary"], experiment["outcome"])
    if experiment["recordings"]:
        comparison_chart(nightly_table(experiment), experiment["outcome"])
    for entry in reversed(experiment.get("decision_history", [])):
        with st.container(border=True):
            st.write("**Earlier choice: " + entry["decision"] + "**")
            st.caption(entry.get("time", "")[:10] + " · " + entry["reason"])
            previous = entry.get("comparison")
            if previous:
                st.write(previous["headline"])
                comparison_cards(previous["primary"], previous["outcome"])
    if experiment["id"] == workspace["active_experiment"]:
        if st.button("Return to my current routine", type="primary"):
            go("Today")
    else:
        st.caption("Want to add more nights to this routine? Making it current keeps your other routines in history.")
        if st.button("Make this my current routine", type="primary"):
            workspace["active_experiment"] = experiment["id"]
            draft_key = "demo_chosen_habit" if st.session_state.get("demo") else "chosen_habit"
            st.session_state.pop(draft_key, None)
            st.session_state.pop("selected_recording", None)
            persist("This is now your current routine. Your other results remain in history.", "Today")
