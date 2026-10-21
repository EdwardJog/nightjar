"""A browsable night log with a small check-in and separate optional details.

Navigation and saving are supplied by the application shell, so these views
cannot accidentally create a second workspace or persistence path.
"""
from datetime import date

import streamlit as st

from app.experiments import (
    PERIODS, RATING, SLEEP, WAKE, record_frame, set_diary, stage_summary, stage_detail_summary,
)
from app.inference import predict_frame
from app.insights import night_insight
from app.journey import active_experiment, CONTEXTS, invalidate_decision, set_night_context
from app.presentation import (
    metric_cards, minutes_text, outcome_value, OUTCOME_NAMES, sleep_ribbon, timeline_chart,
)


PERIOD_NAMES = {PERIODS[0]: "Before the change", PERIODS[1]: "With the change"}


def _date_label(value):
    return date.fromisoformat(value).strftime("%a, %d %b %Y") if value else "Date to add"


def _routine_caption(experiment):
    if experiment is not None:
        st.caption(f"Your routine · {experiment['title']}")


def _selected_night(workspace, go):
    """Resolve the selected recording inside the active experiment only."""
    experiment = active_experiment(workspace)
    selected = st.session_state.get("selected_recording")
    record = next((item for item in experiment["recordings"]
                   if item["recording"] == selected), None) if experiment else None
    if record is None:
        st.info("Choose a night from your log.")
        if st.button("Back to night log"):
            go("Night log")
    return experiment, record


def _suggested_period(experiment, record, night_date):
    """Keep explicit membership; suggest new membership from date or phase."""
    if record.get("period") in PERIODS:
        return record["period"]
    started = experiment.get("change_started_on")
    if started and night_date is not None:
        # A phase-start date is user supplied. Recording IDs are never dates.
        boundary = date.fromisoformat(str(started))
        return PERIODS[1] if night_date >= boundary else PERIODS[0]
    return PERIODS[1] if experiment.get("phase") in ("changed", "complete") else PERIODS[0]


def _advance_if_changed(experiment, period):
    if period == PERIODS[1] and experiment.get("phase") == "usual":
        experiment["phase"] = "changed"


def _analysis_action(record, experiment, *, persist, get_bundle):
    """Run trusted inference when imported or invalidated results need rebuilding."""
    if record.get("stages"):
        return
    if st.session_state.get("demo"):
        st.info("This example has no stage timeline to display.")
        return
    st.info("This recording needs analysis before its sleep estimates are available.")
    if st.button("Analyse this night", type="primary"):
        try:
            with st.spinner("Reading your night..."):
                bundle = get_bundle()
                predictions, quality = predict_frame(record_frame(record), bundle)
            record.update(
                stages=predictions["Predicted stage"].tolist(),
                quality=quality.iloc[0].to_dict(),
                model_fingerprint=bundle.fingerprint,
            )
            invalidate_decision(experiment, "A recording was reanalysed.")
            persist("Night analysed and saved.", page="Night detail")
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(f"We could not analyse this recording: {exc}")


def render_night_log(workspace, *, go, persist, get_bundle):
    """Let people open nights directly, without an ID dropdown or a survey."""
    experiment = active_experiment(workspace)
    heading, action = st.columns([4, 1], vertical_alignment="bottom")
    heading.title("Night log")
    if action.button("Add a night", type="primary", width="stretch"):
        go("Add night")
    _routine_caption(experiment)
    if experiment is None:
        st.write("Choose a routine, then bring in your first recording.")
        if st.button("Go to Today"):
            go("Today")
        return
    if not experiment["recordings"]:
        st.write("Your nights will appear here. Add a recording to start your personal history.")
        return
    st.caption("These nights update your routine progress on Today. Open one for its sleep estimates and check-in.")
    # Put undated uploads first so the next action is visible; dated nights
    # then appear newest first. No invented dates fill the gaps.
    records = sorted(
        experiment["recordings"],
        key=lambda item: (not bool(item.get("date")), item.get("date") or ""),
        reverse=True,
    )
    for record in records:
        period = PERIOD_NAMES.get(record.get("period"), "Routine to confirm")
        if record.get("stages"):
            values = stage_summary(record["stages"])
            summary = f"{minutes_text(values[SLEEP])} estimated sleep"
            if values[WAKE] is not None:
                summary += f" · {minutes_text(values[WAKE])} awake during sleep"
        else:
            summary = "Analysis needed"
        rating = record.get("rating")
        if rating is not None:
            summary += f" · Restfulness {rating}/5"
        status = ("Add the date" if not record.get("date") else
                  "Save your check-in" if record.get("period") not in PERIODS else
                  "Add your restfulness check-in"
                  if experiment["outcome"] == RATING and rating is None else "")
        title = _date_label(record.get("date"))
        if not record.get("date"):
            title += f" · Recording {record['recording']}"
        label = f"**{title}**\n\n{summary}\n\n{period}" + (f" · {status}" if status else "")
        if st.button(label, key=f"night_card_{experiment['id']}_{record['subject']}_{record['recording']}",
                     width="stretch"):
            st.session_state.selected_recording = record["recording"]
            go("Night detail")


def render_night_detail(workspace, *, go, persist, get_bundle):
    """Show one night and only the two everyday check-in fields."""
    experiment, record = _selected_night(workspace, go)
    if record is None:
        return
    if st.button("Back to night log"):
        go("Night log")
    st.title(_date_label(record.get("date")) if record.get("date") else "Your new night")
    _routine_caption(experiment)
    if record.get("stages"):
        values = stage_summary(record["stages"])
        cards = []
        for measure in (SLEEP, WAKE, RATING):
            value = record.get("rating") if measure == RATING else values[measure]
            cards.append((
                OUTCOME_NAMES[measure], outcome_value(value, measure),
                "Your morning check-in" if measure == RATING else (
                    "Invented example measurement" if st.session_state.get("demo")
                    else "Estimated from your recording"),
            ))
        metric_cards(cards)
        st.caption("Estimated deep sleep: " + minutes_text(values["N3 (min)"]) +
                   " · REM sleep: " + minutes_text(values["REM (min)"]) +
                   ". Open Sleep stages below for timing and the full picture.")
        if values[WAKE] is None:
            st.caption("No sleep was estimated, so wake during sleep is unavailable for this night.")
        insight = night_insight(experiment, record)
        if insight["available"]:
            st.write(f"**{OUTCOME_NAMES[experiment['outcome']]}: {insight['headline']}**")
            st.caption(insight["body"])
    else:
        _analysis_action(record, experiment, persist=persist, get_bundle=get_bundle)

    with st.container(key="tour_night_checkin"):
        st.subheader("How was your morning?")
        # Outside a form so date edits update the routine suggestion before saving.
        widget_suffix = f"{experiment['id']}_{record['recording']}"
        night_date = st.date_input(
            "Night date", value=date.fromisoformat(record["date"]) if record.get("date") else None,
            max_value=date.today(), format="DD/MM/YYYY", key=f"night_date_{widget_suffix}",
            disabled=bool(st.session_state.get("demo")) and st.session_state.get("demo_step") == 2,
        )
        rating = st.select_slider(
            "How rested did you feel? (optional)", options=["Not recorded", 1, 2, 3, 4, 5],
            value=record.get("rating") if record.get("rating") is not None else "Not recorded",
            key=f"night_rating_{widget_suffix}",
        )
        st.caption("1 · Not at all rested     3 · In between     5 · Very rested")
        period = _suggested_period(experiment, record, night_date)
        st.caption(f"Counts as: **{PERIOD_NAMES[period]}**. You can change this in Edit night details.")
        if experiment["outcome"] == RATING:
            st.caption("A rating lets this night join your restfulness comparison. You can leave it unrecorded.")
        if st.button("Save check-in", type="primary"):
            if night_date is None:
                st.error("Choose when this night happened. Recording IDs do not tell us the date.")
            elif any(other is not record and other.get("date") == night_date.isoformat()
                     for other in experiment["recordings"]):
                st.error("Another recording already uses this date. Keep one complete recording per night.")
            else:
                before = (record.get("date"), record.get("period"), record.get("rating"))
                set_diary(record, night_date, period, None if rating == "Not recorded" else rating,
                          record.get("notes", ""))
                if before != (record["date"], record["period"], record["rating"]):
                    invalidate_decision(experiment, "A check-in was edited.")
                _advance_if_changed(experiment, period)
                persist("Check-in saved.", page="Night log")
    details, stages = st.columns(2)
    if details.button("Edit night details", width="stretch", key="tour_edit_night"):
        go("Night options")
    if record.get("stages") and stages.button("Sleep stages", width="stretch"):
        st.session_state.sleep_details_parent = "Night detail"
        go("Sleep stages")


def render_night_options(workspace, *, go, persist, get_bundle):
    """Put uncommon edits and optional context behind one clear drilldown."""
    experiment, record = _selected_night(workspace, go)
    if record is None:
        return
    if st.button("Back to night"):
        go("Night detail")
    st.title("Night details")
    _routine_caption(experiment)
    st.caption(_date_label(record.get("date")))
    night_date = date.fromisoformat(record["date"]) if record.get("date") else None
    initial_period = _suggested_period(experiment, record, night_date)
    # Membership is editable here, rather than an extra daily question.
    period_name = st.radio(
        "Which part of your routine?", list(PERIOD_NAMES.values()),
        index=PERIODS.index(initial_period), horizontal=True,
        key=f"night_period_{experiment['id']}_{record['recording']}",
    )
    period = next(key for key, label in PERIOD_NAMES.items() if label == period_name)
    st.subheader("Anything else to remember?")
    st.caption("These details are optional. Unusual nights stay in the main comparison.")
    adherence = None
    if period == PERIODS[1]:
        followed = st.radio(
            "Did you follow your plan?", ("Not recorded", "Yes", "No"),
            index={None: 0, True: 1, False: 2}[record.get("adherence")], horizontal=True,
            key=f"night_adherence_{experiment['id']}_{record['recording']}",
        )
        adherence = {"Not recorded": None, "Yes": True, "No": False}[followed]
    context = st.multiselect(
        "Anything unusual?", CONTEXTS, default=record.get("context", []),
        key=f"night_context_{experiment['id']}_{record['recording']}",
    )
    notes = st.text_area(
        "A note for future you", value=record.get("notes", ""), max_chars=2000,
        key=f"night_note_{experiment['id']}_{record['recording']}",
    )
    if st.button("Save night details", type="primary"):
        before = (record.get("period"), record.get("adherence"), record.get("context", []))
        set_diary(record, record.get("date"), period, record.get("rating"), notes)
        set_night_context(record, context, adherence)
        after = (record["period"], record.get("adherence"), record.get("context", []))
        if before != after:
            invalidate_decision(experiment, "A night's routine or context was edited.")
        _advance_if_changed(experiment, period)
        persist("Night details saved.", page="Night detail")
    st.divider()
    st.subheader("Remove this night")
    remove = st.checkbox(
        "Remove this recording and its check-in",
        key=f"remove_night_{experiment['id']}_{record['recording']}",
    )
    if st.button("Remove night", disabled=not remove):
        experiment["recordings"].remove(record)
        invalidate_decision(experiment, "A recording was removed.")
        if not experiment["recordings"]:
            experiment["subject"] = None
        st.session_state.pop("selected_recording", None)
        persist("Night removed.", page="Night log")


def render_stage_metrics(stages, *, compact=False):
    """Use identical estimates and missing-value explanations in both views."""
    details = stage_detail_summary(stages)
    if not compact:
        st.write("A closer look at the sleep estimated within this recording.")
    metric_cards([
        ("Deep sleep", minutes_text(details["deep_minutes"]), "Total time estimated in deep sleep (N3)"),
        ("REM sleep", minutes_text(details["rem_minutes"]), "Total time estimated in REM sleep"),
        ("First deep sleep", minutes_text(details["first_deep_minutes"]),
         ("After the first estimated sleep" if details["first_deep_minutes"] is not None
          else details["first_deep_note"])),
    ])
    if compact:
        st.caption("First deep sleep is timed from the first estimated sleep, not bedtime. These measures are not targets to maximise.")
        return
    st.caption("These describe this recording, not a target to maximise. More deep sleep or faster arrival "
               "is not automatically a better night.")
    if details["first_deep_minutes"] is not None:
        st.caption(details["first_deep_note"] + " This is not the time it took to fall asleep after going to bed.")


def render_sleep_stages(workspace, *, go, persist, get_bundle):
    """Keep the stage trace available without making it part of every check-in."""
    experiment, record = _selected_night(workspace, go)
    if record is None:
        return
    parent = st.session_state.get("sleep_details_parent", "Night detail")
    if st.button("Back to Today" if parent == "Today" else "Back to night"):
        go(parent)
    st.title("Your night, in stages")
    _routine_caption(experiment)
    st.caption(_date_label(record.get("date")))
    if not record.get("stages"):
        _analysis_action(record, experiment, persist=persist, get_bundle=get_bundle)
        return
    with st.container(key="sleep_stage_metrics"):
        render_stage_metrics(record["stages"])
    sleep_ribbon(record["stages"])
    timeline_chart(record["stages"])
    st.write("Read from left to right, from the start to the end of your recording. "
             "This is an estimated stage timeline, not a raw EEG trace.")
    st.write("N1 and N2 are light sleep; N3 is deeper sleep; REM is another sleep stage. "
             "Nightjar does not set a target percentage for any stage.")
    st.caption("Learn about [sleep stages from NIH](https://www.nhlbi.nih.gov/health/sleep/stages-of-sleep).")
    st.caption(f"Recorded length: {minutes_text(len(record['stages']) * 0.5)}. "
               "Brief awakenings and stage changes may be missed.")
    if st.button("Back to night log"):
        go("Night log")


NIGHT_VIEWS = {
    "Night log": render_night_log,
    "Night detail": render_night_detail,
    "Night options": render_night_options,
    "Sleep stages": render_sleep_stages,
}
