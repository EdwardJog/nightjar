"""Automatic local saving with one active, participant-specific workspace.

The SQLite file belongs to this installation, so browser tabs on the same
computer share it. It is not an account system or a store for public hosting.
Only this internal store retains computed stages; imported backups still pass
through the separate experiment import validation.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4
from app.runtime import session_mode


MAX_WORKSPACE_BYTES = 200 * 1024 * 1024
WORKSPACE_SCHEMA_VERSION = 2


class StorageError(RuntimeError):
    """The local workspace could not be safely read or saved."""


class StorageConflict(StorageError):
    """Another tab saved or cleared the workspace after it was loaded."""


def get_store_path():
    """Return the database path without creating a file or directory."""
    directory = os.environ.get("NIGHTJAR_DATA_DIR")
    base = Path(directory).expanduser() if directory else Path(__file__).parent / ".local"
    return base.resolve() / "nightjar.sqlite3"


def _connect():
    if session_mode():
        raise StorageError("Disk storage is disabled for hosted sessions.")
    path = get_store_path()
    connection = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS workspace (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                revision INTEGER NOT NULL CHECK (revision >= 0),
                payload TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS saved_workspaces (
                space_id TEXT PRIMARY KEY,
                subject TEXT UNIQUE,
                name TEXT NOT NULL,
                recordings INTEGER NOT NULL,
                revision INTEGER NOT NULL,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        return connection
    except (OSError, sqlite3.Error) as exc:
        if connection is not None:
            connection.close()
        raise StorageError("Your local save could not be opened. Check the data folder.") from exc


def _revision(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StorageError("The saved workspace revision is invalid.")
    return value


def _validate_workspace(workspace):
    """Check the small container, without reprocessing every EEG measurement."""
    if not isinstance(workspace, dict):
        raise StorageError("The saved workspace must be an object.")
    if workspace.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
        raise StorageError("This workspace uses an unsupported format.")
    profile = workspace.get("profile")
    if not isinstance(profile, dict):
        raise StorageError("The saved profile is invalid.")
    for key, limit in (("name", 120), ("device", 240), ("goal", 2000)):
        if key in profile and (not isinstance(profile[key], str) or len(profile[key]) > limit):
            raise StorageError("The saved profile contains an invalid field.")
    experiments = workspace.get("experiments")
    if not isinstance(experiments, list) or len(experiments) > 1000:
        raise StorageError("The saved experiment list is invalid.")
    identifiers = set()
    for experiment in experiments:
        if not isinstance(experiment, dict):
            raise StorageError("A saved experiment is invalid.")
        identity = experiment.get("id")
        if not isinstance(identity, str) or not identity or len(identity) > 128:
            raise StorageError("A saved experiment needs a valid identifier.")
        if identity in identifiers:
            raise StorageError("The saved workspace contains duplicate experiment identifiers.")
        identifiers.add(identity)
        recordings = experiment.get("recordings")
        if not isinstance(recordings, list) or len(recordings) > 10000:
            raise StorageError("A saved recording list is invalid.")
        if any(not isinstance(recording, dict) for recording in recordings):
            raise StorageError("A saved recording is invalid.")
    active = workspace.get("active_experiment")
    if active is not None and (not isinstance(active, str) or active not in identifiers):
        raise StorageError("The active experiment could not be found in the saved workspace.")
    if "revision" in workspace:
        _revision(workspace["revision"])
    identity = workspace.get("space_id")
    if identity is not None and (not isinstance(identity, str) or not identity or len(identity) > 128):
        raise StorageError("The saved space identifier is invalid.")


def _json_scalar(value):
    # Summary calculations can return NumPy scalars. Avoid importing the
    # scientific stack simply to save a profile or check an existing revision.
    if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
        result = value.item()
        if result is not value:
            return result
    raise TypeError("Workspace values must be JSON-compatible.")


def _encode_workspace(workspace):
    _validate_workspace(workspace)
    try:
        payload = json.dumps(workspace, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":"), default=_json_scalar)
        if len(payload.encode("utf-8")) > MAX_WORKSPACE_BYTES:
            raise StorageError("Your workspace is too large to save locally (200 MiB limit).")
        return payload
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise StorageError("Your workspace contains a value that could not be saved.") from exc


def _reject_nonfinite(_):
    raise ValueError("Non-finite numbers are not part of the saved format.")


def _decode_workspace(payload, revision, updated_at):
    if not isinstance(payload, str):
        raise StorageError("The local save could not be read. Its JSON content is invalid.")
    try:
        if len(payload.encode("utf-8")) > MAX_WORKSPACE_BYTES:
            raise StorageError("The saved workspace exceeds the supported size.")
        workspace = json.loads(payload, parse_constant=_reject_nonfinite)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise StorageError("The local save could not be read. Its JSON content is invalid.") from exc
    _validate_workspace(workspace)
    if workspace.get("revision") != revision or workspace.get("updated_at") != updated_at:
        raise StorageError("The local save's revision information is inconsistent.")
    return workspace


def load_workspace_snapshot():
    """Return (workspace or None, revision) from one consistent database read.

    Use this on startup or after a reset. An empty store can have a nonzero
    revision because deleting a workspace must also invalidate older tabs.
    """
    if session_mode():
        from app import session_storage
        return session_storage.load_workspace_snapshot()
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT revision, payload, updated_at FROM workspace WHERE id = 1"
        ).fetchone()
        if row is None:
            return None, 0
        revision, payload, updated_at = row
        _revision(revision)
        if payload is None:
            return None, revision
        return _decode_workspace(payload, revision, updated_at), revision
    except sqlite3.Error as exc:
        raise StorageError("Your local save could not be read.") from exc
    finally:
        connection.close()


def load_workspace():
    """Return the saved workspace, including its revision, or None."""
    workspace, _ = load_workspace_snapshot()
    return workspace


def save_workspace(workspace, expected_revision=None):
    """Save atomically and return a new revision, without mutating the argument.

    By default the expected revision comes from workspace['revision'], or 0 for
    a new workspace. Assign the returned revision to in-memory state after a
    successful save. A stale tab always raises StorageConflict.
    """
    if session_mode():
        from app import session_storage
        return session_storage.save_workspace(workspace, expected_revision)
    if not isinstance(workspace, dict):
        raise StorageError("The workspace must be an object.")
    expected = _revision(workspace.get("revision", 0) if expected_revision is None
                         else expected_revision)
    revision = expected + 1
    updated_at = datetime.now(timezone.utc).isoformat()
    saved = {**workspace, "revision": revision, "updated_at": updated_at}
    payload = _encode_workspace(saved)
    connection = _connect()
    try:
        # The write lock covers both the revision check and replacement. Two
        # tabs cannot both pass a check against the same previous revision.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT revision, payload, updated_at FROM workspace WHERE id = 1"
        ).fetchone()
        current = row[0] if row else 0
        if current != expected:
            raise StorageConflict(
                "This workspace changed in another tab. Reload the saved version before continuing."
            )
        if row and row[1] is not None:
            _decode_workspace(row[1], row[0], row[2])
        connection.execute("""
            INSERT INTO workspace (id, revision, payload, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                revision = excluded.revision,
                payload = excluded.payload,
                updated_at = excluded.updated_at
        """, (revision, payload, updated_at))
        connection.commit()
        return revision
    except sqlite3.Error as exc:
        raise StorageError("Your changes could not be saved. The previous save is intact.") from exc
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def _subject(workspace):
    """Older saves can identify the participant only inside an experiment."""
    subjects = {str(experiment["subject"]) for experiment in workspace["experiments"]
                if experiment.get("subject") is not None}
    if workspace.get("subject") is not None:
        subjects.add(str(workspace["subject"]))
    if len(subjects) > 1:
        raise StorageError("A saved space contains more than one participant.")
    return next(iter(subjects), None)


def _checked_current(connection, expected_revision):
    row = connection.execute(
        "SELECT revision, payload, updated_at FROM workspace WHERE id = 1"
    ).fetchone()
    current = row[0] if row else 0
    if current != expected_revision:
        raise StorageConflict(
            "This workspace changed in another tab. Reload the saved version before switching spaces."
        )
    return (_decode_workspace(row[1], row[0], row[2])
            if row and row[1] is not None else None)


def _archive_current(connection, workspace):
    if workspace is None:
        return
    archived = {**workspace, "space_id": workspace.get("space_id") or uuid4().hex}
    connection.execute("""
        INSERT INTO saved_workspaces
            (space_id, subject, name, recordings, revision, payload, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (archived["space_id"], _subject(archived), archived["profile"].get("name", ""),
          sum(len(experiment["recordings"]) for experiment in archived["experiments"]),
          archived["revision"], _encode_workspace(archived), archived["updated_at"]))


def _activate(connection, workspace, revision):
    saved = {**workspace, "revision": revision,
             "updated_at": datetime.now(timezone.utc).isoformat()}
    payload = _encode_workspace(saved)
    connection.execute("""
        INSERT INTO workspace (id, revision, payload, updated_at)
        VALUES (1, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET revision = excluded.revision,
            payload = excluded.payload, updated_at = excluded.updated_at
    """, (revision, payload, saved["updated_at"]))
    # Return JSON-normalised values, matching a fresh session's load.
    return _decode_workspace(payload, revision, saved["updated_at"])


def list_saved_workspaces():
    """List inactive spaces without loading their private measurement payloads."""
    if session_mode():
        from app import session_storage
        return session_storage.list_saved_workspaces()
    connection = _connect()
    try:
        rows = connection.execute("""
            SELECT space_id, subject, name, recordings, updated_at
            FROM saved_workspaces ORDER BY updated_at DESC, space_id
        """).fetchall()
        return [dict(zip(("space_id", "subject", "name", "recordings", "updated_at"), row))
                for row in rows]
    except sqlite3.Error as exc:
        raise StorageError("Your other saved spaces could not be listed.") from exc
    finally:
        connection.close()


def create_separate_workspace(new_workspace, expected_revision):
    """Archive the current space and activate a new empty participant space.

    The caller supplies its copied profile and clean routine. Existing recordings
    may never be carried into this operation. One global revision protects all
    spaces from stale tabs, and both changes commit or roll back together.
    """
    if session_mode():
        from app import session_storage
        return session_storage.create_separate_workspace(new_workspace, expected_revision)
    expected = _revision(expected_revision)
    _validate_workspace(new_workspace)
    if any(experiment["recordings"] for experiment in new_workspace["experiments"]):
        raise StorageError("A new participant space must start without recordings.")
    subject = _subject(new_workspace)
    if subject is None:
        raise StorageError("Choose a participant for the separate space.")
    new = {**new_workspace, "space_id": uuid4().hex, "subject": subject}
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _checked_current(connection, expected)
        if current is not None and _subject(current) == subject:
            raise StorageError("This participant already has the active space.")
        if connection.execute("SELECT 1 FROM saved_workspaces WHERE subject = ?", (subject,)).fetchone():
            raise StorageError("This participant already has a saved space. Open it to continue.")
        _archive_current(connection, current)
        saved = _activate(connection, new, expected + 1)
        connection.commit()
        return saved
    except sqlite3.Error as exc:
        raise StorageError("Spaces could not be switched. Your previous space is intact.") from exc
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def activate_saved_workspace(space_id, expected_revision):
    """Swap an inactive saved space with the active one in a single transaction."""
    if session_mode():
        from app import session_storage
        return session_storage.activate_saved_workspace(space_id, expected_revision)
    expected = _revision(expected_revision)
    if not isinstance(space_id, str) or not space_id or len(space_id) > 128:
        raise StorageError("Choose a valid saved space.")
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = _checked_current(connection, expected)
        row = connection.execute("""
            SELECT revision, payload, updated_at FROM saved_workspaces WHERE space_id = ?
        """, (space_id,)).fetchone()
        if row is None:
            raise StorageError("This saved space is no longer available. Reload before continuing.")
        target = _decode_workspace(row[1], row[0], row[2])
        if target.get("space_id") != space_id:
            raise StorageError("The saved space identifier does not match its contents.")
        _archive_current(connection, current)
        connection.execute("DELETE FROM saved_workspaces WHERE space_id = ?", (space_id,))
        saved = _activate(connection, target, expected + 1)
        connection.commit()
        return saved
    except sqlite3.Error as exc:
        raise StorageError("Spaces could not be switched. Your previous space is intact.") from exc
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def clear_workspace(expected_revision):
    """Delete all active and inactive spaces; retain an increasing revision.

    The resulting tombstone contains no profile, recordings or predictions.
    Return its revision for the next onboarding save. SQLite secure_delete
    clears deleted payload bytes from database pages as well.
    """
    if session_mode():
        from app import session_storage
        return session_storage.clear_workspace(expected_revision)
    expected = _revision(expected_revision)
    connection = _connect()
    try:
        connection.execute("PRAGMA secure_delete = ON")
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT revision FROM workspace WHERE id = 1").fetchone()
        current = row[0] if row else 0
        if current != expected:
            raise StorageConflict(
                "This workspace changed in another tab. Reload it before deleting the local data."
            )
        revision = current + 1
        connection.execute("DELETE FROM saved_workspaces")
        connection.execute("""
            INSERT INTO workspace (id, revision, payload, updated_at)
            VALUES (1, ?, NULL, ?)
            ON CONFLICT (id) DO UPDATE SET
                revision = excluded.revision,
                payload = NULL,
                updated_at = excluded.updated_at
        """, (revision, datetime.now(timezone.utc).isoformat()))
        connection.commit()
        return revision
    except sqlite3.Error as exc:
        raise StorageError("The local data could not be cleared.") from exc
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
