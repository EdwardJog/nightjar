"""Temporary persistence scoped exclusively to Streamlit's current session.

No personal payload is written to disk or placed in a process-wide cache.
JSON snapshots prevent UI mutations from changing the committed save.
"""
from datetime import datetime, timezone
from uuid import uuid4
import streamlit as st
from app import storage as local

STORE_KEY = "_nightjar_private_store"


def _store():
    return st.session_state.get(STORE_KEY, {"revision": 0, "active": None, "archived": {}})


def _copy(workspace):
    if workspace is None:
        return None
    return local._decode_workspace(local._encode_workspace(workspace),
                                   workspace["revision"], workspace["updated_at"])


def _checked(expected):
    store = _store()
    if local._revision(expected) != store["revision"]:
        raise local.StorageConflict("This session changed. Reload its saved version before continuing.")
    return store


def load_workspace_snapshot():
    store = _store()
    return _copy(store["active"]), store["revision"]


def _commit(store, workspace, archived=None):
    revision = store["revision"] + 1
    saved = _copy({**workspace, "revision": revision,
                   "updated_at": datetime.now(timezone.utc).isoformat()}) if workspace is not None else None
    st.session_state[STORE_KEY] = {"revision": revision, "active": saved,
                                 "archived": store["archived"] if archived is None else archived}
    return _copy(saved), revision


def save_workspace(workspace, expected_revision=None):
    local._validate_workspace(workspace)
    expected = workspace.get("revision", 0) if expected_revision is None else expected_revision
    return _commit(_checked(expected), workspace)[1]


def list_saved_workspaces():
    rows = [{"space_id": identity, "subject": local._subject(space),
             "name": space["profile"].get("name", ""),
             "recordings": sum(len(e["recordings"]) for e in space["experiments"]),
             "updated_at": space["updated_at"]}
            for identity, space in _store()["archived"].items()]
    return sorted(rows, key=lambda row: row["updated_at"], reverse=True)


def _archive(store):
    archived = dict(store["archived"])
    if store["active"] is not None:
        current = _copy(store["active"])
        current["space_id"] = current.get("space_id") or uuid4().hex
        archived[current["space_id"]] = current
    return archived


def create_separate_workspace(new_workspace, expected_revision):
    local._validate_workspace(new_workspace)
    store = _checked(expected_revision)
    subject = local._subject(new_workspace)
    if subject is None or any(e["recordings"] for e in new_workspace["experiments"]):
        raise local.StorageError("Choose a participant and start their space without recordings.")
    spaces = list(store["archived"].values()) + ([store["active"]] if store["active"] else [])
    if any(local._subject(space) == subject for space in spaces):
        raise local.StorageError("This participant already has a space. Open it to continue.")
    new = {**new_workspace, "space_id": uuid4().hex, "subject": subject}
    return _commit(store, new, _archive(store))[0]


def activate_saved_workspace(space_id, expected_revision):
    store = _checked(expected_revision)
    if not isinstance(space_id, str) or space_id not in store["archived"]:
        raise local.StorageError("Choose an available saved space.")
    target = store["archived"][space_id]
    archived = _archive(store)
    del archived[space_id]
    return _commit(store, target, archived)[0]


def clear_workspace(expected_revision):
    return _commit(_checked(expected_revision), None, {})[1]
