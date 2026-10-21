import copy
from datetime import date, timedelta
from io import StringIO

import pandas as pd
import pytest

from app.experiments import (
    SLEEP, WAKE, RATING, new_experiment, merge_recordings, record_frame,
    set_diary, update_plan, stage_summary, compare_periods, save_experiment,
    restore_experiment, export_csv, render_report, nightly_table, stage_detail_summary,
)


def test_metrics_are_hand_checkable():
    result = stage_summary(["W", "N1", "N2", "W", "REM", "W"])
    assert result[SLEEP] == 1.5
    assert result[WAKE] == 0.5
    assert result["W (min)"] == 1.5
    awake = stage_summary(["W", "W"])
    assert awake[SLEEP] == 0
    assert awake[WAKE] is None


def test_stage_details_include_intervening_wake_and_all_deep_segments():
    result = stage_detail_summary(["W", "W", "N1", "N2", "W", "W", "N3", "N3", "REM", "N3"])
    assert result["deep_minutes"] == 1.5
    assert result["rem_minutes"] == 0.5
    assert result["first_deep_minutes"] == 2.0


@pytest.mark.parametrize("stages,reason", [
    (["W", "W"], "No sleep"),
    (["W", "N1", "REM"], "No deep-sleep"),
    (["N2", "N3"], "starts during"),
    (["N3", "REM"], "starts during"),
])
def test_stage_timing_is_unavailable_when_not_observed(stages, reason):
    result = stage_detail_summary(stages)
    assert result["first_deep_minutes"] is None
    assert reason in result["first_deep_note"]


def test_first_sleep_can_be_deep_without_inventing_a_positive_delay():
    result = stage_detail_summary(["W", "N3", "N3"])
    assert result["first_deep_minutes"] == 0
    assert result["deep_minutes"] == 1
    assert result["rem_minutes"] == 0


def test_comparison_weights_nights_and_handles_missing():
    nights = pd.DataFrame([
        {"Date": "2026-01-01", "Period": "Usual routine", SLEEP: 100, WAKE: 1, RATING: 1},
        {"Date": "2026-01-02", "Period": "Usual routine", SLEEP: 300, WAKE: 3, RATING: None},
        {"Date": "2026-01-03", "Period": "Changed routine", SLEEP: 250, WAKE: 2, RATING: 4},
        {"Date": None, "Period": "Changed routine", SLEEP: 999, WAKE: 9, RATING: 5},
    ])
    result = compare_periods(nights).set_index("Outcome")
    assert result.loc[SLEEP, "Usual mean"] == 200
    assert result.loc[SLEEP, "Difference"] == 50
    assert result.loc[RATING, "Usual nights"] == 1
    assert result.loc[SLEEP, "Usual SD"] == pytest.approx(141.421356)
    assert pd.isna(result.loc[SLEEP, "Changed SD"])
    assert compare_periods(pd.DataFrame())["Difference"].isna().all()


def test_merge_replace_and_subject_boundaries(feature_frame, bundle):
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    assert len(exp["recordings"]) == 2
    merge_recordings(exp, feature_frame.sample(frac=1), "7", columns)
    assert len(exp["recordings"]) == 2
    changed = feature_frame.copy()
    changed.loc[0, columns[0]] = 80
    before = copy.deepcopy(exp)
    with pytest.raises(ValueError, match="Replace"):
        merge_recordings(exp, changed, "7", columns)
    assert exp == before
    exp["recordings"][0]["stages"] = ["W"] * 12
    merge_recordings(exp, changed, "7", columns, replace=True)
    assert exp["recordings"][0]["stages"] is None
    with pytest.raises(ValueError, match="one person"):
        merge_recordings(exp, feature_frame.assign(Subject_ID="8"), "8", columns)


def test_diary_history_and_roundtrip(feature_frame, bundle):
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    update_plan(exp, "Bedtime", "Keep a consistent bedtime", SLEEP)
    set_diary(exp["recordings"][0], "2026-01-02", "Usual routine", None, "A note")
    exp["reviewed"] = True
    update_plan(exp, "Bedtime", "Keep a consistent bedtime", WAKE)
    assert exp["outcome_history"][-1]["after_review"] is True
    restored = restore_experiment(save_experiment(exp), columns)
    assert restored["outcome_history"] == exp["outcome_history"]
    assert restored["recordings"][0]["rating"] is None
    pd.testing.assert_frame_equal(record_frame(restored["recordings"][0]),
                                  record_frame(exp["recordings"][0]))
    for bad in [b"{}", b"not json", b'{"schema_version": 99}']:
        with pytest.raises(ValueError):
            restore_experiment(bad, columns)
    with pytest.raises(ValueError):
        set_diary(exp["recordings"][0], "bad date", "Usual routine", 6, "")


def test_exports_escape_text_and_restored_predictions_are_not_trusted(feature_frame, bundle):
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    exp["title"] = "<script>alert(1)</script>"
    exp["recordings"][0]["stages"] = ["W"] * 12
    exp["recordings"][0]["model_fingerprint"] = "fake"
    report = render_report(exp, "trusted-model")
    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "'=SUM" in export_csv(pd.DataFrame({"Notes": ["=SUM(A1)"]})).decode()
    restored = restore_experiment(save_experiment(exp), columns)
    assert restored["recordings"][0]["stages"] is None
    assert restored["recordings"][0]["model_fingerprint"] is None


def test_context_and_decisions_survive_backup_and_recording_replacement(feature_frame, bundle):
    from app.journey import set_night_context, invalidate_decision
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    exp.update(habit_id="wind_down", phase="complete", decision="Keep this routine",
               change_started_on="2026-01-02")
    record = exp["recordings"][0]
    set_diary(record, "2026-01-02", "Changed routine", 4, "Travel")
    set_night_context(record, ["Travel"], False)
    invalidate_decision(exp, "A check-in was edited.")
    restored = restore_experiment(save_experiment(exp), columns)
    assert restored["recordings"][0]["context"] == ["Travel"]
    assert restored["recordings"][0]["adherence"] is False
    assert restored["decision_history"] == exp["decision_history"]
    assert restored["phase"] == "changed"
    assert restored["habit_id"] == "wind_down"
    assert restored["change_started_on"] == "2026-01-02"
    changed = feature_frame.copy()
    changed.loc[0, columns[0]] = 80
    merge_recordings(restored, changed, "7", columns, replace=True)
    assert restored["recordings"][0]["context"] == ["Travel"]
    assert restored["recordings"][0]["adherence"] is False


def test_future_dates_and_duplicate_night_dates_cannot_enter_a_backup(feature_frame, bundle):
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    with pytest.raises(ValueError, match="future"):
        set_diary(exp["recordings"][0], date.today() + timedelta(days=1), "Usual routine", None, "")
    for record in exp["recordings"]:
        set_diary(record, "2026-01-02", "Usual routine", None, "")
    with pytest.raises(ValueError, match="one complete recording"):
        restore_experiment(save_experiment(exp), columns)


def test_invalid_routine_start_date_cannot_enter_a_backup(feature_frame, bundle):
    exp = new_experiment()
    columns = bundle.preprocessor["feature_columns"]
    merge_recordings(exp, feature_frame, "7", columns)
    for value in ("not-a-date", (date.today() + timedelta(days=1)).isoformat()):
        exp["change_started_on"] = value
        with pytest.raises(ValueError):
            restore_experiment(save_experiment(exp), columns)


def test_empty_participant_plan_keeps_its_identity_when_restored():
    exp = new_experiment()
    exp["subject"] = "7"
    restored = restore_experiment(save_experiment(exp), ["signal"])
    assert restored["subject"] == "7"
    assert restored["recordings"] == []


def test_imported_comparison_snapshots_are_not_trusted():
    exp = new_experiment()
    exp.update(decision="Keep this routine", phase="complete",
               saved_comparison={"headline": "Unverified claim", "primary": {"difference": 999}})
    exp["decision_history"] = [{
        "decision": "Keep this routine", "reason": "A check-in was edited.",
        "time": "2026-01-01T00:00:00+00:00",
        "comparison": {"headline": "Unverified earlier claim"},
    }]
    restored = restore_experiment(save_experiment(exp), ["signal"])
    assert restored["decision"] == "Keep this routine"
    assert "saved_comparison" not in restored
    assert restored["decision_history"] == [{
        "decision": "Keep this routine", "reason": "A check-in was edited.",
        "time": "2026-01-01T00:00:00+00:00",
    }]


def test_many_identical_reuploads_do_not_inflate_nights_or_clear_results():
    frame = pd.DataFrame({
        "Subject_ID": ["7"] * 6, "Recording_ID": ["1"] * 3 + ["2"] * 3,
        "Epoch_ID": [1, 2, 3] * 2, "signal": [1.25, None, 3, 4, 5, 6],
    })
    exp = new_experiment()
    merge_recordings(exp, frame, "7", ["signal"])
    for record in exp["recordings"]:
        record.update(stages=["W", "N2", "W"], model_fingerprint="test-model",
                      date="2026-01-01" if record["recording"] == "1" else "2026-01-02")
    before = copy.deepcopy(exp)
    for seed in range(25):
        result = merge_recordings(exp, frame.sample(frac=1, random_state=seed), "7", ["signal"])
        assert result == (0, 0, 2)
        assert exp == before


def test_csv_numbers_and_json_numbers_compare_without_false_replacements(feature_frame, bundle):
    columns = bundle.preprocessor["feature_columns"]
    exp = new_experiment()
    merge_recordings(exp, feature_frame, "7", columns)
    before = copy.deepcopy(exp)
    csv_frame = pd.read_csv(StringIO(feature_frame.to_csv(index=False)), dtype=str)
    assert merge_recordings(exp, csv_frame, "7", columns) == (0, 0, 2)
    assert exp == before
