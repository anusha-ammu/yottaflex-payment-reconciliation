
import shutil
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src")
)

from exceptions.workflow import (
    connect_database,
    assign_exception,
    add_note,
    resolve_exception,
    close_exception,
    get_exception_history
)


def test_complete_exception_lifecycle(tmp_path):

    # Create a temporary database copy.
    source = (
        PROJECT_ROOT
        / "data"
        / "reconciliation_anomaly_test.db"
    )

    test_db = tmp_path / "workflow_test.db"

    shutil.copy2(source, test_db)

    connection = connect_database(test_db)

    try:

        # Find the fee discrepancy exception.
        row = connection.execute("""
            SELECT exception_id
            FROM exceptions
            WHERE exception_type = 'FEE_VARIANCE'
            LIMIT 1
        """).fetchone()

        assert row is not None

        exception_id = row["exception_id"]

        # 1. Assign exception.
        result = assign_exception(
            connection,
            exception_id,
            "USR-OPS-001",
            "USR-ADMIN-001",
            "Assigned for investigation."
        )

        assert result["status"] == "IN_REVIEW"

        # 2. Add investigation note.
        result = add_note(
            connection,
            exception_id,
            "USR-OPS-001",
            "Processor fee discrepancy verified."
        )

        assert result["action"] == "NOTE_ADDED"

        # 3. Resolve exception.
        result = resolve_exception(
            connection,
            exception_id,
            "USR-OPS-001",
            "VERIFY_PROCESSOR_FEE",
            "FEE_VARIANCE_CONFIRMED",
            "Fee discrepancy investigated and documented."
        )

        assert result["status"] == "RESOLVED"

        # 4. Close exception.
        result = close_exception(
            connection,
            exception_id,
            "USR-ADMIN-001",
            "Resolution verified and closed."
        )

        assert result["status"] == "CLOSED"

        # 5. Verify final database status.
        status = connection.execute("""
            SELECT exception_status
            FROM exceptions
            WHERE exception_id = ?
        """, (exception_id,)).fetchone()[0]

        assert status == "CLOSED"

        # 6. Verify resolution record.
        resolution_count = connection.execute("""
            SELECT COUNT(*)
            FROM resolutions
            WHERE exception_id = ?
        """, (exception_id,)).fetchone()[0]

        assert resolution_count == 1

        # 7. Verify complete audit history.
        history = get_exception_history(
            connection,
            exception_id
        )

        actions = [
            item["action_type"]
            for item in history
        ]

        assert actions == [
            "DETECTED",
            "ASSIGNED",
            "NOTE_ADDED",
            "RESOLVED",
            "CLOSED"
        ]

        # 8. Verify chronological event timestamps.
        timestamps = [
            item["created_at"]
            for item in history
        ]

        assert timestamps == sorted(timestamps)

        # 9. Verify foreign keys.
        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert foreign_key_errors == []

    finally:
        connection.close()
