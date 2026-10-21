"""Real feature uploads, participant selection and atomic night analysis."""
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import streamlit as st

from app.experiments import new_experiment, merge_recordings, record_frame
from app.inference import read_feature_csv, predict_frame
from app.journey import active_experiment, invalidate_decision
from app.storage import (
    StorageError, StorageConflict, create_separate_workspace, activate_saved_workspace,
    list_saved_workspaces,
)


def clear_upload_selection():
    """Forget a previous space's upload choices after a successful restore."""
    for key in list(st.session_state):
        if key.startswith(("upload_participant_", "upload_recordings_")) or key in {
                "pending_frame", "upload_digest", "selected_recording", "feature_upload"}:
            st.session_state.pop(key, None)


def _empty_participant_space(workspace, subject):
    """Copy the chosen plan, never another person's nights or conclusions."""
    previous = active_experiment(workspace)
    experiment = new_experiment()
    experiment.update(
        id=uuid4().hex, habit_id=previous.get("habit_id"), phase="usual",
        title=previous["title"], change=previous["change"], outcome=previous["outcome"],
        subject=str(subject), decision=None, decision_note="", context_version=1,
    )
    return {"schema_version": 2, "revision": 0, "profile": deepcopy(workspace["profile"]),
            "subject": str(subject), "active_experiment": experiment["id"],
            "experiments": [experiment]}


def _use_space(saved, subject, go):
    # Keep the checked upload in this flow, so switching people does not require
    # selecting the file again. The participant-specific widget keys separate
    # each person's recording selection.
    st.session_state.workspace = saved
    st.session_state.store_revision = saved["revision"]
    st.session_state.pop("selected_recording", None)
    st.session_state.pop("save_error", None)
    st.session_state.notice = f"Participant {subject}'s separate space is ready."
    go("Add night")


def render_add_night(workspace, *, go, persist, get_bundle):
    """Render real uploads; the caller handles the separate illustrative demo."""
    if st.button("← Back to Night log", type="tertiary"):
        go("Night log")
    st.caption("NIGHT LOG / ADD A NIGHT")
    experiment = active_experiment(workspace)
    if experiment is None:
        st.info("Choose a routine before adding recordings.")
        if st.button("Choose my routine"):
            go("Choose routine")
        return
    st.title("Log a night")
    st.write("Add your recording, then its date and how you felt. It will appear in your "
             "Night log and routine progress automatically.")
    try:
        bundle = get_bundle()
    except (OSError, ValueError, RuntimeError) as exc:
        st.error(f"The saved model could not be opened: {exc}")
        return

    feature_columns = bundle.preprocessor["feature_columns"]
    requirements = [
        "Use a CSV of extracted EEG measurements, not raw EEG or predicted stages. "
        "For the assignment walkthrough, test.csv has the required format.",
        f"Include Subject_ID, Recording_ID, Epoch_ID and {len(feature_columns)} measurement "
        "columns. The template below lists their exact names. Each row is 30 seconds. "
        "Epoch_ID must start at 1 and stay consecutive within each recording.",
        "Missing measurements use the saved preprocessing; extra columns and labels are "
        "excluded. Limits: 100 MiB per file, 10,000 epochs per recording and 100,000 per routine.",
        "Selecting a device in setup does not connect it or make its raw export compatible.",
    ]
    # One native button supplies hover help and a keyboard/touch-accessible guide.
    with st.popover("File requirements", type="tertiary", help="\n\n".join(requirements)):
        for paragraph in requirements:
            st.write(paragraph)
        st.download_button(
            "Download column template",
            ",".join(["Subject_ID", "Recording_ID", "Epoch_ID", *feature_columns]) + "\n",
            "nightjar_feature_columns.csv", "text/csv", type="tertiary",
        )
    upload = st.file_uploader("Choose an EEG feature CSV", type=["csv"],
                              key="feature_upload")
    if upload is None:
        st.session_state.pop("pending_frame", None)
        st.session_state.pop("upload_digest", None)
        return

    content = upload.getvalue()
    digest = sha256(content).hexdigest()
    if st.session_state.get("upload_digest") != digest:
        st.session_state.pop("pending_frame", None)
        st.session_state.pop("upload_digest", None)
        try:
            with st.spinner("Checking your recordings..."):
                st.session_state.pending_frame = read_feature_csv(content, feature_columns)
            st.session_state.upload_digest = digest
        except ValueError as exc:
            st.error(str(exc))
            return
    pending = st.session_state.get("pending_frame")
    if pending is None:
        return

    subjects = pending.Subject_ID.unique().tolist()
    existing = workspace.get("subject") or experiment.get("subject")
    default_index = subjects.index(existing) if existing in subjects else 0
    subject = st.selectbox(
        "Which participant is you?", subjects, index=default_index,
        key=f"upload_participant_{digest}",
    )
    if existing is not None and subject != existing:
        st.info(f"This space holds participant {existing}'s nights. Participant {subject} "
                "needs a separate space so their results stay separate. Your current nights "
                "will be kept, and you can return to them in Settings.")
        try:
            saved_space = next((space for space in list_saved_workspaces()
                                if space["subject"] == subject), None)
            label = ("Open this participant's saved space" if saved_space
                     else "Use a separate space")
            if st.button(label, type="primary"):
                if saved_space:
                    saved = activate_saved_workspace(
                        saved_space["space_id"],
                        expected_revision=st.session_state.store_revision,
                    )
                else:
                    saved = create_separate_workspace(
                        _empty_participant_space(workspace, subject),
                        expected_revision=st.session_state.store_revision,
                    )
                _use_space(saved, subject, go)
        except StorageConflict as exc:
            # Reuse the app's explicit discard/reload recovery. Retrying with the
            # stale revision can never succeed and must not replace another tab.
            st.session_state.save_error = str(exc)
            st.rerun()
        except (StorageError, OSError) as exc:
            st.error(f"We couldn't switch spaces: {exc}")
        return

    if existing is not None:
        st.caption(f"This space keeps participant {existing}'s nights together. "
                   "Choose another participant above to open a separate saved space.")
    else:
        st.caption("Choose your participant ID. Only that person's recordings will be added.")
    chosen = pending.loc[pending.Subject_ID == subject]
    recordings = chosen.Recording_ID.unique().tolist()
    selected = st.multiselect("Recordings to add", recordings, default=recordings,
                              key=f"upload_recordings_{digest}_{subject}")
    st.caption(f"{len(selected)} recording(s) for participant {subject}. "
               "Add their dates after analysis.")
    replace = (st.checkbox("Replace matching recordings if their measurements changed")
               if any(record["recording"] in selected for record in experiment["recordings"])
               else False)
    if st.button("Analyse & add nights", type="primary", disabled=not selected):
        candidate = deepcopy(experiment)
        try:
            added, replaced, _ = merge_recordings(
                candidate, chosen.loc[chosen.Recording_ID.isin(selected)],
                subject, feature_columns, replace,
            )
            todo = [record for record in candidate["recordings"]
                    if not record.get("stages") or record.get("model_fingerprint") != bundle.fingerprint]
            progress = st.progress(0, text="Reading your nights...")
            for index, record in enumerate(todo):
                predictions, quality = predict_frame(record_frame(record), bundle)
                record.update(stages=predictions["Predicted stage"].tolist(),
                              quality=quality.iloc[0].to_dict(), model_fingerprint=bundle.fingerprint)
                progress.progress((index + 1) / len(todo),
                                  text=f"Analysed {index + 1} of {len(todo)} nights")
            if added or replaced or todo:
                invalidate_decision(candidate, "Recordings were added or reanalysed.")
            experiment.clear()
            experiment.update(candidate)
            workspace["subject"] = subject
            st.session_state.selected_recording = selected[0]
            st.session_state.pop("pending_frame", None)
            st.session_state.pop("upload_digest", None)
            persist("Recording saved. Add its date to finish logging the night.", "Night detail")
        except (ValueError, RuntimeError) as exc:
            st.error(f"We couldn't add these recordings: {exc}")
