"""Independent small examples for consumer comparisons and their limits."""
from copy import deepcopy
import json

import pytest

from app.experiments import PERIODS, RATING, SLEEP, WAKE, new_experiment
from app.insights import describe_experiment, night_insight


def night(identity, day, period, sleep_minutes=10, wake_minutes=0, rating=None, **kwargs):
    """Put wake only between sleep epochs, so expected durations are explicit."""
    asleep = ["N2"] * int(sleep_minutes * 2)
    stages = (asleep[:1] + ["W"] * int(wake_minutes * 2) + asleep[1:]
              if asleep else ["W"] * 4)
    return {"subject": "one", "recording": str(identity),
            "date": f"2026-10-{day:02}" if day else None,
            "period": period, "stages": stages, "rating": rating, **kwargs}


def experiment(records, outcome=SLEEP):
    result = new_experiment()
    result.update(recordings=records, outcome=outcome)
    return result


def test_equal_night_weight_missing_rating_and_sample_sd():
    records = [
        night("a", 1, PERIODS[0], 10, rating=2),
        night("b", 2, PERIODS[0], 20),
        night("c", 3, PERIODS[0], 30, rating=4),
        night("d", 4, PERIODS[1], 25, rating=5),
        night("e", 5, PERIODS[1], 30),
        night("f", 6, PERIODS[1], 35, rating=3),
    ]
    result = describe_experiment(experiment(records))
    assert result["primary"] == {
        "unit": "minutes", "usual_count": 3, "usual_mean": 20, "usual_sd": 10,
        "changed_count": 3, "changed_mean": 30, "changed_sd": 5,
        "difference": 10, "direction": "higher",
    }
    assert result["outcomes"][RATING]["usual_count"] == 2
    assert result["outcomes"][RATING]["changed_count"] == 2
    assert result["outcomes"][RATING]["difference"] == 1
    assert result["consistency"]["count"] == 3
    assert result["consistency"]["usual_median"] == 20
    assert result["variation"]["difference_to_usual_sd"] == 1
    assert result["status"] == "pattern"
    assert result["progress"]["target"] == 5


def test_duplicate_undated_and_unassigned_nights_never_inflate_comparison():
    a = night("a", 1, PERIODS[0], 10)
    records = [a, deepcopy(a), night("undated", None, PERIODS[0], 100),
               night("unassigned", 2, None, 100), night("b", 3, PERIODS[1], 20)]
    before = deepcopy(records)
    result = describe_experiment(experiment(records))
    assert result["primary"]["usual_count"] == 1
    assert result["eligible_nights"] == 2
    assert result["excluded_undated"] == 1
    assert result["duplicate_recordings"] == 1
    assert result["status"] == "early"
    assert result["primary"]["usual_sd"] is None
    assert records == before


def test_sensitivity_keeps_flagged_nights_in_primary_and_exposes_reversal():
    records = [night(f"u{i}", i, PERIODS[0], 10) for i in range(1, 4)]
    records += [night("c1", 4, PERIODS[1], 9), night("c2", 5, PERIODS[1], 9),
                night("c3", 6, PERIODS[1], 30, context=["Travel"])]
    result = describe_experiment(experiment(records))
    assert result["primary"]["changed_count"] == 3
    assert result["primary"]["difference"] == 6
    assert result["sensitivity"]["primary"]["difference"] == -1
    assert result["sensitivity"]["excluded_count"] == 1
    assert result["sensitivity"]["direction_reversal"] is True
    assert result["status"] == "mixed"
    assert result["consistency"]["count"] == 1
    assert result["consistency"]["total"] == 3


def test_adherence_false_and_all_excluded_leave_sensitivity_unavailable():
    records = [night("u", 1, PERIODS[0], 10),
               night("c", 2, PERIODS[1], 12, adherence=False)]
    result = describe_experiment(experiment(records))
    assert result["primary"]["difference"] == 2
    assert result["sensitivity"]["available"] is False
    assert result["sensitivity"]["primary"]["difference"] is None
    assert result["sensitivity"]["direction_reversal"] is False


def test_adherence_is_not_applied_to_the_usual_routine():
    records = [night("u", 1, PERIODS[0], 10, adherence=False),
               night("c", 2, PERIODS[1], 12)]
    result = describe_experiment(experiment(records))
    assert result["sensitivity"]["excluded_count"] == 0
    assert result["sensitivity"]["primary"]["difference"] == 2


def test_wake_direction_ties_and_disagreement_with_feeling():
    records = [night(f"u{i}", i, PERIODS[0], 10, 2, rating=4) for i in range(1, 4)]
    records += [night("c1", 4, PERIODS[1], 10, 1, rating=3),
                night("c2", 5, PERIODS[1], 10, 2, rating=3),
                night("c3", 6, PERIODS[1], 10, 1, rating=3)]
    result = describe_experiment(experiment(records, WAKE))
    assert result["primary"]["difference"] == pytest.approx(-2 / 3)
    assert result["consistency"]["count"] == 2
    assert result["consistency"]["ties"] == 1
    assert result["consistency"]["total"] == 3
    assert result["feeling_disagrees"] is True
    assert result["status"] == "mixed"
    assert "less rested, while estimated wake during sleep decreased" in result["body"]
    assert result["paired_outcome"] == RATING


def test_no_claim_of_disagreement_without_repeated_ratings():
    records = [night(f"u{i}", i, PERIODS[0], 10, rating=4 if i == 1 else None)
               for i in range(1, 4)]
    records += [night(f"c{i}", i + 3, PERIODS[1], 12, rating=2 if i == 1 else None)
                for i in range(1, 4)]
    result = describe_experiment(experiment(records))
    assert result["feeling_disagrees"] is False
    assert result["paired_status"] == "early"
    assert result["paired_comparison"]["usual_count"] == 1
    assert result["paired_comparison"]["changed_count"] == 1
    assert "fewer than three matching nights" in result["paired_note"]


def test_all_wake_missing_predictions_and_nan_become_unavailable_not_zero():
    records = [night("u", 1, PERIODS[0], 0, rating=float("nan")),
               night("c", 2, PERIODS[1], 0)]
    records[1]["stages"] = None
    result = describe_experiment(experiment(records, WAKE))
    assert result["primary"]["usual_count"] == 0
    assert result["primary"]["usual_mean"] is None
    assert result["outcomes"][SLEEP]["usual_mean"] == 0
    assert result["outcomes"][RATING]["usual_count"] == 0
    assert result["status"] == "starting"
    json.dumps(result, allow_nan=False)


def test_personal_night_reference_excludes_itself_later_and_same_date():
    records = [night("u1", 1, PERIODS[0], 10), night("u2", 2, PERIODS[0], 20),
               night("u3", 3, PERIODS[0], 30), night("selected", 4, PERIODS[0], 50),
               night("same_date", 4, PERIODS[0], 100), night("later", 5, PERIODS[0], 100),
               night("changed_earlier", 2, PERIODS[1], 100)]
    result = night_insight(experiment(records), records[3])
    assert result["available"] is True
    assert result["reference_count"] == 3
    assert result["reference_mean"] == 20
    assert result["reference_sd"] == 10
    assert result["difference"] == 30
    assert result["value"] == 50
    assert "later nights are excluded" in result["body"]


def test_night_insight_needs_date_valid_outcome_and_three_earlier_nights():
    records = [night("u1", 1, PERIODS[0], 10), night("u2", 2, PERIODS[0], 20),
               night("selected", 3, PERIODS[1], 50)]
    result = night_insight(experiment(records), records[2])
    assert result["reference_count"] == 2
    assert result["available"] is False
    assert result["difference"] is None
    records[2]["date"] = None
    result = night_insight(experiment(records), records[2])
    assert result["reference_count"] == 0
    assert result["available"] is False
    assert "date" in result["headline"]


def test_empty_experiment_and_complete_plan_states():
    empty = describe_experiment(new_experiment())
    assert empty["status"] == "starting"
    assert empty["progress"]["remaining"] == 5
    records = [night(f"u{i}", i, PERIODS[0], 10) for i in range(1, 6)]
    baseline = describe_experiment(experiment(records))
    assert baseline["progress"]["phase"] == "change"
    records += [night(f"c{i}", i + 5, PERIODS[1], 10) for i in range(1, 6)]
    complete = describe_experiment(experiment(records))
    assert complete["status"] == "no_change"
    assert complete["progress"]["phase"] == "review"
    assert complete["progress"]["remaining"] == 0
    assert complete["consistency"]["ties"] == 5
    assert complete["variation"]["difference_to_usual_sd"] is None
    json.dumps(complete, allow_nan=False)


def test_comparisons_do_not_pool_different_people():
    records = [night("a", 1, PERIODS[0]), night("b", 2, PERIODS[1])]
    records[1]["subject"] = "another-person"
    with pytest.raises(ValueError, match="one person"):
        describe_experiment(experiment(records))


def test_deliberate_early_switch_does_not_send_person_back_to_baseline():
    records = [night("u1", 1, PERIODS[0], 10),
               night("c1", 2, PERIODS[1], 12)]
    exp = experiment(records)
    exp["phase"] = "changed"
    result = describe_experiment(exp)
    assert result["status"] == "early"
    assert result["progress"]["phase"] == "change"
    assert result["progress"]["usual"] == 1
    assert result["progress"]["remaining"] == 4
    assert "changed-routine" in result["next_action"]
    assert "usual-routine" not in result["next_action"]


@pytest.mark.parametrize("changed_count", [1, 5, 7])
def test_changed_nights_without_a_starting_reference_do_not_prompt_a_decision(changed_count):
    records = [night(f"c{i}", i, PERIODS[1], 12)
               for i in range(1, changed_count + 1)]
    exp = experiment(records)
    exp["phase"] = "changed"
    result = describe_experiment(exp)
    assert result["primary"]["usual_count"] == 0
    assert result["primary"]["changed_count"] == changed_count
    assert result["status"] == "baseline"
    assert result["progress"]["phase"] == ("change" if changed_count < 5 else "review")
    assert "nights recorded before you started the change" in result["next_action"]
    assert "begin a new comparison" in result["next_action"]
    assert "deciding what to keep" not in result["next_action"]
    assert exp["phase"] == "changed"


def test_completed_experiment_does_not_ask_for_more_nights():
    exp = experiment([night("u1", 1, PERIODS[0]), night("c1", 2, PERIODS[1])])
    exp.update(phase="complete", decision="Keep this routine")
    result = describe_experiment(exp)
    assert result["status"] == "early"
    assert result["progress"]["phase"] == "review"
    assert result["progress"]["remaining"] == 0
    assert "saved decision" in result["next_action"]
    assert "Keep tracking" in result["next_action"]


def test_restfulness_goal_also_compares_the_crf_measurement():
    records = [night(f"u{i}", i, PERIODS[0], 10, 2, rating=2) for i in range(1, 4)]
    records += [night(f"c{i}", i + 3, PERIODS[1], 10, 4, rating=4) for i in range(1, 4)]
    result = describe_experiment(experiment(records, RATING))
    assert result["paired_outcome"] == WAKE
    assert result["feeling_disagrees"] is True
    assert result["status"] == "mixed"
    assert "more rested, while estimated wake during sleep increased" in result["body"]


def test_restfulness_pair_uses_sleep_when_wake_is_undefined():
    records = [night(f"u{i}", i, PERIODS[0], 0, rating=2) for i in range(1, 4)]
    records += [night(f"c{i}", i + 3, PERIODS[1], 10, rating=4) for i in range(1, 4)]
    result = describe_experiment(experiment(records, RATING))
    assert result["paired_outcome"] == SLEEP
    assert result["feeling_disagrees"] is False
    assert result["status"] == "pattern"
    assert "more rested, while estimated sleep increased" in result["paired_message"]


def test_restfulness_without_any_stage_estimate_has_no_paired_claim():
    records = [night("u", 1, PERIODS[0], rating=2), night("c", 2, PERIODS[1], rating=4)]
    for record in records:
        record["stages"] = None
    result = describe_experiment(experiment(records, RATING))
    assert result["paired_outcome"] is None
    assert result["paired_message"] is None
    assert result["paired_comparison"] is None
    assert result["paired_status"] == "unavailable"
    assert "both a morning rating and an available sleep estimate" in result["paired_note"]
    assert result["feeling_disagrees"] is False


@pytest.mark.parametrize("outcome", [WAKE, RATING])
def test_feeling_agreement_uses_the_same_nights_without_replacing_all_night_results(outcome):
    # Unrated nights make the full wake average look better. On the nights
    # actually rated, wake gets worse while morning ratings get better.
    records = [
        night(f"u{i}", i, PERIODS[0], 10, 20 if i <= 3 else 100,
              rating=3 if i <= 3 else None)
        for i in range(1, 7)
    ]
    records += [
        night(f"c{i}", i + 6, PERIODS[1], 10, 30 if i <= 3 else 10,
              rating=4 if i <= 3 else None)
        for i in range(1, 7)
    ]
    original = deepcopy(records)
    result = describe_experiment(experiment(records, outcome))
    assert result["outcomes"][WAKE]["usual_mean"] == 60
    assert result["outcomes"][WAKE]["changed_mean"] == 20
    assert result["outcomes"][WAKE]["difference"] == -40
    assert result["outcomes"][WAKE]["usual_count"] == 6
    assert result["primary"] == result["outcomes"][outcome]
    matched = result["paired_comparison"]
    wake = matched["primary"] if outcome == WAKE else matched["paired"]
    rating = matched["paired"] if outcome == WAKE else matched["primary"]
    assert matched["usual_count"] == matched["changed_count"] == 3
    assert wake["usual_mean"] == 20
    assert wake["changed_mean"] == 30
    assert rating["difference"] == 1
    assert result["paired_status"] == "available"
    assert result["feeling_disagrees"] is True
    assert result["status"] == "mixed"
    assert "more rested, while estimated wake during sleep increased" in result["paired_message"]
    assert "same 3 nights before and 3 nights with the change" in result["paired_note"]
    assert records == original


def test_separate_ratings_and_recordings_cannot_create_a_paired_comparison():
    records = []
    for period_index, period in enumerate(PERIODS):
        for i in range(1, 4):
            day = period_index * 6 + i
            records.append(night(f"estimate{day}", day, period, 10, 5))
            rating_only = night(f"rating{day}", day + 3, period, 10, rating=2 + period_index)
            rating_only["stages"] = None
            records.append(rating_only)
    result = describe_experiment(experiment(records, WAKE))
    assert result["outcomes"][WAKE]["usual_count"] == 3
    assert result["outcomes"][RATING]["usual_count"] == 3
    assert result["paired_outcome"] is None
    assert result["paired_comparison"] is None
    assert result["paired_message"] is None
    assert result["paired_status"] == "unavailable"
    assert "Separate averages alone cannot show whether the two agree" in result["paired_note"]
    assert result["feeling_disagrees"] is False


def test_restfulness_prefers_a_recording_measure_with_repeated_matching_nights():
    records = []
    for period_index, period in enumerate(PERIODS):
        for i in range(1, 4):
            # Wake is defined for only one rated night in each period.
            records.append(night(
                f"{period_index}_{i}", period_index * 3 + i, period,
                sleep_minutes=10 if i == 1 else 0, wake_minutes=1,
                rating=2 + period_index,
            ))
    result = describe_experiment(experiment(records, RATING))
    assert result["paired_outcome"] == SLEEP
    assert result["paired_status"] == "available"
    assert result["paired_comparison"]["usual_count"] == 3
    assert result["paired_comparison"]["changed_count"] == 3
    assert result["paired_comparison"]["paired"]["difference"] == 0


def test_recording_coverage_counts_wake_and_excludes_ineligible_or_unanalysed_nights():
    usual = night("u1", 1, PERIODS[0], 10, 5)  # 15 recorded minutes.
    pending = night("pending", 7, PERIODS[1], 100, rating=5)
    pending["stages"] = None
    records = [
        usual, deepcopy(usual), night("u2", 2, PERIODS[0], 20, 0),
        night("c1", 3, PERIODS[1], 20, 10), night("c2", 4, PERIODS[1], 10, 20),
        night("undated", None, PERIODS[0], 100), night("unassigned", 6, None, 100), pending,
    ]
    coverage = describe_experiment(experiment(records))["recording_coverage"]
    assert coverage["usual_count"] == 2
    assert coverage["changed_count"] == 2
    assert coverage["usual_mean"] == 17.5
    assert coverage["changed_mean"] == 30
    assert coverage["difference"] == 12.5
    assert "12.5 more minutes" in coverage["sentence"]
    assert "not time in bed or sleep opportunity" in coverage["note"]


def test_recording_coverage_half_minute_resolution_and_missing_period():
    records = [night("u", 1, PERIODS[0]), night("c", 2, PERIODS[1])]
    records[0]["stages"] = ["N2"] * 1186
    records[1]["stages"] = ["N2"] * 1103
    coverage = describe_experiment(experiment(records))["recording_coverage"]
    assert coverage["difference"] == -41.5
    assert "41.5 fewer minutes" in coverage["sentence"]
    records[1]["date"] = None
    coverage = describe_experiment(experiment(records))["recording_coverage"]
    assert coverage["changed_count"] == 0
    assert coverage["difference"] is None
    json.dumps(coverage, allow_nan=False)
