"""Plain-language, descriptive comparisons for a personal routine experiment.

No threshold here establishes effectiveness. Three nights is only the point at
which the interface stops calling a comparison "early"; five per period is a
workflow target. Every eligible recording has equal weight.

``describe_experiment`` returns:
    status, headline, body, next_action, outcome, primary, outcomes, progress,
    consistency, sensitivity, variation, recording_coverage, feeling_disagrees,
    paired_outcome, paired_message, paired_comparison, paired_status, paired_note,
    eligible_nights, excluded_undated, duplicate_recordings, caveat.
``primary`` and each ``outcomes`` entry contain the period counts, means, sample
SDs, mean difference (changed minus usual), direction and unit. Missing numbers
are None. ``sensitivity["primary"]`` repeats these calculations after excluding
context-flagged nights or changed-routine nights marked adherence=False. The
main comparison always includes those nights.

The feelings-versus-recordings comparison uses only nights with both measures.
``paired_comparison`` contains ``primary`` and ``paired`` summaries on those
same nights, plus their period counts. It never replaces the all-night results.
``paired_status`` is unavailable, early or available; ``paired_note`` explains
the coverage. An early comparison does not establish a disagreement pattern.

``night_insight`` compares the chosen outcome only with valid usual-routine
nights dated strictly before the selected night. Its response includes the
reference count, mean and SD, selected value and difference. It never compares
a night against a baseline that includes itself.
"""

from datetime import date
from math import isfinite
from statistics import mean, median, stdev

from app.experiments import OUTCOMES, PERIODS, RATING, SLEEP, WAKE, stage_summary


WORKFLOW_NIGHTS = 5
EARLY_NIGHTS = 3
CONTEXT_TAGS = ("Travel", "Unwell", "Alcohol", "Unusual stress", "Schedule change")
_DIRECTION = {SLEEP: 1, WAKE: -1, RATING: 1}
_DIRECTION_LABEL = {
    SLEEP: "more estimated sleep",
    WAKE: "less estimated wake during sleep",
    RATING: "higher morning restfulness",
}
_OUTCOME_LABEL = {
    SLEEP: "estimated sleep",
    WAKE: "estimated wake during sleep",
    RATING: "morning restfulness",
}


def _finite_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _night_date(value):
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _prepare_nights(experiment):
    """Deduplicate by recording identity before deriving any comparison."""
    nights, seen, subjects = [], set(), set()
    duplicates = undated = 0
    for record in experiment.get("recordings", []):
        identity = (str(record.get("subject")), str(record.get("recording")))
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        subjects.add(identity[0])
        if len(subjects) > 1:
            raise ValueError("An experiment belongs to one person.")
        night_date = _night_date(record.get("date"))
        if night_date is None:
            undated += 1
        values = {SLEEP: None, WAKE: None}
        if record.get("stages"):
            values.update(stage_summary(record["stages"]))
        values[RATING] = _finite_number(record.get("rating"))
        context = [tag for tag in (record.get("context") or []) if tag in CONTEXT_TAGS]
        nights.append({
            "identity": identity, "date": night_date, "period": record.get("period"),
            "context": context, "adherence": record.get("adherence"),
            "recording_minutes": len(record["stages"]) * 0.5 if record.get("stages") else None,
            **{outcome: _finite_number(values.get(outcome)) for outcome in OUTCOMES},
        })
    return nights, undated, duplicates


def _outcome_values(nights, period, outcome):
    return [night[outcome] for night in nights
            if night["period"] == period and night[outcome] is not None]


def _compare_outcome(nights, outcome):
    result = {"unit": "rating points" if outcome == RATING else "minutes"}
    for period, prefix in zip(PERIODS, ("usual", "changed")):
        values = _outcome_values(nights, period, outcome)
        result.update({
            f"{prefix}_count": len(values),
            f"{prefix}_mean": mean(values) if values else None,
            f"{prefix}_sd": stdev(values) if len(values) > 1 else None,
        })
    difference = (result["changed_mean"] - result["usual_mean"]
                  if result["changed_mean"] is not None
                  and result["usual_mean"] is not None else None)
    result["difference"] = difference
    result["direction"] = (
        None if difference is None else
        "higher" if difference > 0 else "lower" if difference < 0 else "unchanged"
    )
    return result


def _direction(value):
    return 0 if value in (None, 0) else 1 if value > 0 else -1


def _difference_sentence(comparison, outcome):
    difference = comparison["difference"]
    if difference is None:
        return "Add a dated night in each routine to start comparing."
    if difference == 0:
        return f"No average change in {_OUTCOME_LABEL[outcome]}."
    if outcome == RATING:
        direction = "more" if difference > 0 else "less"
        return f"Mornings felt {abs(difference):.1f} points {direction} restful."
    direction = "more" if difference > 0 else "fewer"
    description = "awake during sleep" if outcome == WAKE else "of estimated sleep"
    return f"{abs(difference):.1f} {direction} minutes {description}, on average."


def _compare_feelings_with_recordings(nights, outcome):
    """Compare feelings and estimates on the same nights in each period."""
    candidates = [RATING] if outcome != RATING else [WAKE, SLEEP]
    comparisons = {}
    for candidate in candidates:
        matched = [night for night in nights
                   if night[outcome] is not None and night[candidate] is not None]
        primary = _compare_outcome(matched, outcome)
        comparisons[candidate] = {
            "primary": primary,
            "paired": _compare_outcome(matched, candidate),
            "usual_count": primary["usual_count"],
            "changed_count": primary["changed_count"],
        }
    available = [candidate for candidate in candidates
                 if comparisons[candidate]["primary"]["difference"] is not None]
    repeated = [candidate for candidate in available
                if min(comparisons[candidate]["usual_count"],
                       comparisons[candidate]["changed_count"]) >= EARLY_NIGHTS]
    paired_outcome = next(iter(repeated or available), None)
    if paired_outcome is None:
        return {
            "paired_outcome": None, "paired_comparison": None,
            "paired_status": "unavailable", "paired_message": None,
            "paired_note": (
                "This comparison needs dated nights with both a morning rating and "
                "an available sleep estimate before and with the change. "
                "Separate averages alone cannot show whether the two agree."
            ),
            "feeling_disagrees": False,
        }
    comparison = comparisons[paired_outcome]
    matched_primary, matched_pair = comparison["primary"], comparison["paired"]
    usual, changed = comparison["usual_count"], comparison["changed_count"]
    enough_nights = min(usual, changed) >= EARLY_NIGHTS
    objective = paired_outcome if outcome == RATING else outcome
    rating = matched_primary if outcome == RATING else matched_pair
    estimate = matched_pair if outcome == RATING else matched_primary
    feeling = ("more rested" if rating["difference"] > 0 else
               "less rested" if rating["difference"] < 0 else "equally rested")
    estimate_direction = ("increased" if estimate["difference"] > 0 else
                          "decreased" if estimate["difference"] < 0 else "stayed the same")
    usual_label = f"{usual} {'night' if usual == 1 else 'nights'}"
    changed_label = f"{changed} {'night' if changed == 1 else 'nights'}"
    note = (f"Uses the same {usual_label} before and {changed_label} with the change "
            "for both measures.")
    if not enough_nights:
        note += " This is an early comparison; there are fewer than three matching nights in at least one period."
    return {
        "paired_outcome": paired_outcome,
        "paired_comparison": comparison,
        "paired_status": "available" if enough_nights else "early",
        "paired_message": (
            f"On nights with both measurements, you reported feeling {feeling}, "
            f"while {_OUTCOME_LABEL[objective]} {estimate_direction}. " + note
        ),
        "paired_note": note,
        "feeling_disagrees": bool(
            enough_nights
            and _direction(rating["difference"])
            * _direction(estimate["difference"] * _DIRECTION[objective]) == -1
        ),
    }


def describe_experiment(experiment):
    """Describe the data, consistency and sensitivity without choosing a winner."""
    outcome = experiment.get("outcome", SLEEP)
    if outcome not in OUTCOMES:
        raise ValueError("Choose a supported main outcome.")
    nights, undated, duplicates = _prepare_nights(experiment)
    eligible = [night for night in nights
                if night["date"] is not None and night["period"] in PERIODS]
    outcomes = {item: _compare_outcome(eligible, item) for item in OUTCOMES}
    # Longer recordings can contain more estimated sleep simply because they
    # cover more time. Expose coverage rather than treating it as time in bed.
    recording_coverage = _compare_outcome(eligible, "recording_minutes")
    coverage_difference = recording_coverage["difference"]
    if coverage_difference is None:
        coverage_sentence = "Add an analysed, dated recording to each routine to compare recording lengths."
    elif coverage_difference == 0:
        coverage_sentence = "The recordings cover the same average length in both routines."
    else:
        coverage_direction = "more" if coverage_difference > 0 else "fewer"
        coverage_sentence = (
            f"The changed-routine recordings cover {abs(coverage_difference):.1f} "
            f"{coverage_direction} minutes on average. "
            "Keep recording start/end conditions comparable."
        )
    recording_coverage.update(
        sentence=coverage_sentence,
        note="This is recorded length, not time in bed or sleep opportunity.",
    )
    primary = outcomes[outcome]
    usual_count, changed_count = primary["usual_count"], primary["changed_count"]
    usual_values = _outcome_values(eligible, PERIODS[0], outcome)
    changed_values = _outcome_values(eligible, PERIODS[1], outcome)
    usual_median = median(usual_values) if usual_values else None
    comparisons = ([(value - usual_median) * _DIRECTION[outcome]
                    for value in changed_values] if usual_median is not None else [])
    consistency = {
        "count": sum(value > 0 for value in comparisons),
        "total": len(comparisons),
        "ties": sum(value == 0 for value in comparisons),
        "usual_median": usual_median,
        "direction": _DIRECTION_LABEL[outcome],
        "label": (f"{sum(value > 0 for value in comparisons)} of {len(comparisons)} "
                  f"changed nights had {_DIRECTION_LABEL[outcome]} "
                  "than your usual-routine median.")
                 if comparisons else "Add both routines to compare individual nights.",
    }

    # Keep all nights in the main result. This second view reveals whether the
    # direction depends on unusual circumstances, rather than selecting them out.
    retained = [night for night in eligible
                if not night["context"]
                and not (night["period"] == PERIODS[1] and night["adherence"] is False)]
    sensitivity_comparison = _compare_outcome(retained, outcome)
    before = primary["difference"]
    after = sensitivity_comparison["difference"]
    reversal = (before is not None and after is not None
                and _direction(before) * _direction(after) == -1)
    excluded_count = len(eligible) - len(retained)
    sensitivity = {
        "primary": sensitivity_comparison,
        "excluded_count": excluded_count,
        "retained_count": len(retained),
        "direction_reversal": reversal,
        "available": after is not None,
        "headline": (
            "The direction reverses when flagged nights are set aside." if reversal else
            "Both routines need unflagged nights for this second comparison."
            if excluded_count and after is None else
            "The direction is unchanged when flagged nights are set aside."
            if excluded_count and _direction(before) == _direction(after) else
            "The difference becomes zero when flagged nights are set aside."
            if excluded_count and after == 0 else
            "A difference appears when flagged nights are set aside."
            if excluded_count else "No nights have been flagged."
        ),
    }

    # Optional ratings may cover only a subset of recordings. Compare the two
    # measures on their overlap so missing check-ins cannot create agreement
    # or disagreement simply by changing which nights enter each average.
    paired_result = _compare_feelings_with_recordings(eligible, outcome)
    feeling_disagrees = paired_result["feeling_disagrees"]
    paired_message = paired_result["paired_message"]
    # A person may deliberately start the change before five usual nights.
    # Do not tell them to return to baseline merely because its guide is unmet.
    chosen_phase = experiment.get("phase")
    if chosen_phase == "complete":
        phase = "review"
    elif chosen_phase == "changed":
        phase = "change" if changed_count < WORKFLOW_NIGHTS else "review"
    else:
        phase = ("baseline" if usual_count < WORKFLOW_NIGHTS else
                 "change" if changed_count < WORKFLOW_NIGHTS else "review")
    progress = {
        "usual": usual_count, "changed": changed_count, "target": WORKFLOW_NIGHTS,
        "phase": phase,
        "remaining": (max(0, WORKFLOW_NIGHTS - usual_count) if phase == "baseline"
                      else max(0, WORKFLOW_NIGHTS - changed_count) if phase == "change" else 0),
        "note": "Five nights per routine is a practical starting plan, not proof of an effect.",
    }

    if usual_count == 0 and changed_count == 0:
        status, headline = "starting", "Start with a few nights of your usual routine."
    elif changed_count == 0:
        status, headline = "baseline", "You are learning what your usual nights look like."
    elif usual_count == 0:
        status, headline = "baseline", "Your changed nights need a usual-routine comparison."
    elif min(usual_count, changed_count) < EARLY_NIGHTS:
        status, headline = "early", _difference_sentence(primary, outcome)
    elif reversal or feeling_disagrees:
        status, headline = "mixed", "There is more than one story in these nights."
    else:
        status = "no_change" if before == 0 else "pattern"
        headline = _difference_sentence(primary, outcome)
    usual_label = f"{usual_count} {'night' if usual_count == 1 else 'nights'}"
    changed_label = f"{changed_count} {'night' if changed_count == 1 else 'nights'}"
    if usual_count and changed_count:
        body = (f"Comparing {usual_label} before the change with {changed_label} with it, "
                f"using {_OUTCOME_LABEL[outcome]}. Each night counts equally.")
    elif usual_count:
        body = (f"Your starting picture uses {usual_label} of {_OUTCOME_LABEL[outcome]}. "
                "After you start the change, its nights will appear alongside these.")
    elif changed_count:
        body = (f"You have {changed_label} with the change. "
                "Add nights from before the change to make a comparison.")
    else:
        body = "Add a dated night with this measure to begin your personal comparison."
    if status == "early":
        body += " This is an early comparison; one unusual night can move the averages."
    if status == "mixed":
        body += " " + _difference_sentence(primary, outcome)
    if feeling_disagrees:
        body += " " + paired_message
    if reversal:
        body += " The direction changes when flagged nights are set aside."
    if outcome == SLEEP and before is not None:
        body += " More recorded sleep is not automatically better; read it alongside how you feel."
    if chosen_phase == "complete":
        next_action = "Keep tracking this routine, revisit your saved decision, or explore another change."
    elif usual_count == 0 and changed_count:
        next_action = (
            "Add nights recorded before you started the change. If none are available, "
            "begin a new comparison with your usual routine."
        )
    elif phase == "baseline":
        next_action = (f"Add {progress['remaining']} more usual-routine "
                       f"{'night' if progress['remaining'] == 1 else 'nights'} with your main outcome.")
    elif phase == "change":
        next_action = (f"Keep your chosen change consistent and add {progress['remaining']} more "
                       f"changed-routine {'night' if progress['remaining'] == 1 else 'nights'}.")
    elif status == "early":
        next_action = ("Read this as an early comparison. Your usual-routine reference is short; "
                       "consider repeating the experiment before deciding what to keep.")
    elif status == "mixed":
        next_action = "Review the flagged nights and how you felt before deciding what to keep."
    else:
        next_action = "Review how you felt and whether the routine is manageable before deciding what to keep."
    spread = primary["usual_sd"]
    variation = {
        "usual_sd": spread,
        "difference_to_usual_sd": (abs(before) / spread
                                   if before is not None and spread is not None and spread > 0 else None),
        "note": "The usual-night sample SD describes spread, not confidence that the routine works.",
    }
    return {
        "status": status, "headline": headline, "body": body, "next_action": next_action,
        "outcome": outcome, "primary": primary, "outcomes": outcomes, "progress": progress,
        "consistency": consistency, "sensitivity": sensitivity, "variation": variation,
        "recording_coverage": recording_coverage,
        **paired_result, "eligible_nights": len(eligible),
        "excluded_undated": undated, "duplicate_recordings": duplicates,
        "caveat": "These are observed differences, not proof that the routine caused them.",
    }


def night_insight(experiment, record):
    """Compare a night with at least three earlier usual-routine nights."""
    outcome = experiment.get("outcome", SLEEP)
    if outcome not in OUTCOMES:
        raise ValueError("Choose a supported main outcome.")
    selected_date = _night_date(record.get("date"))
    selected_identity = (str(record.get("subject")), str(record.get("recording")))
    nights, _, _ = _prepare_nights(experiment)
    reference = [night[outcome] for night in nights
                 if selected_date is not None and night["date"] is not None
                 and night["date"] < selected_date and night["period"] == PERIODS[0]
                 and night["identity"] != selected_identity and night[outcome] is not None]
    selected, _, _ = _prepare_nights({"recordings": [record]})
    value = selected[0][outcome]
    available = len(reference) >= EARLY_NIGHTS and value is not None
    reference_mean = mean(reference) if reference else None
    difference = value - reference_mean if available else None
    if selected_date is None:
        headline = "Give this night a date to place it in your story."
    elif value is None:
        headline = "Your main outcome is not available for this night."
    elif not available:
        headline = "Your personal comparison is still taking shape."
    elif difference == 0:
        headline = "This night matches your earlier usual-routine average."
    else:
        direction = "higher" if difference > 0 else "lower"
        unit = "rating points" if outcome == RATING else "minutes"
        headline = (f"{abs(difference):.1f} {unit} {direction} than "
                    "your earlier usual-routine average.")
    body = (f"Compared with {len(reference)} earlier usual-routine nights. "
            "This night and later nights are excluded from that average.")
    if not available:
        body += " A personal comparison needs three earlier nights with this outcome."
    elif outcome == SLEEP:
        body += " More or less recorded sleep alone does not tell you whether you slept better."
    return {
        "available": available, "headline": headline, "body": body,
        "reference_count": len(reference), "reference_mean": reference_mean,
        "reference_sd": stdev(reference) if len(reference) > 1 else None,
        "value": value, "difference": difference, "outcome": outcome,
    }
