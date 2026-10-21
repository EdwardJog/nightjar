"""Read-only dashboard insights from the experiment's actual nights.

The dashboard brings the useful comparison forward. It does not choose a
routine, change the primary outcome, assign dates, or save anything.
"""
from datetime import date

import pandas as pd
import streamlit as st

from app.experiments import PERIODS, RATING, SLEEP, WAKE, nightly_table
from app.insights import describe_experiment, night_insight
from app.presentation import info_cards, comparison_chart, metric_card, metric_cards, outcome_value, OUTCOME_NAMES


def _night_word(count):
    return "night" if count == 1 else "nights"


def _difference_text(value, outcome):
    if value == 0:
        return "No change"
    return f"{value:+.1f} " + ("points" if outcome == RATING else "min")


def _show_period_averages(comparison, outcome):
    """Keep missing periods visible instead of showing them as zero."""
    values = (
        ("Before the change", comparison["usual_mean"], comparison["usual_count"]),
        ("With the change", comparison["changed_mean"], comparison["changed_count"]),
    )
    cards = [
        (label, outcome_value(average, outcome) if average is not None else "Still to come",
         f"{count} {_night_word(count)} · {OUTCOME_NAMES[outcome]}"
         if count else "No dated nights with this measure yet")
        for label, average, count in values
    ]
    if comparison["difference"] is not None:
        cards.append((
            "Average difference", _difference_text(comparison["difference"], outcome),
            "With the change minus before · Every night counts equally",
        ))
    metric_cards(cards)


def _show_unassigned_measurements(nights):
    """Give undated recordings useful measurements without placing them in time."""
    st.write("Your recordings are here. Add their dates to see how your nights change over time.")
    analysed = nights[nights[SLEEP].notna()]
    if analysed.empty:
        ratings = pd.to_numeric(nights[RATING], errors="coerce").dropna()
        if not ratings.empty:
            metric_card("Recorded restfulness", outcome_value(ratings.mean(), RATING),
                        f"Average of {len(ratings)} recorded morning check-ins")
        st.caption("Open a night to complete its date and analysis. No dates are inferred from recording IDs.")
        return
    cards = []
    for outcome in (SLEEP, WAKE):
        values = pd.to_numeric(analysed[outcome], errors="coerce").dropna()
        cards.append((
            OUTCOME_NAMES[outcome],
            outcome_value(values.mean(), outcome) if not values.empty else "Not available",
            f"Average across {len(values)} analysed recordings"
            if not values.empty else "Unavailable when no sleep is estimated",
        ))
    metric_cards(cards)
    st.caption("These are recording averages, not a before-and-after comparison.")


def _show_consistency_and_feeling(insight):
    """Distinguish repeated observations from a single favourable average."""
    consistency, outcome = insight["consistency"], insight["outcome"]
    tie_note = (f" {consistency['ties']} matched that value."
                if consistency["ties"] else "")
    cards = [(
        "IS IT JUST ONE NIGHT?",
        f"{consistency['count']} of {consistency['total']} nights",
        f"With the change, this many nights had {consistency['direction']} "
        f"than the middle value before the change.{tie_note}",
    )]
    paired_outcome = insight["paired_outcome"]
    if paired_outcome is not None and insight["paired_message"]:
        paired = insight["paired_comparison"]["paired"]
        difference = paired["difference"]
        if paired_outcome == RATING:
            title = (
                f"Mornings felt {abs(difference):.1f} points "
                + ("more" if difference > 0 else "less") + " restful"
                if difference else "No average change in restfulness"
            )
        else:
            title = (
                f"{abs(difference):.1f} min "
                + ("more " if difference > 0 else "less ")
                + ("wake during sleep" if paired_outcome == WAKE else "estimated sleep")
                if difference else f"No average change in {OUTCOME_NAMES[paired_outcome].lower()}"
            )
        cards.append((
            "HOW FEELINGS AND RECORDINGS COMPARE",
            title,
            insight["paired_message"],
        ))
    elif outcome == RATING:
        cards.append((
            "THE RECORDING SIDE OF THE PICTURE",
            "Your ratings are one part of the story.",
            insight["paired_note"],
        ))
    else:
        rating_counts = insight["outcomes"][RATING]
        cards.append((
            "AND HOW DID YOU FEEL?",
            "Add a morning check-in to connect the two.",
            f"You have {rating_counts['usual_count']} ratings before and "
            f"{rating_counts['changed_count']} with the change. "
            "Unrecorded ratings stay unknown. " + insight["paired_note"],
        ))
    info_cards(cards)


def _show_context_notes(insight):
    """Surface known interpretation issues without replacing the main result."""
    sensitivity = insight["sensitivity"]
    if sensitivity["excluded_count"]:
        reduced = sensitivity["primary"]
        count = sensitivity["excluded_count"]
        if reduced["difference"] is None:
            detail = "There are not yet unflagged nights with this measure in both parts to compare separately."
        else:
            detail = (
                "Setting them aside gives a difference of "
                f"{_difference_text(reduced['difference'], insight['outcome'])} "
                f"across {reduced['usual_count']} nights before and "
                f"{reduced['changed_count']} with the change."
            )
        st.caption(
            f"Context check · {count} {_night_word(count)} tagged as unusual or with the plan not followed. "
            + sensitivity["headline"] + " " + detail + " The main comparison above keeps those nights."
        )
    coverage = insight["recording_coverage"]
    if insight["outcome"] == SLEEP and coverage["difference"] not in (None, 0):
        st.caption("Recording window · " + coverage["sentence"] + " " + coverage["note"])


def _show_latest_personal_reference(experiment):
    """Use earlier usual nights only; never put a night in its own reference."""
    candidates = [record for record in experiment["recordings"]
                  if record.get("date") and record.get("stages")]
    if not candidates:
        return
    latest = max(candidates, key=lambda record: record["date"])
    personal = night_insight(experiment, latest)
    if not personal["available"]:
        return
    label = date.fromisoformat(latest["date"]).strftime("%d %b")
    st.caption(
        f"Your latest dated night, {label} · {OUTCOME_NAMES[personal['outcome']]} was "
        f"{outcome_value(personal['value'], personal['outcome'])}. "
        + personal["headline"]
        + f" This reference uses {personal['reference_count']} earlier nights before the change."
    )


def render_dashboard_insights(experiment):
    """Render key findings, a trend and interpretation context without mutation.

    Call once on Today after its primary next action and before routine/latest
    night cards. This function renders no navigation controls.
    """
    st.subheader("What your nights are showing")
    if not experiment or not experiment.get("recordings"):
        st.write("Your first recording will show estimated sleep and wake time. "
                 "A few dated nights build a reference that belongs to you.")
        return
    insight = describe_experiment(experiment)
    nights = nightly_table(experiment).drop_duplicates(["Subject_ID", "Recording_ID"])
    eligible = nights[nights.Date.notna() & nights.Period.isin(PERIODS)].copy()
    if eligible.empty:
        _show_unassigned_measurements(nights)
        return

    outcome = experiment["outcome"]
    comparison = insight["primary"]
    count = comparison["usual_count"] + comparison["changed_count"]
    if count:
        st.write(f"**{insight['headline']}**")
        st.caption(insight["body"])
    else:
        # Keep the chosen question intact while showing the measurements that
        # exist. This is labelled as a fallback view, not a new chosen outcome.
        alternatives = [item for item in (SLEEP, WAKE, RATING)
                        if insight["outcomes"][item]["usual_count"]
                        + insight["outcomes"][item]["changed_count"]]
        if not alternatives:
            st.write("Your night dates are saved. Their sleep analysis or morning check-ins "
                     "will add the first measurements here.")
            return
        if outcome == RATING:
            st.write("**Your sleep estimates are ready. How did those mornings feel?**")
            st.caption("Your main question is restfulness. Add a morning rating to dated nights "
                       "to answer it; the view below shows your estimated sleep.")
        elif outcome == WAKE:
            st.write("**Your other measurements are available.**")
            if insight["outcomes"][SLEEP]["usual_count"] + insight["outcomes"][SLEEP]["changed_count"]:
                st.caption("Wake during sleep is unavailable where no sleep was estimated. "
                           "Your chosen question stays the same.")
            else:
                st.caption("Analyse your recordings to add wake estimates. "
                           "For now, the view below shows your recorded morning restfulness.")
        else:
            st.write("**Your morning check-ins are available.**")
            st.caption("Complete the sleep analysis to add your main measure.")
        outcome = alternatives[0]
        comparison = insight["outcomes"][outcome]
        count = comparison["usual_count"] + comparison["changed_count"]

    _show_period_averages(comparison, outcome)
    if count >= 2:
        comparison_chart(nights, outcome)
    else:
        st.caption("Your next dated night adds another point to the picture.")
    if insight["primary"]["difference"] is not None:
        _show_consistency_and_feeling(insight)
        _show_context_notes(insight)
    _show_latest_personal_reference(experiment)
    if insight["excluded_undated"]:
        count = insight["excluded_undated"]
        st.caption(f"{count} {_night_word(count)} still need a date before joining the comparison.")
