"""Data controls that remain available without loading the prediction model."""
import streamlit as st
from app.runtime import session_mode, saving_notice, delete_label, delete_notice, reset_interface

from app.experiments import save_experiment
from app.storage import clear_workspace, load_workspace_snapshot, StorageError


def render_model_recovery(workspace, *, go):
    """Offer a safe route out, portable backups and revision-checked deletion."""
    st.info("Your saved routines and recordings are still available. Restore the model files "
            "and retry, or use the data controls below.")
    retry, welcome = st.columns(2)
    if retry.button("Retry model check", key="recovery_retry", type="primary", width="stretch"):
        st.rerun()
    if welcome.button("Back to welcome", key="recovery_welcome", width="stretch"):
        go("Welcome")

    experiments = workspace.get("experiments", []) if workspace else []
    if experiments:
        st.subheader("Back up a routine")
        st.caption("This portable copy keeps its measurements, check-ins and choices. "
                   "Its predictions must be regenerated after import.")
        choices = {experiment["id"]: experiment for experiment in experiments}
        identifiers = list(choices)
        active = workspace.get("active_experiment")
        selected = st.selectbox(
            "Routine to back up", identifiers,
            index=identifiers.index(active) if active in choices else 0,
            format_func=lambda identity: choices[identity]["title"] or "Untitled routine",
            key="recovery_backup_routine",
        )
        try:
            content = save_experiment(choices[selected])
            st.download_button(
                "Download routine backup", content, "nightjar_experiment.json",
                "application/json", key="recovery_backup",
            )
        except (ValueError, TypeError, RecursionError) as exc:
            st.error(f"This routine could not be exported: {exc}")

    st.divider()
    st.subheader("Delete session data" if session_mode() else "Delete local data")
    st.write(delete_notice())
    confirm = st.checkbox(
        "Delete all profiles, recordings, experiments and decisions",
        help=delete_notice(),
        key="recovery_delete_confirm",
    )
    if st.button(delete_label(), disabled=not confirm, key="recovery_delete"):
        try:
            clear_workspace(expected_revision=st.session_state.store_revision)
            reset_interface()
            go("Welcome")
        except (StorageError, OSError) as exc:
            st.session_state.model_recovery_error = str(exc)

    if st.session_state.get("model_recovery_error"):
        st.error(st.session_state.model_recovery_error)
        st.caption("Reload the saved data before trying again if another tab changed it.")
        if st.button("Reload saved data", key="recovery_reload"):
            try:
                saved, revision = load_workspace_snapshot()
                # Drop stale upload/widget state together with the old workspace.
                reset_interface()
                st.session_state.workspace = saved
                st.session_state.store_revision = revision
                go("Welcome")
            except (StorageError, OSError) as exc:
                st.session_state.model_recovery_error = str(exc)
                st.rerun()
