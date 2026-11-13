
import sqlite3
import uuid

from datetime import datetime,timedelta
from pathlib import Path


# =====================================================
# PROJECT CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATABASE = (
    PROJECT_ROOT / "data" / "reconciliation.db"
)

ALLOWED_ROLES = {
    "OPS_ANALYST",
    "RISK_COMPLIANCE_REVIEWER",
    "SYSTEM_ADMIN"
}


# =====================================================
# DATABASE CONNECTION
# =====================================================

def connect_database(database_path=DEFAULT_DATABASE):

    database_path = Path(database_path)

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}"
        )

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    ensure_schema(connection)

    return connection


# =====================================================
# DATABASE MIGRATION
# =====================================================

def ensure_schema(connection):

    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(exceptions)"
        )
    }

    if "assigned_to_user_id" not in columns:

        connection.execute("""
            ALTER TABLE exceptions
            ADD COLUMN assigned_to_user_id TEXT
            REFERENCES app_users(user_id)
        """)

        connection.commit()


# =====================================================
# HELPERS
# =====================================================

def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def current_timestamp():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def next_event_timestamp(connection, exception_id):

    row = connection.execute("""
        SELECT MAX(event_time)
        FROM (
            SELECT created_at AS event_time
            FROM exception_events
            WHERE exception_id = ?

            UNION ALL

            SELECT created_at AS event_time
            FROM resolutions
            WHERE exception_id = ?
        )
    """, (exception_id, exception_id)).fetchone()

    now = datetime.now()

    last_event = row[0]

    if last_event:

        last_time = datetime.strptime(
            last_event,
            "%Y-%m-%d %H:%M:%S"
        )

        if now <= last_time:
            now = last_time + timedelta(seconds=1)

    return now.strftime("%Y-%m-%d %H:%M:%S")



def new_id(prefix):

    return (
        prefix + "-"
        + uuid.uuid4().hex[:12].upper()
    )


def get_exception(connection, exception_id):

    row = connection.execute("""
        SELECT *
        FROM exceptions
        WHERE exception_id = ?
    """, (exception_id,)).fetchone()

    if row is None:
        raise ValueError(
            f"Exception not found: {exception_id}"
        )

    return row


def require_active_user(
    connection,
    user_id,
    allowed_roles=ALLOWED_ROLES
):

    user = connection.execute("""
        SELECT user_id, display_name, role, is_active
        FROM app_users
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if user is None or user["is_active"] != 1:
        raise ValueError(
            f"User is missing or inactive: {user_id}"
        )

    if user["role"] not in allowed_roles:
        raise ValueError(
            f"User role {user['role']} is not permitted."
        )

    return user


def record_event(
    connection,
    exception_id,
    previous_status,
    new_status,
    action_type,
    actor_user_id,
    notes
):

    connection.execute("""
        INSERT INTO exception_events (
            exception_event_id,
            exception_id,
            previous_status,
            new_status,
            action_type,
            actor_user_id,
            notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        new_id("EXEV"),
        exception_id,
        previous_status,
        new_status,
        action_type,
        actor_user_id,
        notes,
        next_event_timestamp(connection, exception_id)
    ))


# =====================================================
# 1. LIST EXCEPTIONS
# =====================================================

def list_exceptions(
    connection,
    status=None
):

    ensure_schema(connection)

    if status:

        rows = connection.execute("""
            SELECT
                e.*,
                u.display_name AS assigned_to_name
            FROM exceptions e
            LEFT JOIN app_users u
              ON u.user_id = e.assigned_to_user_id
            WHERE e.exception_status = ?
            ORDER BY
                CASE e.severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    ELSE 4
                END,
                e.detected_at
        """, (status,)).fetchall()

    else:

        rows = connection.execute("""
            SELECT
                e.*,
                u.display_name AS assigned_to_name
            FROM exceptions e
            LEFT JOIN app_users u
              ON u.user_id = e.assigned_to_user_id
            ORDER BY e.detected_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


# =====================================================
# 2. ASSIGN EXCEPTION
# =====================================================

def assign_exception(
    connection,
    exception_id,
    assigned_to_user_id,
    actor_user_id,
    notes="Exception assigned for investigation."
):

    ensure_schema(connection)

    actor = require_active_user(
        connection,
        actor_user_id
    )

    assignee = require_active_user(
        connection,
        assigned_to_user_id
    )

    exception = get_exception(
        connection,
        exception_id
    )

    previous_status = exception["exception_status"]

    if previous_status in ("RESOLVED", "CLOSED"):
        raise ValueError(
            "Resolved or closed exceptions cannot be reassigned."
        )

    new_status = "IN_REVIEW"

    with connection:

        connection.execute("""
            UPDATE exceptions
            SET assigned_to_user_id = ?,
                exception_status = ?
            WHERE exception_id = ?
        """, (
            assignee["user_id"],
            new_status,
            exception_id
        ))

        record_event(
            connection,
            exception_id,
            previous_status,
            new_status,
            "ASSIGNED",
            actor["user_id"],
            notes
        )

    return {
        "exception_id": exception_id,
        "assigned_to": assignee["display_name"],
        "status": new_status
    }


# =====================================================
# 3. ADD INVESTIGATION NOTE
# =====================================================

def add_note(
    connection,
    exception_id,
    actor_user_id,
    notes
):

    if not notes or not notes.strip():
        raise ValueError(
            "Investigation notes cannot be empty."
        )

    actor = require_active_user(
        connection,
        actor_user_id
    )

    exception = get_exception(
        connection,
        exception_id
    )

    status = exception["exception_status"]

    if status not in ("OPEN", "IN_REVIEW"):
        raise ValueError(
            "Notes cannot be added to resolved or closed exceptions."
        )

    with connection:

        record_event(
            connection,
            exception_id,
            status,
            status,
            "NOTE_ADDED",
            actor["user_id"],
            notes.strip()
        )

    return {
        "exception_id": exception_id,
        "action": "NOTE_ADDED",
        "status": status
    }


# =====================================================
# 4. RESOLVE EXCEPTION
# =====================================================

def resolve_exception(
    connection,
    exception_id,
    actor_user_id,
    action,
    outcome,
    notes
):

    if not action.strip():
        raise ValueError("Resolution action is required.")

    if not outcome.strip():
        raise ValueError("Resolution outcome is required.")

    if not notes.strip():
        raise ValueError("Resolution notes are required.")

    actor = require_active_user(
        connection,
        actor_user_id
    )

    exception = get_exception(
        connection,
        exception_id
    )

    if exception["exception_status"] != "IN_REVIEW":
        raise ValueError(
            "Exception must be IN_REVIEW before resolution."
        )

    if not exception["assigned_to_user_id"]:
        raise ValueError(
            "Exception must be assigned before resolution."
        )

    
    timestamp = next_event_timestamp(connection, exception_id)

    resolution_id = new_id("RES")

    with connection:

        connection.execute("""
            INSERT INTO resolutions (
                resolution_id,
                exception_id,
                action,
                outcome,
                notes,
                resolved_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            resolution_id,
            exception_id,
            action,
            outcome,
            notes,
            actor["user_id"],
            timestamp
        ))

        connection.execute("""
            UPDATE exceptions
            SET exception_status = 'RESOLVED'
            WHERE exception_id = ?
        """, (exception_id,))

        record_event(
            connection,
            exception_id,
            "IN_REVIEW",
            "RESOLVED",
            "RESOLVED",
            actor["user_id"],
            notes
        )

    return {
        "exception_id": exception_id,
        "resolution_id": resolution_id,
        "status": "RESOLVED"
    }


# =====================================================
# 5. CLOSE RESOLVED EXCEPTION
# =====================================================

def close_exception(
    connection,
    exception_id,
    actor_user_id,
    notes="Resolution verified and exception closed."
):

    actor = require_active_user(
        connection,
        actor_user_id
    )

    exception = get_exception(
        connection,
        exception_id
    )

    if exception["exception_status"] != "RESOLVED":
        raise ValueError(
            "Only resolved exceptions can be closed."
        )

    
    timestamp = next_event_timestamp(connection, exception_id)

    with connection:

        connection.execute("""
            UPDATE exceptions
            SET exception_status = 'CLOSED',
                closed_at = ?
            WHERE exception_id = ?
        """, (
            timestamp,
            exception_id
        ))

        record_event(
            connection,
            exception_id,
            "RESOLVED",
            "CLOSED",
            "CLOSED",
            actor["user_id"],
            notes
        )

    return {
        "exception_id": exception_id,
        "status": "CLOSED"
    }


# =====================================================
# 6. VIEW EXCEPTION HISTORY
# =====================================================

def get_exception_history(
    connection,
    exception_id
):

    get_exception(
        connection,
        exception_id
    )

    rows = connection.execute("""
        SELECT
            e.exception_event_id,
            e.previous_status,
            e.new_status,
            e.action_type,
            e.notes,
            e.created_at,
            u.display_name AS actor_name
        FROM exception_events e
        LEFT JOIN app_users u
          ON u.user_id = e.actor_user_id
        WHERE e.exception_id = ?
        ORDER BY e.created_at, e.exception_event_id
    """, (exception_id,)).fetchall()

    return [dict(row) for row in rows]
