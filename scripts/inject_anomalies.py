
import argparse
import csv
import json
import shutil
import sqlite3
import sys

from datetime import datetime, timedelta
from pathlib import Path


# =========================================================
# PROJECT PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

# Original starter-data compatibility paths.
CLEAN_DATABASE = (
    DATA_DIR / "reconciliation_clean_backup.db"
)

TEST_DATABASE = (
    DATA_DIR / "reconciliation_anomaly_test.db"
)

GROUND_TRUTH_DIR = (
    DATA_DIR / "ground_truth"
)

GROUND_TRUTH_JSON = (
    GROUND_TRUTH_DIR / "anomaly_ground_truth.json"
)

GROUND_TRUTH_CSV = (
    GROUND_TRUTH_DIR / "anomaly_ground_truth.csv"
)

# Full-scale testing paths.
DEFAULT_TEST_DATABASE = (
    DATA_DIR / "reconciliation_full_scale_anomaly_test.db"
)

DEFAULT_GROUND_TRUTH_DIR = (
    DATA_DIR / "ground_truth_full_scale"
)


# =========================================================
# HELPERS
# =========================================================

def require_row(row, description):

    if row is None:
        raise RuntimeError(
            f"Could not find suitable record: {description}"
        )

    return row


def update_one(cursor, description):

    if cursor.rowcount != 1:
        raise RuntimeError(
            f"Expected one updated row for {description}, "
            f"but got {cursor.rowcount}"
        )


def count_records(connection, table):

    allowed_tables = {
        "merchants",
        "payment_orders",
        "payment_attempts",
        "processor_events",
        "settlement_batches",
        "settlement_lines",
        "bank_statement_lines"
    }

    if table not in allowed_tables:
        raise ValueError("Invalid table name.")

    return connection.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]


def validate_full_scale_database(connection):

    expected = {
        "merchants": 2000,
        "payment_orders": 50000,
        "payment_attempts": 55000,
        "settlement_batches": 1000,
        "bank_statement_lines": 5000
    }

    for table, expected_count in expected.items():

        actual_count = count_records(
            connection,
            table
        )

        if actual_count != expected_count:
            raise RuntimeError(
                f"{table}: expected {expected_count}, "
                f"found {actual_count}."
            )

    payout_count = connection.execute("""
        SELECT COUNT(*)
        FROM bank_statement_lines
        WHERE description = 'SETTLEMENT_PAYOUT'
    """).fetchone()[0]

    if payout_count != 1000:
        raise RuntimeError(
            f"Expected 1,000 payout lines, found {payout_count}."
        )


# =========================================================
# PREVENT ACCIDENTAL DUPLICATE INJECTION
# =========================================================

def validate_fresh_test_database(connection):

    markers = [
        (
            "SELECT COUNT(*) FROM settlement_lines "
            "WHERE settlement_line_id = ?",
            ("STL-ANOM-FULL-001-DUP-001",)
        ),
        (
            "SELECT COUNT(*) FROM processor_events "
            "WHERE external_event_id = ?",
            ("evt_anom_full_refund_before_capture",)
        ),
        (
            "SELECT COUNT(*) FROM processor_events "
            "WHERE processor_event_id = ?",
            ("PEV-ANOM-FULL-006-DUP-001",)
        )
    ]

    for query, parameters in markers:

        exists = connection.execute(
            query,
            parameters
        ).fetchone()[0]

        if exists:
            raise RuntimeError(
                "Anomaly markers already exist. "
                "Restore a fresh database copy before running "
                "the injector again."
            )


# =========================================================
# 1. DUPLICATE SETTLEMENT LINE
# =========================================================

def inject_duplicate_settlement_line(connection):

    original = require_row(
        connection.execute("""
            SELECT
                settlement_line_id,
                settlement_batch_id
            FROM settlement_lines
            WHERE line_type = 'CAPTURE'
              AND source_transaction_reference IS NOT NULL
            ORDER BY settlement_line_id
            LIMIT 1
        """).fetchone(),
        "original capture settlement line"
    )

    original_line_id, batch_id = original

    duplicate_line_id = "STL-ANOM-FULL-001-DUP-001"

    cursor = connection.execute("""
        INSERT INTO settlement_lines (
            settlement_line_id,
            settlement_batch_id,
            attempt_id,
            processor_event_id,
            line_type,
            amount_minor,
            currency_code,
            source_transaction_reference,
            created_at
        )
        SELECT
            ?,
            settlement_batch_id,
            attempt_id,
            processor_event_id,
            line_type,
            amount_minor,
            currency_code,
            source_transaction_reference,
            created_at
        FROM settlement_lines
        WHERE settlement_line_id = ?
    """, (
        duplicate_line_id,
        original_line_id
    ))

    update_one(cursor, "duplicate settlement line")

    return {
        "anomaly_id": "A1",
        "scenario": "Duplicate settlement line",
        "expected_exception_type": "DUPLICATE_SETTLEMENT_LINE",
        "affected_record_ids": [
            original_line_id,
            duplicate_line_id,
            batch_id
        ],
        "injection_summary": (
            "Inserted a second settlement line with the "
            "same source transaction reference."
        )
    }


# =========================================================
# 2. FEE VARIANCE
# =========================================================

def inject_fee_variance(connection):

    fee_data = require_row(
        connection.execute("""
            SELECT
                b.settlement_batch_id,
                b.gross_capture_minor,
                b.refund_total_minor,
                b.fee_total_minor,
                b.net_amount_minor,
                s.bank_line_id,
                s.signed_amount_minor
            FROM settlement_batches b
            JOIN bank_statement_lines s
              ON s.bank_reference = b.payout_reference
            WHERE b.fee_total_minor > 0
              AND s.description = 'SETTLEMENT_PAYOUT'
              AND s.transaction_type = 'CREDIT'
            ORDER BY b.settlement_batch_id
            LIMIT 1
        """).fetchone(),
        "settlement batch with processor fee"
    )

    (
        batch_id,
        gross,
        refunds,
        fees,
        net,
        bank_line_id,
        original_bank_amount
    ) = fee_data

    if original_bank_amount != net:
        raise RuntimeError(
            "Baseline bank payout does not equal expected net amount."
        )

    amount_without_fee = gross - refunds

    if amount_without_fee - net != fees:
        raise RuntimeError(
            "Settlement fee arithmetic validation failed."
        )

    cursor = connection.execute("""
        UPDATE bank_statement_lines
        SET signed_amount_minor = ?
        WHERE bank_line_id = ?
          AND signed_amount_minor = ?
    """, (
        amount_without_fee,
        bank_line_id,
        original_bank_amount
    ))

    update_one(cursor, "bank fee discrepancy")

    return {
        "anomaly_id": "A2",
        "scenario": "Bank amount differs by processor fee",
        "expected_exception_type": "FEE_VARIANCE",
        "affected_record_ids": [
            batch_id,
            bank_line_id
        ],
        "injection_summary": (
            f"Changed bank amount from {net} to "
            f"{amount_without_fee}; difference equals "
            f"processor fee {fees}."
        )
    }


# =========================================================
# 3. REFUND BEFORE CAPTURE
# =========================================================

def inject_refund_before_capture(connection):

    # The full-scale baseline has no refunds.
    # Create a controlled synthetic refund against a
    # legitimate successful capture.

    capture = require_row(
        connection.execute("""
            SELECT
                processor_event_id,
                processor_name,
                attempt_id,
                amount_minor,
                currency_code,
                occurred_at,
                received_at,
                feed_manifest_id
            FROM processor_events
            WHERE event_type = 'PAYMENT_CAPTURED'
              AND duplicate_of_event_id IS NULL
              AND processing_status = 'PROCESSED'
            ORDER BY processor_event_id
            LIMIT 1
        """).fetchone(),
        "canonical successful capture"
    )

    (
        capture_event_id,
        processor_name,
        attempt_id,
        capture_amount,
        currency,
        capture_time,
        capture_received_at,
        feed_id
    ) = capture

    capture_datetime = datetime.strptime(
        capture_time,
        "%Y-%m-%d %H:%M:%S"
    )

    capture_received_datetime = datetime.strptime(
        capture_received_at,
        "%Y-%m-%d %H:%M:%S"
    )

    refund_datetime = (
        capture_datetime - timedelta(hours=1)
    )

    refund_received_datetime = (
        capture_received_datetime + timedelta(seconds=5)
    )

    refund_event_id = "PEV-ANOM-FULL-003-REFUND"

    refund_reference = (
        "evt_anom_full_refund_before_capture"
    )

    refund_amount = max(
        1,
        capture_amount // 2
    )

    connection.execute("""
        INSERT INTO processor_events (
            processor_event_id,
            processor_name,
            external_event_id,
            attempt_id,
            event_type,
            amount_minor,
            currency_code,
            occurred_at,
            received_at,
            duplicate_of_event_id,
            processing_status,
            feed_manifest_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
    """, (
        refund_event_id,
        processor_name,
        refund_reference,
        attempt_id,
        "REFUND_SUCCEEDED",
        refund_amount,
        currency,
        refund_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        refund_received_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "PROCESSED",
        feed_id
    ))

    return {
        "anomaly_id": "A3",
        "scenario": "Refund before capture",
        "expected_exception_type": "REFUND_BEFORE_CAPTURE",
        "affected_record_ids": [
            refund_event_id,
            capture_event_id,
            attempt_id
        ],
        "injection_summary": (
            f"Inserted a synthetic refund of {refund_amount} "
            f"minor units one hour before capture."
        )
    }


# =========================================================
# 4. MISSING SOURCE RECORD
# =========================================================

def inject_missing_source_record(connection):

    feed = require_row(
        connection.execute("""
            SELECT
                feed_manifest_id,
                expected_record_count,
                ingested_record_count
            FROM source_feed_manifests
            WHERE source_system = 'SYNTHETIC_BANK'
              AND feed_type = 'BANK_STATEMENT'
            ORDER BY feed_manifest_id
            LIMIT 1
        """).fetchone(),
        "bank statement feed manifest"
    )

    feed_id, expected_count, ingested_count = feed

    if expected_count != ingested_count:
        raise RuntimeError(
            "Selected baseline feed is already inconsistent."
        )

    new_expected_count = ingested_count + 1

    cursor = connection.execute("""
        UPDATE source_feed_manifests
        SET expected_record_count = ?
        WHERE feed_manifest_id = ?
          AND expected_record_count = ?
          AND ingested_record_count = ?
    """, (
        new_expected_count,
        feed_id,
        expected_count,
        ingested_count
    ))

    update_one(cursor, "missing source feed record")

    return {
        "anomaly_id": "A4",
        "scenario": "Silently dropped source record",
        "expected_exception_type": "MISSING_SOURCE_RECORD",
        "affected_record_ids": [feed_id],
        "injection_summary": (
            f"Manifest expects {new_expected_count} records "
            f"but only {ingested_count} were ingested. "
            "No physical bank row was deleted."
        )
    }


# =========================================================
# 5. CURRENCY MISMATCH
# =========================================================

def inject_currency_mismatch(connection):

    currency_data = require_row(
        connection.execute("""
            SELECT
                l.settlement_line_id,
                l.settlement_batch_id,
                l.currency_code,
                b.currency_code
            FROM settlement_lines l
            JOIN settlement_batches b
              ON b.settlement_batch_id = l.settlement_batch_id
            WHERE l.currency_code = b.currency_code
              AND l.line_type = 'FEE'
              AND l.source_transaction_reference IS NOT NULL
            GROUP BY
                l.settlement_batch_id,
                l.source_transaction_reference
            HAVING COUNT(*) = 1
            ORDER BY l.settlement_line_id
            LIMIT 1
        """).fetchone(),
        "unique settlement fee line"
    )

    (
        line_id,
        batch_id,
        original_currency,
        batch_currency
    ) = currency_data

    alternate_currencies = {
        "GBP": "USD",
        "USD": "GBP",
        "INR": "USD",
        "EUR": "GBP"
    }

    new_currency = alternate_currencies.get(
        original_currency
    )

    if new_currency is None or new_currency == batch_currency:
        raise RuntimeError(
            f"No alternate currency for {original_currency}"
        )

    cursor = connection.execute("""
        UPDATE settlement_lines
        SET currency_code = ?
        WHERE settlement_line_id = ?
          AND currency_code = ?
    """, (
        new_currency,
        line_id,
        original_currency
    ))

    update_one(cursor, "currency mismatch")

    return {
        "anomaly_id": "A5",
        "scenario": "Currency mismatch",
        "expected_exception_type": "CURRENCY_MISMATCH",
        "affected_record_ids": [
            line_id,
            batch_id
        ],
        "injection_summary": (
            f"Changed settlement line currency from "
            f"{original_currency} to {new_currency}; "
            f"batch currency remains {batch_currency}."
        )
    }


# =========================================================
# 6. DUPLICATE PROCESSOR EVENT
# =========================================================

def inject_duplicate_processor_event(connection):

    original = require_row(
        connection.execute("""
            SELECT
                processor_event_id,
                processor_name,
                external_event_id,
                attempt_id,
                event_type,
                amount_minor,
                currency_code,
                occurred_at,
                received_at,
                feed_manifest_id
            FROM processor_events
            WHERE event_type = 'PAYMENT_CAPTURED'
              AND duplicate_of_event_id IS NULL
              AND processing_status = 'PROCESSED'
            ORDER BY processor_event_id
            LIMIT 1
        """).fetchone(),
        "canonical successful processor capture"
    )

    (
        original_event_id,
        processor_name,
        external_event_id,
        attempt_id,
        event_type,
        amount,
        currency,
        occurred_at,
        received_at,
        feed_id
    ) = original

    duplicate_event_id = "PEV-ANOM-FULL-006-DUP-001"

    duplicate_received_at = (
        datetime.strptime(
            received_at,
            "%Y-%m-%d %H:%M:%S"
        ) + timedelta(seconds=5)
    ).strftime("%Y-%m-%d %H:%M:%S")

    cursor = connection.execute("""
        INSERT INTO processor_events (
            processor_event_id,
            processor_name,
            external_event_id,
            attempt_id,
            event_type,
            amount_minor,
            currency_code,
            occurred_at,
            received_at,
            duplicate_of_event_id,
            processing_status,
            feed_manifest_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        duplicate_event_id,
        processor_name,
        external_event_id,
        attempt_id,
        event_type,
        amount,
        currency,
        occurred_at,
        duplicate_received_at,
        original_event_id,
        "DUPLICATE",
        feed_id
    ))

    update_one(cursor, "duplicate processor event")

    return {
        "anomaly_id": "A6",
        "scenario": "Duplicate processor event",
        "expected_exception_type": "DUPLICATE_PROCESSOR_EVENT",
        "affected_record_ids": [
            original_event_id,
            duplicate_event_id,
            attempt_id
        ],
        "injection_summary": (
            "Inserted a second delivery with the same "
            "processor event reference and linked it to "
            "the canonical event."
        )
    }


# =========================================================
# INJECT ALL SIX ANOMALIES
# =========================================================

def inject_anomalies(connection):

    labels = []

    labels.append(
        inject_duplicate_settlement_line(connection)
    )

    labels.append(
        inject_fee_variance(connection)
    )

    labels.append(
        inject_refund_before_capture(connection)
    )

    labels.append(
        inject_missing_source_record(connection)
    )

    labels.append(
        inject_currency_mismatch(connection)
    )

    labels.append(
        inject_duplicate_processor_event(connection)
    )

    return labels


# =========================================================
# WRITE GROUND TRUTH
# =========================================================

def write_ground_truth(
    labels,
    output_dir,
    database_path,
    json_path=None,
    csv_path=None,
    dataset="FULL_SCALE"
):

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    if json_path is None:
        json_path = (
            output_dir / "anomaly_ground_truth_full_scale.json"
        )

    if csv_path is None:
        csv_path = (
            output_dir / "anomaly_ground_truth_full_scale.csv"
        )

    document = {
        "project": "YottaFlex Payment Reconciliation",
        "dataset": dataset,
        "database": Path(database_path).name,
        "purpose": (
            "Evaluation labels for synthetic anomaly testing. "
            "This file must never be used as reconciliation "
            "engine input."
        ),
        "engine_input": False,
        "anomalies": labels
    }

    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            document,
            file,
            indent=4
        )

    fields = [
        "anomaly_id",
        "scenario",
        "expected_exception_type",
        "affected_record_ids",
        "injection_summary"
    ]

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        for label in labels:

            writer.writerow({
                **label,
                "affected_record_ids": ";".join(
                    label["affected_record_ids"]
                )
            })

    return json_path, csv_path


# =========================================================
# MAIN PROGRAM
# =========================================================

def main(argv=None):

    # -----------------------------------------------------
    # LEGACY MODE: Used by existing automated tests.
    # -----------------------------------------------------

    if argv is None:

        if not CLEAN_DATABASE.exists():
            raise FileNotFoundError(
                f"Clean starter database not found: {CLEAN_DATABASE}"
            )

        shutil.copy2(
            CLEAN_DATABASE,
            TEST_DATABASE
        )

        database_path = TEST_DATABASE
        output_dir = GROUND_TRUTH_DIR
        json_path = GROUND_TRUTH_JSON
        csv_path = GROUND_TRUTH_CSV

        dataset = "STARTER"
        full_scale = False

    # -----------------------------------------------------
    # FULL-SCALE MODE: Used from PowerShell.
    # -----------------------------------------------------

    else:

        parser = argparse.ArgumentParser(
            description=(
                "Inject anomalies into YottaFlex reconciliation data"
            )
        )

        parser.add_argument(
            "--database",
            type=Path,
            default=DEFAULT_TEST_DATABASE,
            help="Anomaly-testing database."
        )

        parser.add_argument(
            "--ground-truth-dir",
            type=Path,
            default=DEFAULT_GROUND_TRUTH_DIR,
            help="Separate ground-truth output directory."
        )

        args = parser.parse_args(argv)

        database_path = args.database
        output_dir = args.ground_truth_dir
        json_path = None
        csv_path = None

        dataset = "FULL_SCALE"
        full_scale = True

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}"
        )

    connection = sqlite3.connect(database_path)

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:

        connection.execute("BEGIN IMMEDIATE")

        if full_scale:
            validate_full_scale_database(connection)

        validate_fresh_test_database(connection)

        labels = inject_anomalies(connection)

        if full_scale:
            validate_full_scale_database(connection)

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:
            raise RuntimeError(
                f"Foreign-key errors: {foreign_key_errors}"
            )

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"Database integrity failed: {integrity}"
            )

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()

    json_result, csv_result = write_ground_truth(
        labels,
        output_dir,
        database_path,
        json_path=json_path,
        csv_path=csv_path,
        dataset=dataset
    )

    print("\nANOMALY INJECTION COMPLETED")
    print("---------------------------")

    for label in labels:

        print(
            label["anomaly_id"],
            label["expected_exception_type"]
        )

    print("\nTotal anomalies injected:", len(labels))
    print("Foreign-key errors: 0")
    print("Database integrity: PASSED")

    print("\nTest database:")
    print(database_path)

    print("\nGround-truth JSON:")
    print(json_result)

    print("\nGround-truth CSV:")
    print(csv_result)


if __name__ == "__main__":
    main(sys.argv[1:])
