"""Explicit storage policy for the local app and the hosted demonstration."""
import os


def session_mode():
    mode = os.environ.get("NIGHTJAR_STORAGE_MODE", "local")
    if mode not in {"local", "session"}:
        raise RuntimeError("NIGHTJAR_STORAGE_MODE must be local or session.")
    return mode == "session"


def saving_notice():
    if session_mode():
        return ("Temporary browser session. Uploads are processed on the server. "
                "Refreshing, disconnecting or restarting may clear your progress. "
                "Download a routine backup in Settings to keep it.")
    return "No account. No subscription. Saved automatically on this computer."


def delete_label():
    return "Delete all session spaces" if session_mode() else "Delete all local spaces"


def delete_notice():
    if session_mode():
        return ("Remove all profiles, recordings, experiments and decisions from this browser session. "
                "Other visitors are unaffected. Downloaded copies must be removed separately.")
    return ("This computer stores your active space and other participant spaces, shared by its browsers. "
            "Closing the app keeps them. Deletion removes all local spaces; exported copies and "
            "computer backups must be removed separately.")


def reset_interface():
    """Discard stale widget state without losing this session's backing store."""
    import streamlit as st
    from app.session_storage import STORE_KEY
    saved = st.session_state.get(STORE_KEY)
    st.session_state.clear()
    if session_mode() and saved is not None:
        st.session_state[STORE_KEY] = saved
