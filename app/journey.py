"""Small, explicit product rules for a personal routine experiment."""
from datetime import date, timedelta, datetime, timezone
from uuid import uuid4

from app.experiments import new_experiment, update_plan, stage_summary, SLEEP, WAKE, RATING, PERIODS

GOALS = {
    "Feel more rested": RATING,
    "Spend less time awake at night": WAKE,
    "Make more room for sleep": SLEEP,
}
DEVICES = (
    "Compatible feature CSV",
    "Muse / Interaxon",
    "FRENZ Brainband",
    "Another EEG recorder",
)
CONTEXTS = ("Travel", "Unwell", "Alcohol", "Unusual stress", "Schedule change")
HABITS = {
    "wind_down": {
        "name": "A calmer last hour",
        "short": "Give the day a gentler ending.",
        "action": "Set aside the hour before bed for quiet activities and softer light.",
        "why": "A quiet hour gives you a practical routine to repeat. Keep the rest of your evening as similar as you can.",
        "prompt": "Did you make time for your quieter last hour?",
        "icon": "☾",
    },
    "wake_time": {
        "name": "A steadier wake-up",
        "short": "One familiar start to your day.",
        "action": "Choose a realistic wake-up time and aim to keep it consistent, including weekends.",
        "why": "Regular sleep and wake times are part of healthy sleep habits. Choose a time that still leaves enough opportunity to sleep.",
        "prompt": "Did you keep your chosen wake-up time?",
        "icon": "◷",
    },
    "caffeine": {
        "name": "An earlier last coffee",
        "short": "Try moving caffeine out of your evening.",
        "action": "Choose an earlier cutoff for caffeinated drinks and keep it the same during this experiment.",
        "why": "Caffeine can affect sleep for up to eight hours. Your cutoff is a routine to explore, not a timing prescription from your EEG.",
        "prompt": "Did you keep your caffeine cutoff?",
        "icon": "◌",
    },
    "bedroom": {
        "name": "A quieter, darker room",
        "short": "Make one change to your surroundings.",
        "action": "Choose one practical change that makes your room quieter or darker, then repeat it each night.",
        "why": "A quiet, dark bedroom supports sleep. Change one thing so your comparison stays understandable.",
        "prompt": "Did you use your chosen room change?",
        "icon": "▧",
    },
}


def make_workspace(name, device, goal):
    """No birth date: this model cannot use it to personalise its estimates."""
    if device not in DEVICES or goal not in GOALS:
        raise ValueError("Choose a device and a sleep goal.")
    if not isinstance(name, str) or len(name) > 40:
        raise ValueError("Use a name of at most 40 characters.")
    return {"schema_version": 2, "revision": 0,
            "profile": {"name": name.strip(), "device": device, "goal": goal},
            "subject": None, "active_experiment": None, "experiments": []}


def start_experiment(workspace, habit_id, personal_plan=""):
    if habit_id not in HABITS:
        raise ValueError("Choose a routine from the library.")
    if len(personal_plan) > 300:
        raise ValueError("Keep your personal plan under 300 characters.")
    habit = HABITS[habit_id]
    experiment = new_experiment()
    update_plan(experiment, habit["name"], personal_plan.strip() or habit["action"],
                GOALS[workspace["profile"]["goal"]])
    experiment.update(id=uuid4().hex, habit_id=habit_id, phase="usual",
                      decision=None, decision_note="", context_version=1)
    workspace["experiments"].append(experiment)
    workspace["active_experiment"] = experiment["id"]
    return experiment


def active_experiment(workspace):
    return next((e for e in workspace["experiments"]
                 if e["id"] == workspace["active_experiment"]), None)


def count_complete_nights(experiment, period):
    """Progress counts nights with the chosen outcome, not just uploaded files."""
    return sum(night_is_complete(experiment, record) and record.get("period") == period
               for record in experiment["recordings"])


def night_is_complete(experiment, record):
    if not record.get("stages") or not record.get("date") or record.get("period") not in PERIODS:
        return False
    if experiment["outcome"] == RATING:
        return record.get("rating") is not None
    return stage_summary(record["stages"])[experiment["outcome"]] is not None


def night_needs_attention(experiment, record):
    """Undefined all-wake WASO needs a new recording, not an endless check-in."""
    return (not record.get("stages") or not record.get("date") or record.get("period") not in PERIODS
            or (experiment["outcome"] == RATING and record.get("rating") is None))


def invalidate_decision(experiment, reason):
    """Retain the prior choice as history when its underlying evidence changes."""
    if experiment.get("decision"):
        entry = {
            "decision": experiment["decision"], "reason": reason,
            "time": datetime.now(timezone.utc).isoformat()}
        if experiment.get("saved_comparison"):
            entry["comparison"] = experiment.pop("saved_comparison")
        experiment.setdefault("decision_history", []).append(entry)
        experiment.update(decision=None, phase="changed")
    experiment["reviewed"] = False


def set_night_context(record, context, adherence):
    if not isinstance(context, list) or not set(context) <= set(CONTEXTS):
        raise ValueError("Choose recognised night circumstances.")
    if adherence is not None and type(adherence) is not bool:
        raise ValueError("Choose yes, no or not recorded for your routine.")
    record["context"] = list(dict.fromkeys(context))
    record["adherence"] = adherence


def build_demo_workspace():
    """Generate an illustrative experience, never copied patient data or CRF results.

    Formula-generated stage sequences let the normal summary and insight functions
    explain a clear before/after example. They are not a physiological simulation,
    model test or evidence that the chosen routine causes an improvement.
    """
    workspace = make_workspace("Alex", DEVICES[0], "Spend less time awake at night")
    experiment = start_experiment(workspace, "wind_down")
    experiment["phase"] = "changed"
    workspace["subject"] = experiment["subject"] = "illustration"
    # Invented, varying nights make the comparison easy to follow. One changed
    # night deliberately goes against the overall pattern and stays in the
    # main average. Context is a label, not a claimed explanation for its sleep.
    wake_minutes = (39, 48, 44, 54, 40, 9, 12, 14, 45, 10)
    ratings = (2, 2, 3, 1, 2, 4, 5, 4, 3, 5)
    # Both periods average 500 recorded minutes. The stronger example should
    # not come merely from making the changed recordings longer.
    recording_epochs = (980, 1010, 990, 1020, 1000, 990, 1000, 1020, 980, 1010)
    for i in range(10):
        changed = i >= 5
        unusual = i == 8
        wake_epochs = 2 * wake_minutes[i]
        # The five blocks below contain 745 sleep epochs before extra N2 is
        # added. Distribute that extra sleep and the internal wake intervals
        # across the trace, keeping the requested total recording length.
        extra_sleep = recording_epochs[i] - 26 - wake_epochs - 745
        extra_per_cycle, extra_remainder = divmod(extra_sleep, 5)
        wake_per_break, wake_remainder = divmod(wake_epochs, 4)
        stages = ["W"] * 18
        for cycle in range(5):
            extra_n2 = extra_per_cycle + int(cycle < extra_remainder)
            stages += ["N1"] * 5 + ["N2"] * (62 + extra_n2) + ["N3"] * (30 - cycle * 4)
            stages += ["N2"] * 38 + ["REM"] * (12 + cycle * 5)
            if cycle < 4:
                stages += ["W"] * (wake_per_break + int(cycle < wake_remainder))
        stages += ["W"] * 8
        experiment["recordings"].append({
            "subject": "illustration", "recording": str(i + 1), "columns": [], "data": [],
            "date": (date.today() - timedelta(days=11 - i)).isoformat(),
            "period": PERIODS[int(changed)], "rating": ratings[i],
            "notes": "An invented night for the walkthrough.",
            "stages": stages, "quality": None, "model_fingerprint": "illustrative-demo",
            "context": ["Unusual stress"] if unusual else [], "adherence": True if changed else None,
        })
    return workspace
