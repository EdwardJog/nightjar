"""Experiment state, transparent nightly calculations, and portable exports."""
from copy import deepcopy
from datetime import date, datetime, timezone
from html import escape
import json

import numpy as np
import pandas as pd

from app.inference import STAGES, EPOCH_KEY, MAX_ROWS, validate_frame

SLEEP = "Estimated sleep (min)"
WAKE = "Estimated wake during sleep (min)"
RATING = "Morning restfulness (1-5)"
OUTCOMES = (SLEEP, WAKE, RATING)
PERIODS = ("Usual routine", "Changed routine")
MAX_EXPERIMENT_BYTES = 150 * 1024 * 1024


def new_experiment():
    return {"schema_version": 1, "title": "", "change": "", "outcome": SLEEP,
            "outcome_history": [], "reviewed": False, "subject": None, "recordings": []}


def _text(value, limit, field):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{field} must be text of at most {limit} characters.")
    return value


def update_plan(experiment, title, change, outcome):
    title = _text(title, 120, "Experiment title").strip()
    change = _text(change, 1000, "Routine change").strip()
    if outcome not in OUTCOMES:
        raise ValueError("Choose a supported main outcome.")
    if outcome != experiment["outcome"]:
        experiment["outcome_history"].append({
            "from": experiment["outcome"], "to": outcome,
            "after_review": experiment["reviewed"],
            "time": datetime.now(timezone.utc).isoformat(),
        })
    experiment.update(title=title, change=change, outcome=outcome)


def record_frame(record):
    return pd.DataFrame(record["data"], columns=record["columns"])


def _pack_frame(frame):
    # Preserve floating-point precision so reopening cannot change model inputs.
    def portable(value):
        if pd.isna(value):
            return None
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            return str(value)
        return value
    return list(frame.columns), [[portable(v) for v in row]
                                 for row in frame.itertuples(index=False, name=None)]


def merge_recordings(experiment, frame, subject, feature_columns, replace=False):
    """Validate the entire change first, then add/replace recordings atomically."""
    frame = validate_frame(frame, feature_columns)
    subject = str(subject)
    if experiment["subject"] not in (None, subject):
        raise ValueError("An experiment belongs to one person. Start a new experiment first.")
    chosen = frame[frame.Subject_ID == subject]
    if chosen.empty:
        raise ValueError("The selected subject has no recordings.")
    pending = deepcopy(experiment["recordings"])
    added = replaced = unchanged = 0
    for recording_id, rows in chosen.groupby("Recording_ID", sort=False):
        rows = rows.sort_values("Epoch_ID").reset_index(drop=True)
        existing = next((r for r in pending if r["recording"] == recording_id), None)
        if existing is not None:
            compare_columns = EPOCH_KEY + list(feature_columns)
            previous = record_frame(existing)
            # Normalise numeric feature strings for repeat uploads from CSV versus JSON.
            def comparable(df):
                out = df[compare_columns].copy()
                # Use the same parsing path for JSON numbers and CSV strings.
                # Parsing only the string side can differ by one floating-point
                # bit and incorrectly demand replacement of an unchanged night.
                out[list(feature_columns)] = out[list(feature_columns)].astype(str).apply(
                    pd.to_numeric, errors="coerce").astype(float)
                return out
            if comparable(rows).equals(comparable(previous)):
                unchanged += 1
                continue
            if not replace:
                raise ValueError(f"Recording {recording_id} already exists with different data. "
                                 "Choose Replace existing recordings to continue.")
        columns, data = _pack_frame(rows)
        record = {"subject": subject, "recording": str(recording_id),
                  "columns": columns, "data": data, "date": None, "period": None,
                  "rating": None, "notes": "", "stages": None,
                  "quality": None, "model_fingerprint": None}
        if existing is not None:
            for field in ("date", "period", "rating", "notes", "context", "adherence"):
                if field in existing:
                    record[field] = existing[field]
            pending[pending.index(existing)] = record
            replaced += 1
        else:
            pending.append(record)
            added += 1
    if sum(len(r["data"]) for r in pending) > MAX_ROWS:
        raise ValueError("An experiment can contain at most 100,000 epochs.")
    experiment.update(subject=subject, recordings=pending)
    return added, replaced, unchanged


def set_diary(record, night_date, period, rating, notes):
    if night_date in ("", None):
        night_date = None
    else:
        try:
            night_date = date.fromisoformat(str(night_date)).isoformat()
        except (ValueError, TypeError) as exc:
            raise ValueError("Choose a valid night date.") from exc
        if night_date > date.today().isoformat():
            raise ValueError("A recorded night cannot have a future date.")
    if period not in (None, *PERIODS):
        raise ValueError("Choose usual routine or changed routine.")
    if rating is not None and (type(rating) not in (int, float)
                               or rating not in (1, 2, 3, 4, 5)):
        raise ValueError("Morning restfulness must be a whole number from 1 to 5.")
    notes = _text(notes, 2000, "Night notes")
    record.update(date=night_date, period=period, rating=rating, notes=notes)


def stage_summary(stages):
    if not stages or not set(stages) <= set(STAGES):
        raise ValueError("A recording must contain recognised predicted stages.")
    values = np.asarray(stages)
    asleep = np.flatnonzero(values != "W")
    wake = (float(np.count_nonzero(values[asleep[0]:asleep[-1] + 1] == "W") * 0.5)
            if len(asleep) else None)
    return {SLEEP: float(len(asleep) * 0.5), WAKE: wake,
            **{f"{stage} (min)": float(np.count_nonzero(values == stage) * 0.5)
               for stage in STAGES}}


def stage_detail_summary(stages):
    """Descriptive stage totals and observed sleep-to-first-N3 elapsed time.

    There is no bedtime/lights-out marker in these files. Do not call this
    time to fall asleep, and withhold the interval if the recording starts
    during sleep because its onset may have happened before recording.
    """
    totals = stage_summary(stages)
    first_sleep = next((i for i, stage in enumerate(stages) if stage != "W"), None)
    first_deep = next((i for i, stage in enumerate(stages) if stage == "N3"), None)
    if first_sleep is None:
        interval, reason = None, "No sleep was estimated in this recording."
    elif first_deep is None:
        interval, reason = None, "No deep-sleep stage was estimated in this recording."
    elif first_sleep == 0:
        interval, reason = None, "The recording starts during estimated sleep, so its beginning was not observed."
    else:
        interval = (first_deep - first_sleep) * 0.5
        reason = "Elapsed time from the first estimated sleep to the first deep-sleep stage, including any wake in between."
    return {"deep_minutes": totals["N3 (min)"], "rem_minutes": totals["REM (min)"],
            "first_deep_minutes": interval, "first_deep_note": reason}


def nightly_table(experiment):
    rows = []
    for record in experiment["recordings"]:
        summary = stage_summary(record["stages"]) if record["stages"] else {
            SLEEP: None, WAKE: None, **{f"{stage} (min)": None for stage in STAGES}}
        rows.append({"Subject_ID": record["subject"], "Recording_ID": record["recording"],
                     "Date": record["date"], "Period": record["period"],
                     **summary, RATING: record["rating"], "Notes": record["notes"],
                     "Circumstances": ", ".join(record.get("context", [])),
                     "Followed routine": record.get("adherence"),
                     "Model fingerprint": record["model_fingerprint"]})
    return pd.DataFrame(rows)


def compare_periods(nights):
    eligible = (nights[nights.Date.notna() & nights.Period.isin(PERIODS)]
                if not nights.empty else nights)
    rows = []
    for outcome in OUTCOMES:
        row = {"Outcome": outcome}
        for period, prefix in zip(PERIODS, ("Usual", "Changed")):
            values = (pd.to_numeric(eligible.loc[eligible.Period == period, outcome],
                                    errors="coerce").dropna()
                      if not eligible.empty else pd.Series(dtype=float))
            row.update({f"{prefix} nights": len(values),
                        f"{prefix} mean": values.mean(),
                        f"{prefix} SD": values.std(ddof=1) if len(values) > 1 else np.nan})
        row["Difference"] = row["Changed mean"] - row["Usual mean"]
        rows.append(row)
    return pd.DataFrame(rows)


def comparison_sentences(comparison):
    sentences = []
    for row in comparison.to_dict("records"):
        if pd.isna(row["Difference"]):
            sentences.append(f"{row['Outcome']}: add a dated night with this outcome "
                             "to each period to compare.")
            continue
        direction = "higher" if row["Difference"] > 0 else "lower"
        unit = "rating points" if row["Outcome"] == RATING else "minutes"
        change = (f"{abs(row['Difference']):.1f} {unit} {direction}"
                  if row["Difference"] != 0 else "unchanged")
        sentences.append(f"{row['Outcome']}: the changed-routine average was {change} "
                         f"({row['Usual nights']} usual, {row['Changed nights']} changed nights).")
    return sentences


def save_experiment(experiment):
    portable = deepcopy(experiment)
    portable["saved_model_fingerprints"] = sorted({
        record["model_fingerprint"] for record in portable["recordings"]
        if record["model_fingerprint"] is not None})
    # Predictions are recomputed after reopening, avoiding trust in edited results.
    for record in portable["recordings"]:
        record["stages"] = record["quality"] = record["model_fingerprint"] = None
    content = json.dumps(portable, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(content) > MAX_EXPERIMENT_BYTES:
        raise ValueError("This experiment exceeds the 150 MiB save-file limit.")
    return content


def restore_experiment(content, feature_columns):
    """Rebuild a validated experiment; never execute or trust imported predictions."""
    if not content or len(content) > MAX_EXPERIMENT_BYTES:
        raise ValueError("Choose an experiment file no larger than 150 MiB.")
    try:
        raw = json.loads(content, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported experiment format. Expected version 1.")
        restored = new_experiment()
        update_plan(restored, raw["title"], raw["change"], raw["outcome"])
        subject = raw.get("subject")
        if subject is not None:
            _text(subject, 128, "Participant identifier")
            if not subject or subject != subject.strip():
                raise ValueError("The participant identifier is invalid.")
        # Empty participant-specific plans also need to retain their identity.
        restored["subject"] = subject
        history = raw["outcome_history"]
        if not isinstance(history, list) or len(history) > 1000:
            raise ValueError("Invalid outcome history.")
        for entry in history:
            if (not isinstance(entry, dict) or entry.get("from") not in OUTCOMES
                    or entry.get("to") not in OUTCOMES
                    or type(entry.get("after_review")) is not bool):
                raise ValueError("Invalid outcome history entry.")
            datetime.fromisoformat(entry["time"])
        restored["outcome_history"] = history
        if type(raw["reviewed"]) is not bool or not isinstance(raw["recordings"], list):
            raise ValueError("Invalid experiment metadata.")
        restored["reviewed"] = raw["reviewed"]
        # Version 1 remains readable. New optional fields keep a portable backup
        # useful without trusting its computed predictions.
        from app.journey import HABITS, set_night_context
        if raw.get("habit_id") not in (None, *HABITS):
            raise ValueError("Unknown routine.")
        if raw.get("phase", "usual") not in ("usual", "changed", "complete"):
            raise ValueError("Invalid experiment phase.")
        if raw.get("decision") not in (None, "Keep this routine", "Try a different routine"):
            raise ValueError("Invalid saved decision.")
        restored.update(habit_id=raw.get("habit_id"), phase=raw.get("phase", "usual"),
                        decision=raw.get("decision"))
        if raw.get("change_started_on") is not None:
            started = date.fromisoformat(raw["change_started_on"])
            if started > date.today():
                raise ValueError("A routine start date cannot be in the future.")
            restored["change_started_on"] = started.isoformat()
        decision_history = raw.get("decision_history", [])
        if not isinstance(decision_history, list) or len(decision_history) > 1000:
            raise ValueError("Invalid decision history.")
        for entry in decision_history:
            if not isinstance(entry, dict) or entry.get("decision") not in ("Keep this routine", "Try a different routine"):
                raise ValueError("Invalid prior decision.")
            _text(entry["reason"], 1000, "Decision revision")
            datetime.fromisoformat(entry["time"])
        # Imported choices are the user's history, but their copied numerical
        # comparisons are not trusted model results. Whitelist the diary fields
        # and regenerate estimates before displaying a new comparison.
        restored["decision_history"] = [
            {key: entry[key] for key in ("decision", "reason", "time")}
            for entry in decision_history
        ]
        seen = set()
        total = 0
        for saved in raw["recordings"]:
            frame = record_frame(saved)
            total += len(frame)
            if total > MAX_ROWS:
                raise ValueError("An experiment can contain at most 100,000 epochs.")
            frame = validate_frame(frame, feature_columns)
            pairs = frame[EPOCH_KEY[:2]].drop_duplicates()
            if len(pairs) != 1:
                raise ValueError("Each stored recording must contain exactly one recording.")
            subject, recording = pairs.iloc[0].tolist()
            if (subject != saved["subject"] or recording != saved["recording"]
                    or subject != raw["subject"] or recording in seen):
                raise ValueError("Recording identity is inconsistent or duplicated.")
            seen.add(recording)
            merge_recordings(restored, frame, subject, feature_columns)
            set_diary(restored["recordings"][-1], saved["date"], saved["period"],
                      saved["rating"], saved["notes"])
            set_night_context(restored["recordings"][-1], saved.get("context", []),
                              saved.get("adherence"))
        dates = [r["date"] for r in restored["recordings"] if r["date"]]
        if len(set(dates)) != len(dates):
            raise ValueError("Use one complete recording per night date.")
        return restored
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, OverflowError) as exc:
        raise ValueError("This is not a valid saved experiment.") from exc


def export_csv(frame):
    """Protect free text when a user opens an exported CSV in a spreadsheet."""
    safe = frame.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(
            lambda value: "'" + value if isinstance(value, str)
            and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) else value)
    return safe.to_csv(index=False).encode("utf-8-sig")


def prediction_table(experiment):
    frames = []
    for record in experiment["recordings"]:
        if record["stages"]:
            frame = record_frame(record)
            frame = frame[EPOCH_KEY + [c for c in ("Row_ID", "Upload_Row_ID") if c in frame]]
            frame["Predicted stage"] = record["stages"]
            frame["Model fingerprint"] = record["model_fingerprint"]
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def render_report(experiment, fingerprint):
    nights = nightly_table(experiment)
    comparison = compare_periods(nights)
    history = pd.DataFrame(experiment["outcome_history"])
    summaries = "".join(f"<li>{escape(s)}</li>" for s in comparison_sentences(comparison))
    from app.insights import describe_experiment
    insight = describe_experiment(experiment)
    sensitivity = insight["sensitivity"]
    reduced = sensitivity["primary"]
    sensitivity_text = (f"Unflagged comparison: {reduced['difference']:+.1f} {reduced['unit']} "
                        f"({reduced['usual_count']} usual, {reduced['changed_count']} changed nights)."
                        if reduced["difference"] is not None else "Not enough unflagged nights in both periods.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Nightjar comparison</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#183b3a;max-width:1100px;margin:40px auto;padding:24px}}
h1,h2{{line-height:1.2}}table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border:1px solid #ccd9d4;padding:8px;text-align:left}}th{{background:#edf3ef}}
.note{{background:#f4f3ed;padding:18px}}@media print{{body{{margin:0;padding:0}}table{{font-size:9px}}}}
</style></head><body><p>NIGHTJAR · PERSONAL SLEEP EXPERIMENT</p>
<h1>{escape(experiment['title'] or 'Untitled experiment')}</h1>
<p>{escape(experiment['change'])}</p>
<p><b>Main outcome:</b> {escape(experiment['outcome'])}</p>
<div class="note">Measurements are CRF estimates. Morning restfulness is self-reported.
These comparisons describe observed differences, not proof that a routine caused a change.
Brief stage changes may be missed. One night per period is a two-night comparison only.</div>
<h2>Period comparison</h2><ul>{summaries}</ul>
<h2>{escape(insight['headline'])}</h2><p>{escape(insight['body'])}</p>
<p>{escape(insight['consistency']['label'])}</p>
<p>{escape(sensitivity['headline'])} {escape(sensitivity_text)}</p>
<p>The main comparison keeps all nights. The second view excludes tagged unusual nights
and changed-routine nights marked as not following the plan.</p>
<p>Next step: {escape(insight['next_action'])}</p>
<p>Your decision: {escape(experiment.get('decision') or 'Still exploring')}</p>
{comparison.round(2).to_html(index=False, escape=True, na_rep='Unavailable')}
<p>Difference = changed minus usual. Each night has equal weight.
SD describes variation between nights and needs at least two valid nights.
Only dated, assigned nights enter comparisons; missing outcomes are excluded separately.</p>
<h2>Nightly measurements and diary</h2>
{nights.round(2).to_html(index=False, escape=True, na_rep='Unavailable')}
<h2>Main outcome changes</h2>
{history.to_html(index=False, escape=True) if not history.empty else '<p>No outcome changes recorded.</p>'}
<p>Model and preprocessor SHA-256: {escape(fingerprint)}</p>
<p>Estimated sleep is 0.5 minutes per non-W epoch. Wake during sleep counts W epochs
between the first and last non-W epochs; it is unavailable if no sleep is predicted.</p>
</body></html>"""
