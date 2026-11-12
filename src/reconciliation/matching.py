
import sqlite3
import argparse

from datetime import datetime, timedelta
from pathlib import Path


# =========================================================
# 1. PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_PATH = (
    PROJECT_ROOT / "data" / "reconciliation.db"
)

RULE_VERSION = "RECON-V1.0"

DATE_WINDOW_BEFORE_DAYS = 1
DATE_WINDOW_AFTER_DAYS = 4

# Only these columns can be used to associate
# an exception with an affected database record.
LINK_COLUMNS = {
    "payment_id",
    "attempt_id",
    "processor_event_id",
    "settlement_batch_id",
    "settlement_line_id",
    "bank_line_id",
    "reconciliation_id"
}


# =========================================================
# 2. DETERMINISTIC ID GENERATOR
# =========================================================

class IDGenerator:

    def __init__(self):

        self.match_number = 1
        self.exception_number = 1
        self.event_number = 1
        self.link_number = 1
        self.allocation_number = 1

    def match_id(self):

        value = f"REC-2026-{self.match_number:06d}"
        self.match_number += 1

        return value

    def exception_id(self):

        value = f"EXC-{self.exception_number:06d}"
        self.exception_number += 1

        return value

    def event_id(self):

        value = f"EXEV-{self.event_number:06d}"
        self.event_number += 1

        return value

    def link_id(self):

        value = f"EXLINK-{self.link_number:06d}"
        self.link_number += 1

        return value

    def allocation_id(self):

        value = f"ALLOC-{self.allocation_number:06d}"
        self.allocation_number += 1

        return value


# =========================================================
# 3. DATE VALIDATION
# =========================================================

def parse_date(value):

    return datetime.strptime(
        value[:10],
        "%Y-%m-%d"
    ).date()


def is_inside_date_window(
    bank_date,
    expected_date
):

    actual_date = parse_date(bank_date)

    expected = parse_date(expected_date)

    start_date = expected - timedelta(
        days=DATE_WINDOW_BEFORE_DAYS
    )

    end_date = expected + timedelta(
        days=DATE_WINDOW_AFTER_DAYS
    )

    return start_date <= actual_date <= end_date


# =========================================================
# 4. CLEAR PREVIOUS RECONCILIATION RESULTS
# =========================================================

def clear_previous_reconciliation(connection):

    # Delete dependent records before their parent records.

    tables = [
        "exception_entity_links",
        "exception_events",
        "resolutions",
        "reconciliation_allocations",
        "reconciliation_matches",
        "exceptions",
        "reconciliation_runs"
    ]

    for table in tables:

        connection.execute(
            f"DELETE FROM {table}"
        )


# =========================================================
# 5. CREATE EXCEPTION RECORDS
# =========================================================

def create_exception(
    connection,
    ids,
    exception_type,
    severity,
    title,
    description,
    detected_at,
    links=None
):

    exception_id = ids.exception_id()

    # Create main exception.
    connection.execute("""
        INSERT INTO exceptions (
            exception_id,
            exception_type,
            severity,
            exception_status,
            title,
            description,
            detected_at,
            closed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exception_id,
        exception_type,
        severity,
        "OPEN",
        title,
        description,
        detected_at,
        None
    ))

    # Link exception with the affected entities.
    for column, record_id in (links or []):

        if column not in LINK_COLUMNS:

            raise ValueError(
                f"Invalid exception link: {column}"
            )

        values = {
            name: None
            for name in LINK_COLUMNS
        }

        values[column] = record_id

        connection.execute("""
            INSERT INTO exception_entity_links (
                exception_link_id,
                exception_id,
                payment_id,
                attempt_id,
                processor_event_id,
                settlement_batch_id,
                settlement_line_id,
                bank_line_id,
                reconciliation_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ids.link_id(),
            exception_id,
            values["payment_id"],
            values["attempt_id"],
            values["processor_event_id"],
            values["settlement_batch_id"],
            values["settlement_line_id"],
            values["bank_line_id"],
            values["reconciliation_id"]
        ))

    # Preserve initial exception history.
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
        ids.event_id(),
        exception_id,
        None,
        "OPEN",
        "DETECTED",
        None,
        description,
        detected_at
    ))

    return exception_id


# =========================================================
# 6. RECORD RECONCILIATION DECISIONS
# =========================================================

def record_match(
    connection,
    ids,
    run_id,
    batch_id,
    bank_line_id,
    status,
    method,
    expected_amount,
    actual_amount,
    reason,
    evaluated_at
):

    reconciliation_id = ids.match_id()

    difference = None

    if (
        expected_amount is not None
        and actual_amount is not None
    ):

        difference = actual_amount - expected_amount

    # Store the decision.
    connection.execute("""
        INSERT INTO reconciliation_matches (
            reconciliation_id,
            run_id,
            settlement_batch_id,
            bank_line_id,
            match_status,
            match_method,
            expected_amount_minor,
            actual_amount_minor,
            difference_minor,
            decision_reason,
            rule_version,
            evaluated_at,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        reconciliation_id,
        run_id,
        batch_id,
        bank_line_id,
        status,
        method,
        expected_amount,
        actual_amount,
        difference,
        reason,
        RULE_VERSION,
        evaluated_at,
        None
    ))

    # Record allocation for exact and partial matches.
    if status in ("MATCHED", "PARTIAL"):

        allocated_amount = min(
            expected_amount,
            actual_amount
        )

        if allocated_amount > 0:

            connection.execute("""
                INSERT INTO reconciliation_allocations (
                    allocation_id,
                    reconciliation_id,
                    settlement_batch_id,
                    bank_line_id,
                    allocated_amount_minor,
                    currency_code,
                    created_at
                )
                SELECT ?, ?, ?, ?, ?, currency_code, ?
                FROM settlement_batches
                WHERE settlement_batch_id = ?
            """, (
                ids.allocation_id(),
                reconciliation_id,
                batch_id,
                bank_line_id,
                allocated_amount,
                evaluated_at,
                batch_id
            ))

    return reconciliation_id


# =========================================================
# 7. LOAD SETTLEMENT DATA
# =========================================================

def load_batches(connection):

    rows = connection.execute("""
        SELECT *
        FROM settlement_batches
        ORDER BY settlement_batch_id
    """).fetchall()

    return [
        dict(row) for row in rows
    ]


# =========================================================
# 8. LOAD ELIGIBLE BANK PAYOUT RECORDS
# =========================================================

def load_payout_bank_lines(connection):

    rows = connection.execute("""
        SELECT *
        FROM bank_statement_lines
        WHERE description = 'SETTLEMENT_PAYOUT'
        ORDER BY bank_line_id
    """).fetchall()

    return [
        dict(row) for row in rows
    ]


# =========================================================
# 9. RECONCILE INDIVIDUAL SETTLEMENT BATCH
# =========================================================

def process_batch(
    connection,
    ids,
    run_id,
    batch,
    bank_lines,
    consumed_bank_ids,
    evaluated_at
):

    batch_id = batch["settlement_batch_id"]

    expected_amount = batch["net_amount_minor"]

    # Do not reuse a bank line already allocated.
    available_lines = [
        line
        for line in bank_lines
        if line["bank_line_id"] not in consumed_bank_ids
    ]

    # -----------------------------------------------------
    # STEP 1: Match by exact payout reference.
    # -----------------------------------------------------

    candidates = [
        line
        for line in available_lines
        if line["bank_reference"] == batch["payout_reference"]
    ]

    # More than one candidate is ambiguous.
    if len(candidates) > 1:

        record_match(
            connection,
            ids,
            run_id,
            batch_id,
            None,
            "UNMATCHED",
            "DUPLICATE_REFERENCE",
            expected_amount,
            None,
            "Multiple bank records have the same payout reference.",
            evaluated_at
        )

        create_exception(
            connection,
            ids,
            "UNMATCHED_SETTLEMENT",
            "HIGH",
            "Ambiguous payout reference",
            f"Settlement {batch_id} has multiple bank candidates.",
            evaluated_at,
            [
                ("settlement_batch_id", batch_id)
            ]
        )

        return

    # -----------------------------------------------------
    # STEP 2: Handle missing bank references.
    # -----------------------------------------------------

    if len(candidates) == 0:

        fallback = []

        for line in available_lines:

            if line["bank_reference"] is not None:
                continue

            if line["merchant_id"] != batch["merchant_id"]:
                continue

            if line["currency_code"] != batch["currency_code"]:
                continue

            if line["signed_amount_minor"] != expected_amount:
                continue

            if not is_inside_date_window(
                line["transaction_at"],
                batch["expected_payout_date"]
            ):
                continue

            fallback.append(line)

        if len(fallback) == 1:

            bank = fallback[0]

            # Mark bank record as consumed.
            consumed_bank_ids.add(
                bank["bank_line_id"]
            )

            reconciliation_id = record_match(
                connection,
                ids,
                run_id,
                batch_id,
                bank["bank_line_id"],
                "REVIEW_REQUIRED",
                "COMPOSITE_MISSING_REFERENCE",
                expected_amount,
                bank["signed_amount_minor"],
                "Reference is missing. "
                "Other transaction attributes match.",
                evaluated_at
            )

            create_exception(
                connection,
                ids,
                "UNMATCHED_SETTLEMENT",
                "MEDIUM",
                "Missing payout reference",
                "Manual confirmation is required.",
                evaluated_at,
                [
                    ("settlement_batch_id", batch_id),
                    ("bank_line_id", bank["bank_line_id"]),
                    ("reconciliation_id", reconciliation_id)
                ]
            )

            return

        record_match(
            connection,
            ids,
            run_id,
            batch_id,
            None,
            "UNMATCHED",
            "NO_CANDIDATE",
            expected_amount,
            None,
            "No suitable bank payout found.",
            evaluated_at
        )

        create_exception(
            connection,
            ids,
            "UNMATCHED_SETTLEMENT",
            "HIGH",
            "Settlement missing from bank statement",
            f"No eligible bank payout was found for {batch_id}.",
            evaluated_at,
            [
                ("settlement_batch_id", batch_id)
            ]
        )

        return

    # -----------------------------------------------------
    # STEP 3: Candidate found.
    # Important: mark it as consumed immediately so that
    # it cannot be matched to another settlement batch.
    # -----------------------------------------------------

    bank = candidates[0]

    consumed_bank_ids.add(
        bank["bank_line_id"]
    )

    bank_line_id = bank["bank_line_id"]

    actual_amount = bank["signed_amount_minor"]

    bank_currency = bank["currency_code"]

    settlement_currency = batch["currency_code"]

    # -----------------------------------------------------
    # STEP 4: Validate merchant.
    # -----------------------------------------------------

    if bank["merchant_id"] != batch["merchant_id"]:

        status = "REJECTED"

        reason = "Merchant does not match."

        issue_type = "UNMATCHED_SETTLEMENT"

    # -----------------------------------------------------
    # STEP 5: Validate currency.
    # -----------------------------------------------------

    elif bank_currency != settlement_currency:

        status = "REJECTED"

        reason = (
            f"Currency mismatch: "
            f"settlement {settlement_currency}, "
            f"bank {bank_currency}."
        )

        issue_type = "CURRENCY_MISMATCH"

    # -----------------------------------------------------
    # STEP 6: Validate transaction type.
    # -----------------------------------------------------

    elif bank["transaction_type"] != "CREDIT":

        status = "REJECTED"

        reason = "Expected bank payout is not a credit."

        issue_type = "AMOUNT_MISMATCH"

    # -----------------------------------------------------
    # STEP 7: Validate date.
    # -----------------------------------------------------

    elif not is_inside_date_window(
        bank["transaction_at"],
        batch["expected_payout_date"]
    ):

        status = "REVIEW_REQUIRED"

        reason = "Bank transaction date is outside the configured window."

        issue_type = "UNMATCHED_SETTLEMENT"

    # -----------------------------------------------------
    # STEP 8: Compare amounts.
    # -----------------------------------------------------

    elif actual_amount == expected_amount:

        status = "MATCHED"

        reason = (
            "Reference, merchant, currency, "
            "date and amount match."
        )

        issue_type = None

    elif 0 < actual_amount < expected_amount:

        status = "PARTIAL"

        reason = (
            "Bank received less than the expected settlement."
        )

        issue_type = "AMOUNT_MISMATCH"

    elif (
        actual_amount ==
        batch["gross_capture_minor"]
        - batch["refund_total_minor"]
        and batch["fee_total_minor"] > 0
    ):

        status = "REVIEW_REQUIRED"

        reason = (
            "Bank credit appears to exclude processor fees."
        )

        issue_type = "FEE_VARIANCE"

    else:

        status = "REVIEW_REQUIRED"

        reason = (
            "Actual and expected settlement amounts differ."
        )

        issue_type = "AMOUNT_MISMATCH"

    # -----------------------------------------------------
    # STEP 9: Save the decision.
    # -----------------------------------------------------

    reconciliation_id = record_match(
        connection,
        ids,
        run_id,
        batch_id,
        bank_line_id,
        status,
        "EXACT_REFERENCE",
        expected_amount,
        actual_amount,
        reason,
        evaluated_at
    )

    # -----------------------------------------------------
    # STEP 10: Create exception where necessary.
    # -----------------------------------------------------

    if status != "MATCHED":

        severity = (
            "HIGH"
            if status in ("REJECTED", "REVIEW_REQUIRED")
            else "MEDIUM"
        )

        create_exception(
            connection,
            ids,
            issue_type,
            severity,
            reason,
            (
                f"Settlement: {batch_id}. "
                f"Bank line: {bank_line_id}. "
                f"Expected: {expected_amount}. "
                f"Actual: {actual_amount}. "
                f"Difference: {actual_amount - expected_amount}."
            ),
            evaluated_at,
            [
                ("settlement_batch_id", batch_id),
                ("bank_line_id", bank_line_id),
                ("reconciliation_id", reconciliation_id)
            ]
        )


# =========================================================
# 10. DUPLICATE SETTLEMENT LINE DETECTION
# =========================================================

def detect_duplicate_settlement_lines(
    connection,
    ids,
    evaluated_at
):

    duplicates = connection.execute("""
        SELECT
            settlement_batch_id,
            source_transaction_reference,
            COUNT(*) AS duplicate_count
        FROM settlement_lines
        WHERE source_transaction_reference IS NOT NULL
        GROUP BY
            settlement_batch_id,
            source_transaction_reference
        HAVING COUNT(*) > 1
    """).fetchall()

    for batch_id, reference, count in duplicates:

        line_ids = connection.execute("""
            SELECT settlement_line_id
            FROM settlement_lines
            WHERE settlement_batch_id = ?
              AND source_transaction_reference = ?
        """, (
            batch_id,
            reference
        )).fetchall()

        links = [
            ("settlement_line_id", row[0])
            for row in line_ids
        ]

        links.append(
            ("settlement_batch_id", batch_id)
        )

        create_exception(
            connection,
            ids,
            "DUPLICATE_SETTLEMENT_LINE",
            "HIGH",
            "Duplicate settlement line detected",
            (
                f"Reference {reference} appears {count} times "
                f"in batch {batch_id}."
            ),
            evaluated_at,
            links
        )


# =========================================================
# 11. DUPLICATE PROCESSOR EVENT DETECTION
# =========================================================

def detect_duplicate_processor_events(
    connection,
    ids,
    evaluated_at
):

    duplicates = connection.execute("""
        SELECT
            processor_event_id,
            attempt_id,
            external_event_id
        FROM processor_events
        WHERE duplicate_of_event_id IS NOT NULL
           OR processing_status = 'DUPLICATE'
    """).fetchall()

    for event_id, attempt_id, external_id in duplicates:

        create_exception(
            connection,
            ids,
            "DUPLICATE_PROCESSOR_EVENT",
            "MEDIUM",
            "Duplicate processor event",
            (
                f"Processor event {external_id} was ingested "
                "more than once. Its financial effect must "
                "only be processed once."
            ),
            evaluated_at,
            [
                ("processor_event_id", event_id),
                ("attempt_id", attempt_id)
            ]
        )


# =========================================================
# 12. REFUND BEFORE CAPTURE DETECTION
# =========================================================

def detect_refund_before_capture(
    connection,
    ids,
    evaluated_at
):

    refunds = connection.execute("""
        SELECT
            r.processor_event_id,
            r.attempt_id,
            r.occurred_at,
            MIN(c.occurred_at) AS first_capture_at
        FROM processor_events r
        LEFT JOIN processor_events c
            ON c.attempt_id = r.attempt_id
           AND c.event_type = 'PAYMENT_CAPTURED'
           AND c.duplicate_of_event_id IS NULL
        WHERE r.event_type = 'REFUND_SUCCEEDED'
        GROUP BY
            r.processor_event_id,
            r.attempt_id,
            r.occurred_at
    """).fetchall()

    for event_id, attempt_id, refund_time, capture_time in refunds:

        if (
            capture_time is None
            or refund_time < capture_time
        ):

            create_exception(
                connection,
                ids,
                "REFUND_BEFORE_CAPTURE",
                "CRITICAL",
                "Refund lifecycle violation",
                (
                    f"Refund event {event_id} occurred "
                    "before a valid capture."
                ),
                evaluated_at,
                [
                    ("processor_event_id", event_id),
                    ("attempt_id", attempt_id)
                ]
            )


# =========================================================
# 13. CURRENCY CONSISTENCY DETECTION
# =========================================================

def detect_currency_mismatches(
    connection,
    ids,
    evaluated_at
):

    rows = connection.execute("""
        SELECT
            l.settlement_line_id,
            l.settlement_batch_id,
            l.currency_code,
            b.currency_code
        FROM settlement_lines l
        JOIN settlement_batches b
            ON b.settlement_batch_id =
               l.settlement_batch_id
        WHERE l.currency_code <> b.currency_code
    """).fetchall()

    for (
        line_id,
        batch_id,
        line_currency,
        batch_currency
    ) in rows:

        create_exception(
            connection,
            ids,
            "CURRENCY_MISMATCH",
            "CRITICAL",
            "Settlement line currency mismatch",
            (
                f"Line currency {line_currency} differs "
                f"from batch currency {batch_currency}."
            ),
            evaluated_at,
            [
                ("settlement_line_id", line_id),
                ("settlement_batch_id", batch_id)
            ]
        )


# =========================================================
# 14. MISSING SOURCE FEED DETECTION
# =========================================================

def detect_missing_feed_records(
    connection,
    ids,
    evaluated_at
):

    feeds = connection.execute("""
        SELECT
            feed_manifest_id,
            expected_record_count,
            ingested_record_count,
            expected_total_minor,
            ingested_total_minor
        FROM source_feed_manifests
    """).fetchall()

    for (
        feed_id,
        expected_count,
        ingested_count,
        expected_total,
        ingested_total
    ) in feeds:

        count_mismatch = (
            expected_count != ingested_count
        )

        total_mismatch = (
            expected_total is not None
            and ingested_total is not None
            and expected_total != ingested_total
        )

        if count_mismatch or total_mismatch:

            create_exception(
                connection,
                ids,
                "MISSING_SOURCE_RECORD",
                "HIGH",
                "Source feed control mismatch",
                (
                    f"Feed {feed_id}: expected records "
                    f"{expected_count}, ingested records "
                    f"{ingested_count}, expected total "
                    f"{expected_total}, ingested total "
                    f"{ingested_total}."
                ),
                evaluated_at
            )


# =========================================================
# 15. COMPLETE RECONCILIATION PROCESS
# =========================================================

def run_reconciliation(
    replace_existing=False
):

    if not DATABASE_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.row_factory = sqlite3.Row

    try:

        with connection:

            existing_runs = connection.execute("""
                SELECT COUNT(*)
                FROM reconciliation_runs
            """).fetchone()[0]

            if existing_runs and not replace_existing:

                raise ValueError(
                    "Previous reconciliation results exist. "
                    "Use --replace-existing to rerun."
                )

            if replace_existing:

                clear_previous_reconciliation(connection)

            batches = load_batches(connection)

            bank_lines = load_payout_bank_lines(connection)

            if not batches:

                raise ValueError(
                    "No settlement batches found."
                )

            if not bank_lines:

                raise ValueError(
                    "No eligible bank payout lines found."
                )

            # Deterministic synthetic processing timestamp.
            latest_bank_time = max(
                datetime.strptime(
                    line["transaction_at"],
                    "%Y-%m-%d %H:%M:%S"
                )
                for line in bank_lines
            )

            started_at = (
                latest_bank_time + timedelta(minutes=1)
            )

            completed_at = (
                started_at + timedelta(minutes=1)
            )

            started_text = started_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            evaluated_at = completed_at.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            run_id = "RUN-2026-000001"

            connection.execute("""
                INSERT INTO reconciliation_runs (
                    run_id,
                    rule_version,
                    run_status,
                    started_at,
                    completed_at,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                RULE_VERSION,
                "RUNNING",
                started_text,
                None,
                None
            ))

            ids = IDGenerator()

            consumed_bank_ids = set()

            print("Starting reconciliation...")
            print("Rule version:", RULE_VERSION)
            print("Settlement batches:", len(batches))
            print(
                "Eligible bank payout lines:",
                len(bank_lines)
            )

            # Match every settlement batch.
            for batch in batches:

                process_batch(
                    connection,
                    ids,
                    run_id,
                    batch,
                    bank_lines,
                    consumed_bank_ids,
                    evaluated_at
                )

            # Identify bank payout lines with no batch.
            for bank in bank_lines:

                bank_id = bank["bank_line_id"]

                if bank_id in consumed_bank_ids:
                    continue

                reconciliation_id = record_match(
                    connection,
                    ids,
                    run_id,
                    None,
                    bank_id,
                    "UNMATCHED",
                    "NO_SETTLEMENT_CANDIDATE",
                    None,
                    bank["signed_amount_minor"],
                    (
                        "No eligible settlement batch "
                        "matched this bank payout."
                    ),
                    evaluated_at
                )

                create_exception(
                    connection,
                    ids,
                    "UNMATCHED_BANK_LINE",
                    "HIGH",
                    "Unmatched bank payout",
                    (
                        f"Bank line {bank_id} has no "
                        "matching settlement batch."
                    ),
                    evaluated_at,
                    [
                        ("bank_line_id", bank_id),
                        ("reconciliation_id", reconciliation_id)
                    ]
                )

            # Run source anomaly detection.
            detect_duplicate_settlement_lines(
                connection,
                ids,
                evaluated_at
            )

            detect_duplicate_processor_events(
                connection,
                ids,
                evaluated_at
            )

            detect_refund_before_capture(
                connection,
                ids,
                evaluated_at
            )

            detect_currency_mismatches(
                connection,
                ids,
                evaluated_at
            )

            detect_missing_feed_records(
                connection,
                ids,
                evaluated_at
            )

            # Mark the reconciliation run complete.
            connection.execute("""
                UPDATE reconciliation_runs
                SET run_status = 'COMPLETED',
                    completed_at = ?
                WHERE run_id = ?
            """, (
                evaluated_at,
                run_id
            ))

            # Display match summary.
            match_summary = connection.execute("""
                SELECT match_status, COUNT(*)
                FROM reconciliation_matches
                WHERE run_id = ?
                GROUP BY match_status
                ORDER BY match_status
            """, (
                run_id,
            )).fetchall()

            exception_summary = connection.execute("""
                SELECT exception_type, COUNT(*)
                FROM exceptions
                GROUP BY exception_type
                ORDER BY exception_type
            """).fetchall()

            total_matches = connection.execute("""
                SELECT COUNT(*)
                FROM reconciliation_matches
                WHERE run_id = ?
            """, (
                run_id,
            )).fetchone()[0]

            total_exceptions = connection.execute("""
                SELECT COUNT(*)
                FROM exceptions
            """).fetchone()[0]

            fk_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            print("\nRECONCILIATION COMPLETED")
            print("------------------------")
            print("Run ID:", run_id)

            print("\nMATCH SUMMARY")

            for status, count in match_summary:

                print(f"{status}: {count}")

            print("\nEXCEPTION SUMMARY")

            if exception_summary:

                for issue, count in exception_summary:

                    print(f"{issue}: {count}")

            else:

                print("No exceptions detected.")

            print("\nTotal reconciliation decisions:", total_matches)
            print("Total exceptions:", total_exceptions)
            print("Foreign-key errors:", len(fk_errors))

            if fk_errors:

                raise ValueError(
                    f"Foreign-key validation failed: {fk_errors}"
                )

            print("\nFOREIGN KEY VALIDATION: PASSED")
            print("RECONCILIATION ENGINE: PASSED")

    finally:

        connection.close()


# =========================================================
# 16. COMMAND LINE EXECUTION
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="YottaFlex Payment Reconciliation Engine"
    )

    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace previous reconciliation results."
    )

    args = parser.parse_args()

    run_reconciliation(
        replace_existing=args.replace_existing
    )
