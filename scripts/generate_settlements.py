
import argparse
import sqlite3

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


# =====================================================
# CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

FEE_BASIS_POINTS = 200  # 2% processing fee
YEAR = 2026


# =====================================================
# FEE CALCULATION
# =====================================================

def calculate_fee(amount_minor):
    """
    Calculate processor fee using integer minor units.

    200 basis points = 2%.
    Half units are rounded upward.
    """

    return (
        amount_minor * FEE_BASIS_POINTS + 5000
    ) // 10000


# =====================================================
# SETTLEMENT DATE
# =====================================================

def add_business_days(date_value, days=1):
    """
    Add business days, skipping Saturday and Sunday.
    """

    current = datetime.strptime(
        date_value, "%Y-%m-%d"
    ).date()

    added = 0

    while added < days:

        current += timedelta(days=1)

        if current.weekday() < 5:
            added += 1

    return current.isoformat()


# =====================================================
# LOAD PROCESSOR EVENTS
# =====================================================

def load_financial_events(connection):

    rows = connection.execute("""
        SELECT
            pe.processor_event_id,
            pe.external_event_id,
            pe.event_type,
            pe.attempt_id,
            pa.payment_id,
            po.merchant_id,
            pe.processor_name,
            pe.amount_minor,
            pe.currency_code,
            pe.occurred_at,
            pa.currency_code,
            po.currency_code

        FROM processor_events pe

        JOIN payment_attempts pa
            ON pa.attempt_id = pe.attempt_id

        JOIN payment_orders po
            ON po.payment_id = pa.payment_id

        WHERE pe.event_type IN (
            'PAYMENT_CAPTURED',
            'REFUND_SUCCEEDED'
        )

        AND pe.duplicate_of_event_id IS NULL
        AND pe.processing_status = 'PROCESSED'

        ORDER BY pe.occurred_at, pe.processor_event_id

    """).fetchall()

    events = []

    for row in rows:

        (
            event_id,
            external_event_id,
            event_type,
            attempt_id,
            payment_id,
            merchant_id,
            processor_name,
            amount,
            event_currency,
            occurred_at,
            attempt_currency,
            order_currency
        ) = row

        # Currency must agree throughout the transaction.
        if not (
            event_currency
            == attempt_currency
            == order_currency
        ):
            raise ValueError(
                f"Currency inconsistency in event {event_id}"
            )

        if amount <= 0:
            raise ValueError(
                f"Invalid financial event amount: {event_id}"
            )

        events.append({
            "event_id": event_id,
            "external_event_id": external_event_id,
            "event_type": event_type,
            "attempt_id": attempt_id,
            "payment_id": payment_id,
            "merchant_id": merchant_id,
            "processor_name": processor_name,
            "amount": amount,
            "currency": event_currency,
            "occurred_at": occurred_at
        })

    return events


# =====================================================
# VALIDATE CAPTURE AND REFUND RELATIONSHIPS
# =====================================================

def validate_financial_events(events):

    captured_amounts = defaultdict(int)
    refunded_amounts = defaultdict(int)
    capture_dates = defaultdict(list)

    capture_count = 0
    refund_count = 0

    for event in events:

        attempt_id = event["attempt_id"]

        if event["event_type"] == "PAYMENT_CAPTURED":

            captured_amounts[attempt_id] += event["amount"]

            capture_dates[attempt_id].append(
                datetime.strptime(
                    event["occurred_at"],
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            capture_count += 1

        elif event["event_type"] == "REFUND_SUCCEEDED":

            refunded_amounts[attempt_id] += event["amount"]

            refund_count += 1

    for attempt_id, refund_total in refunded_amounts.items():

        if attempt_id not in captured_amounts:
            raise ValueError(
                f"Refund without capture: {attempt_id}"
            )

        earliest_capture = min(capture_dates[attempt_id])

        refunds = [
            event for event in events
            if event["attempt_id"] == attempt_id
            and event["event_type"] == "REFUND_SUCCEEDED"
        ]

        for refund in refunds:

            refund_time = datetime.strptime(
                refund["occurred_at"],
                "%Y-%m-%d %H:%M:%S"
            )

            if refund_time < earliest_capture:
                raise ValueError(
                    f"Refund occurred before capture: "
                    f"{attempt_id}"
                )

        if refund_total > captured_amounts[attempt_id]:
            raise ValueError(
                f"Refund exceeds captured amount: {attempt_id}"
            )

    return capture_count, refund_count


# =====================================================
# GROUP EVENTS INTO SETTLEMENT BATCHES
# =====================================================

def build_settlement_batches(events):

    grouped = defaultdict(list)

    for event in events:

        # Never aggregate across merchants, processors
        # or currencies.
        key = (
            event["merchant_id"],
            event["processor_name"],
            event["currency"]
        )

        grouped[key].append(event)

    batches = []
    lines = []

    for batch_number, key in enumerate(
        sorted(grouped.keys()), start=1
    ):

        merchant_id, processor_name, currency = key

        batch_id = f"SET-{YEAR}-{batch_number:06d}"

        payout_reference = (
            f"PAYOUT-{YEAR}-{batch_number:06d}"
        )

        batch_events = grouped[key]

        gross_capture = sum(
            event["amount"]
            for event in batch_events
            if event["event_type"] == "PAYMENT_CAPTURED"
        )

        total_refunds = sum(
            event["amount"]
            for event in batch_events
            if event["event_type"] == "REFUND_SUCCEEDED"
        )

        total_fees = sum(
            calculate_fee(event["amount"])
            for event in batch_events
            if event["event_type"] == "PAYMENT_CAPTURED"
        )

        adjustment_total = 0

        net_amount = (
            gross_capture
            - total_refunds
            - total_fees
            + adjustment_total
        )

        event_dates = [
            event["occurred_at"][:10]
            for event in batch_events
        ]

        period_start = min(event_dates)
        period_end = max(event_dates)

        expected_payout_date = add_business_days(
            period_end, 1
        )

        created_at = period_end + " 20:00:00"

        batches.append((
            batch_id,
            merchant_id,
            processor_name,
            payout_reference,
            currency,
            period_start,
            period_end,
            expected_payout_date,
            None,
            "SUBMITTED",
            gross_capture,
            total_refunds,
            total_fees,
            adjustment_total,
            net_amount,
            created_at
        ))

        # Generate traceable financial lines.
        line_number = 1

        sorted_events = sorted(
            batch_events,
            key=lambda event: (
                event["occurred_at"],
                event["event_id"]
            )
        )

        for event in sorted_events:

            event_id = event["event_id"]
            attempt_id = event["attempt_id"]
            amount = event["amount"]
            timestamp = event["occurred_at"]

            if event["event_type"] == "PAYMENT_CAPTURED":

                line_id = (
                    f"STL-{batch_id}-{line_number:03d}"
                )

                lines.append((
                    line_id,
                    batch_id,
                    attempt_id,
                    event_id,
                    "CAPTURE",
                    amount,
                    currency,
                    f"CAPTURE:{event['external_event_id']}",
                    timestamp
                ))

                line_number += 1

                # Processor fee is a separate negative line.
                fee = calculate_fee(amount)

                fee_line_id = (
                    f"STL-{batch_id}-{line_number:03d}"
                )

                lines.append((
                    fee_line_id,
                    batch_id,
                    attempt_id,
                    event_id,
                    "FEE",
                    -fee,
                    currency,
                    f"FEE:{event['external_event_id']}",
                    timestamp
                ))

                line_number += 1

            elif event["event_type"] == "REFUND_SUCCEEDED":

                refund_line_id = (
                    f"STL-{batch_id}-{line_number:03d}"
                )

                lines.append((
                    refund_line_id,
                    batch_id,
                    attempt_id,
                    event_id,
                    "REFUND",
                    -amount,
                    currency,
                    f"REFUND:{event['external_event_id']}",
                    timestamp
                ))

                line_number += 1

    return batches, lines


# =====================================================
# REPLACE PREVIOUS SETTLEMENT DATA
# =====================================================

def clear_previous_settlements(connection):

    dependent_tables = [
        "reconciliation_allocations",
        "exception_entity_links",
        "exception_events",
        "resolutions",
        "reconciliation_matches",
        "exceptions",
        "reconciliation_runs",
        "bank_statement_lines",
        "settlement_lines",
        "settlement_batches"
    ]

    for table in dependent_tables:

        connection.execute(
            f"DELETE FROM {table}"
        )


# =====================================================
# SAVE AND VALIDATE SETTLEMENTS
# =====================================================

def save_settlements(
    batches,
    lines,
    replace_existing=False,
    database_path=DATABASE_PATH
):

    database_path = Path(database_path)

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}"
        )

    connection = sqlite3.connect(database_path)

    connection.execute("PRAGMA foreign_keys = ON")

    try:

        existing_batches = connection.execute("""
            SELECT COUNT(*) FROM settlement_batches
        """).fetchone()[0]

        if existing_batches and not replace_existing:
            raise ValueError(
                "Settlement batches already exist. "
                "Use --replace-existing only when intentionally "
                "regenerating synthetic settlement data."
            )

        with connection:

            if replace_existing:
                clear_previous_settlements(connection)

            connection.executemany("""
                INSERT INTO settlement_batches (
                    settlement_batch_id,
                    merchant_id,
                    processor_name,
                    payout_reference,
                    currency_code,
                    period_start,
                    period_end,
                    expected_payout_date,
                    settled_at,
                    batch_status,
                    gross_capture_minor,
                    refund_total_minor,
                    fee_total_minor,
                    adjustment_total_minor,
                    net_amount_minor,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batches)

            connection.executemany("""
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, lines)

            # Verify batch totals against actual line sums.
            mismatches = connection.execute("""
                SELECT
                    b.settlement_batch_id,
                    b.net_amount_minor,
                    COALESCE(SUM(l.amount_minor), 0)
                FROM settlement_batches b
                LEFT JOIN settlement_lines l
                    ON l.settlement_batch_id =
                       b.settlement_batch_id
                GROUP BY b.settlement_batch_id
                HAVING b.net_amount_minor <>
                       COALESCE(SUM(l.amount_minor), 0)
            """).fetchall()

            if mismatches:
                raise ValueError(
                    f"Settlement arithmetic mismatch: {mismatches}"
                )

            # Verify foreign keys.
            fk_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if fk_errors:
                raise ValueError(
                    f"Foreign key errors: {fk_errors}"
                )

            batch_count = connection.execute("""
                SELECT COUNT(*) FROM settlement_batches
            """).fetchone()[0]

            line_count = connection.execute("""
                SELECT COUNT(*) FROM settlement_lines
            """).fetchone()[0]

            if batch_count != len(batches):
                raise ValueError(
                    "Settlement batch count verification failed."
                )

            if line_count != len(lines):
                raise ValueError(
                    "Settlement line count verification failed."
                )

            print("\nSETTLEMENT GENERATION SUCCESSFUL")
            print("--------------------------------")
            print(f"Database: {database_path}")
            print(f"Settlement batches: {batch_count}")
            print(f"Settlement lines: {line_count}")

            # Never combine different currencies.
            currency_totals = connection.execute("""
                SELECT
                    currency_code,
                    COUNT(*),
                    SUM(gross_capture_minor),
                    SUM(refund_total_minor),
                    SUM(fee_total_minor),
                    SUM(net_amount_minor)
                FROM settlement_batches
                GROUP BY currency_code
                ORDER BY currency_code
            """).fetchall()

            for row in currency_totals:

                currency, count, gross, refunds, fees, net = row

                print(f"\nCurrency: {currency}")
                print(f"Batches: {count}")
                print(f"Gross captures (minor units): {gross}")
                print(f"Refunds (minor units): {refunds}")
                print(f"Fees (minor units): {fees}")
                print(f"Net settlement (minor units): {net}")

            print("\nSettlement line arithmetic: PASSED")
            print("Foreign-key validation: PASSED")

    finally:
        connection.close()


# =====================================================
# MAIN PROGRAM
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description="Generate YottaFlex settlement batches"
    )

    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace existing settlement and reconciliation data."
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DATABASE_PATH,
        help="SQLite database path."
    )

    parser.add_argument(
        "--expected-batches",
        type=int,
        default=None,
        help="Optional expected settlement batch count."
    )

    args = parser.parse_args()

    database_path = args.database

    if not database_path.exists():
        parser.error(
            f"Database not found: {database_path}"
        )

    if (
        args.expected_batches is not None
        and args.expected_batches < 1
    ):
        parser.error(
            "--expected-batches must be at least 1."
        )

    with sqlite3.connect(database_path) as connection:

        connection.execute("PRAGMA foreign_keys = ON")

        events = load_financial_events(connection)

        if not events:
            parser.error(
                "No eligible capture or refund events found."
            )

        capture_count, refund_count = (
            validate_financial_events(events)
        )

        batches, lines = build_settlement_batches(events)

    print("Starting settlement generation...")
    print(f"Database: {database_path}")
    print(f"Capture events: {capture_count}")
    print(f"Refund events: {refund_count}")
    print(f"Settlement fee: {FEE_BASIS_POINTS / 100}%")
    print(f"Settlement batches prepared: {len(batches)}")
    print(f"Settlement lines prepared: {len(lines)}")

    # Check expected batch count BEFORE modifying the database.
    if (
        args.expected_batches is not None
        and len(batches) != args.expected_batches
    ):
        parser.error(
            f"Expected {args.expected_batches} settlement batches, "
            f"but generated {len(batches)}. Database was not modified."
        )

    save_settlements(
        batches,
        lines,
        args.replace_existing,
        database_path
    )

    print("\nSettlement generation completed!")


if __name__ == "__main__":
    main()
