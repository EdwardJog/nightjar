"""Product rules: usable progress, revisable decisions and an isolated demo."""
from copy import deepcopy

import pytest

from app.experiments import PERIODS, RATING, SLEEP, WAKE, stage_summary
from app.insights import describe_experiment
from app.journey import (
    DEVICES, HABITS, active_experiment, build_demo_workspace, count_complete_nights,
    invalidate_decision, make_workspace, night_is_complete, night_needs_attention, set_night_context,
    start_experiment,
)


def record(identity, *, stages=None, rating=None, night_date="2026-10-01"):
    return {
        "subject": "one", "recording": identity, "stages": stages,
        "rating": rating, "date": night_date, "period": PERIODS[0],
    }


def test_restfulness_progress_requires_rating_and_an_analysed_night():
    workspace = make_workspace("Alex", DEVICES[0], "Feel more rested")
    exp = start_experiment(workspace, "wind_down")
    exp["recordings"] = [
        record("missing_rating", stages=["N2", "W", "N2"]),
        record("pending_analysis", rating=4),
        record("missing_date", stages=["N2"], rating=4, night_date=None),
        record("complete", stages=["N2"], rating=3),
    ]
    assert count_complete_nights(exp, PERIODS[0]) == 1
    assert count_complete_nights(exp, PERIODS[1]) == 0


def test_all_wake_night_cannot_complete_wake_goal_but_can_complete_sleep_goal():
    exp = {"outcome": WAKE, "recordings": []}
    awake = record("all_wake", stages=["W"] * 10)
    assert night_is_complete(exp, awake) is False
    assert night_needs_attention(exp, awake) is False
    exp["outcome"] = SLEEP
    assert night_is_complete(exp, awake) is True
    exp["outcome"] = RATING
    awake["rating"] = 2
    assert night_is_complete(exp, awake) is True


def test_profile_goal_change_affects_future_experiments_only():
    workspace = make_workspace(" Alex ", DEVICES[0], "Feel more rested")
    first = start_experiment(workspace, "wind_down", "Read quietly for an hour.")
    workspace["profile"]["goal"] = "Spend less time awake at night"
    second = start_experiment(workspace, "bedroom")
    assert workspace["profile"]["name"] == "Alex"
    assert first["outcome"] == RATING
    assert first["change"] == "Read quietly for an hour."
    assert second["outcome"] == WAKE
    assert second["change"] == HABITS["bedroom"]["action"]
    assert active_experiment(workspace) is second
    assert first["id"] != second["id"]


def test_changed_evidence_keeps_previous_decision_as_history():
    workspace = make_workspace("", DEVICES[0], "Feel more rested")
    exp = start_experiment(workspace, "wind_down")
    exp.update(decision="Keep this routine", phase="complete", reviewed=True)
    invalidate_decision(exp, "A night was removed.")
    assert exp["decision"] is None
    assert exp["phase"] == "changed"
    assert exp["reviewed"] is False
    assert exp["decision_history"][0]["decision"] == "Keep this routine"
    assert exp["decision_history"][0]["reason"] == "A night was removed."
    invalidate_decision(exp, "Another change.")
    assert len(exp["decision_history"]) == 1


def test_night_context_is_validated_before_mutating_and_duplicates_removed():
    night = record("one", stages=["N2"])
    set_night_context(night, ["Travel", "Travel"], False)
    assert night["context"] == ["Travel"]
    assert night["adherence"] is False
    previous = deepcopy(night)
    with pytest.raises(ValueError, match="circumstances"):
        set_night_context(night, ["Unknown"], True)
    assert night == previous
    with pytest.raises(ValueError, match="yes, no"):
        set_night_context(night, [], "Yes")
    assert night == previous


def test_demo_is_generated_isolated_and_explicitly_unanalysed():
    first, second = build_demo_workspace(), build_demo_workspace()
    exp = active_experiment(first)
    assert len(exp["recordings"]) == 10
    assert count_complete_nights(exp, PERIODS[0]) == 5
    assert count_complete_nights(exp, PERIODS[1]) == 5
    assert {r["model_fingerprint"] for r in exp["recordings"]} == {"illustrative-demo"}
    assert all(not r["data"] and not r["columns"] for r in exp["recordings"])
    assert all("invented" in r["notes"] for r in exp["recordings"])
    assert len({r["date"] for r in exp["recordings"]}) == 10
    assert describe_experiment(exp)["primary"]["difference"] is not None
    exp["recordings"][0]["rating"] = 1
    assert active_experiment(second)["recordings"][0]["rating"] == 2


def test_demo_comparison_comes_from_stages_and_keeps_the_unusual_night():
    """Known fictional sequences produce a clear but imperfect comparison."""
    exp = active_experiment(build_demo_workspace())
    summaries = [stage_summary(night["stages"]) for night in exp["recordings"]]
    assert [summary[WAKE] for summary in summaries] == [
        39, 48, 44, 54, 40, 9, 12, 14, 45, 10,
    ]
    assert [summary[SLEEP] for summary in summaries] == [
        438, 444, 438, 443, 447, 473, 475, 483, 432, 482,
    ]
    assert [len(night["stages"]) * 0.5 for night in exp["recordings"]] == [
        490, 505, 495, 510, 500, 495, 500, 510, 490, 505,
    ]
    result = describe_experiment(exp)
    primary = result["primary"]
    assert primary["usual_count"] == primary["changed_count"] == 5
    assert primary["usual_mean"] == 45
    assert primary["changed_mean"] == 18
    assert primary["difference"] == -27
    assert primary["usual_sd"] == pytest.approx(38 ** 0.5)
    assert primary["changed_sd"] == pytest.approx(231.5 ** 0.5)
    assert result["consistency"]["count"] == 4
    assert result["consistency"]["total"] == 5
    assert result["consistency"]["usual_median"] == 44
    assert result["consistency"]["ties"] == 0
    assert result["outcomes"][RATING]["usual_mean"] == 2
    assert result["outcomes"][RATING]["changed_mean"] == pytest.approx(4.2)
    assert result["outcomes"][RATING]["difference"] == pytest.approx(2.2)
    assert result["outcomes"][SLEEP]["difference"] == 27
    assert result["recording_coverage"]["usual_mean"] == 500
    assert result["recording_coverage"]["changed_mean"] == 500
    assert result["recording_coverage"]["difference"] == 0

    # The main result includes the 45-minute changed night. The optional view
    # excludes exactly that labelled night, without changing the main counts.
    assert exp["recordings"][8]["context"] == ["Unusual stress"]
    assert sum(bool(night["context"]) for night in exp["recordings"]) == 1
    sensitivity = result["sensitivity"]
    assert sensitivity["excluded_count"] == 1
    assert sensitivity["primary"]["changed_count"] == 4
    assert sensitivity["primary"]["changed_mean"] == 11.25
    assert sensitivity["primary"]["difference"] == -33.75
    assert sensitivity["direction_reversal"] is False
    assert result["feeling_disagrees"] is False


def test_profile_does_not_fake_device_or_age_based_personalisation():
    workspace = make_workspace("Alex", "Muse / Interaxon", "Feel more rested")
    assert set(workspace["profile"]) == {"name", "device", "goal"}
    assert workspace["subject"] is None
    with pytest.raises(ValueError):
        make_workspace("Alex", "Unsupported invented device", "Feel more rested")
