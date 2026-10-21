"""A saved choice keeps its original evidence as the live comparison evolves."""
from copy import deepcopy

import pytest

from app.experiments import PERIODS
from app.insights import describe_experiment
from app.journey import active_experiment, build_demo_workspace, invalidate_decision
from app.routine_history import keep_routine
from app.storage import load_workspace, save_workspace


def test_kept_comparison_is_frozen_through_edits_and_local_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("NIGHTJAR_DATA_DIR", str(tmp_path / "history"))
    workspace = build_demo_workspace()
    experiment = active_experiment(workspace)
    keep_routine(experiment)
    saved = deepcopy(experiment["saved_comparison"])
    assert saved["primary"]["usual_mean"] == 45
    assert saved["primary"]["changed_mean"] == 18
    assert saved["primary"]["difference"] == -27
    keep_routine(experiment)
    assert experiment["saved_comparison"] == saved

    # A later edit changes live results, but not the evidence behind the choice.
    experiment["recordings"][-1]["stages"] = ["N2"] * 100 + ["W"] * 160 + ["N2"] * 100
    invalidate_decision(experiment, "A saved night changed.")
    assert experiment["decision"] is None
    assert "saved_comparison" not in experiment
    assert experiment["decision_history"][-1]["comparison"] == saved
    assert describe_experiment(experiment)["primary"]["changed_mean"] == 32
    save_workspace(workspace)
    reloaded = active_experiment(load_workspace())
    assert reloaded["decision_history"][-1]["comparison"] == saved
    keep_routine(reloaded)
    assert reloaded["saved_comparison"]["primary"]["changed_mean"] == 32
    assert reloaded["decision_history"][-1]["comparison"] == saved


def test_cannot_save_a_comparison_with_one_period_missing():
    experiment = active_experiment(build_demo_workspace())
    experiment["recordings"] = [r for r in experiment["recordings"] if r["period"] == PERIODS[0]]
    before = deepcopy(experiment)
    with pytest.raises(ValueError, match="both periods"):
        keep_routine(experiment)
    assert experiment == before
