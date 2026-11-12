
import argparse
import random
import sqlite3

from datetime import datetime, timedelta
from pathlib import Path


# =====================================================
# CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

DEFAULT_SEED = 20261022

BANK_MANIFEST_ID = "FEED-BANK-20261112-001"

LINE_CONFIG = {
    # We currently have 60 settlement batches.
    # Use 100 lines so every payout has a bank line.
    "starter": 100,
    "full": 5000
}


# =====================================================
# DATE HELPER
# =====================================================

def add_business_days(date_value, days):

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
# LOAD SETTLEMENT BATCHES
# =====================================================

def load_settlements(connection):

    return connection.execute("""
        SELECT
            settlement_batch_id,
            merchant_id,
            payout_reference,
            currency_code,
            expected_payout_date,
            net_amount_minor

        FROM settlement_batches

        ORDER BY settlement_batch_id

    """).fetchall()


# =====================================================
# GENERATE BANK PAYOUT TRANSACTIONS
# =====================================================

def generate_payout_lines(
    settlement_batches,
    next_number,
    rng
):

    records = []

    for batch in settlement_batches:

        (
            batch_id,
            merchant_id,
            payout_reference,
            currency,
            expected_date,
            net_amount
        ) = batch

        if net_amount <= 0:
            raise ValueError(
                f"Non-positive payout amount for {batch_id}"
            )

        # Most payouts arrive on expected date.
        # Some are delayed by one or two business days.
        delay = rng.choices(
            [0, 1, 2],
            weights=[85, 10, 5],
            k=1
        )[0]

        actual_date = add_business_days(
            expected_date,
            delay
        )

        bank_line_id = (
            f"BANK-2026-{next_number:06d}"
        )

        external_bank_id = (
            f"BTX-2026-{next_number:08d}"
        )

        bank_account_reference = (
            f"BA-{merchant_id}"
        )

        transaction_at = (
            actual_date + " 10:00:00"
        )

        records.append((
            bank_line_id,
            merchant_id,
            bank_account_reference,
            payout_reference,
            external_bank_id,
            "CREDIT",
            net_amount,
            currency,
            transaction_at,
            "SETTLEMENT_PAYOUT",
            BANK_MANIFEST_ID,
            transaction_at
        ))

        next_number += 1

    return records, next_number


# =====================================================
# GENERATE OTHER BANK ACCOUNT ACTIVITY
# =====================================================

def generate_other_bank_lines(
    merchants,
    remaining_count,
    next_number,
    rng
):

    records = []

    for _ in range(remaining_count):

        merchant_id, currency = rng.choice(merchants)

        transaction_type = rng.choice([
            "CREDIT",
            "DEBIT"
        ])

        amount = rng.randint(10000, 2500000)

        signed_amount = (
            amount
            if transaction_type == "CREDIT"
            else -amount
        )

        days_after_start = rng.randint(0, 6)

        transaction_date = (
            datetime(2026, 11, 10)
            + timedelta(days=days_after_start)
        )

        transaction_at = (
            transaction_date.strftime(
                "%Y-%m-%d 11:00:00"
            )
        )

        bank_line_id = (
            f"BANK-2026-{next_number:06d}"
        )

        external_bank_id = (
            f"BTX-2026-{next_number:08d}"
        )

        records.append((
            bank_line_id,
            merchant_id,
            f"BA-{merchant_id}",
            None,
            external_bank_id,
            transaction_type,
            signed_amount,
            currency,
            transaction_at,
            "OTHER_ACCOUNT_ACTIVITY",
            BANK_MANIFEST_ID,
            transaction_at
        ))

        next_number += 1

    return records


# =====================================================
# SAVE BANK STATEMENT DATA
# =====================================================

def save_bank_lines(
    connection,
    records,
    replace_existing=False
):

    existing_count = connection.execute("""
        SELECT COUNT(*)
        FROM bank_statement_lines
    """).fetchone()[0]

    if existing_count and not replace_existing:
        raise ValueError(
            "Bank statement records already exist. "
            "Use --replace-existing to regenerate."
        )

    with connection:

        if replace_existing:

            # Remove downstream records first because
            # they may reference bank statement lines.
            dependent_tables = [
                "reconciliation_allocations",
                "exception_entity_links",
                "exception_events",
                "resolutions",
                "reconciliation_matches",
                "exceptions",
                "reconciliation_runs"
            ]

            for table in dependent_tables:
                connection.execute(
                    f"DELETE FROM {table}"
                )

            connection.execute("""
                DELETE FROM bank_statement_lines
            """)

            connection.execute("""
                DELETE FROM source_feed_manifests
                WHERE feed_manifest_id = ?
            """, (BANK_MANIFEST_ID,))

        # Create independent feed control record.
        connection.execute("""
            INSERT INTO source_feed_manifests (
                feed_manifest_id,
                source_system,
                feed_type,
                file_name,
                currency_code,
                expected_record_count,
                ingested_record_count,
                expected_total_minor,
                ingested_total_minor,
                sha256_checksum,
                feed_status,
                received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            BANK_MANIFEST_ID,
            "SYNTHETIC_BANK",
            "BANK_STATEMENT",
            "bank_statement_feed.csv",
            None,
            len(records),
            len(records),
            None,
            None,
            None,
            "PROCESSED",
            "2026-11-17 09:00:00"
        ))

        connection.executemany("""
            INSERT INTO bank_statement_lines (
                bank_line_id,
                merchant_id,
                bank_account_reference,
                bank_reference,
                external_bank_transaction_id,
                transaction_type,
                signed_amount_minor,
                currency_code,
                transaction_at,
                description,
                feed_manifest_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

        # Verify actual line count.
        actual_count = connection.execute("""
            SELECT COUNT(*)
            FROM bank_statement_lines
        """).fetchone()[0]

        if actual_count != len(records):
            raise ValueError(
                "Bank statement count validation failed."
            )

        # Verify all payout references exist.
        missing_payouts = connection.execute("""
            SELECT
                b.settlement_batch_id,
                b.payout_reference
            FROM settlement_batches b
            LEFT JOIN bank_statement_lines s
                ON s.bank_reference = b.payout_reference
            WHERE s.bank_line_id IS NULL
        """).fetchall()

        if missing_payouts:
            raise ValueError(
                f"Missing payout bank records: {missing_payouts}"
            )

        # Verify payout amounts and currencies.
        mismatches = connection.execute("""
            SELECT
                b.settlement_batch_id
            FROM settlement_batches b
            JOIN bank_statement_lines s
                ON s.bank_reference = b.payout_reference
            WHERE b.net_amount_minor <> s.signed_amount_minor
               OR b.currency_code <> s.currency_code
               OR s.transaction_type <> 'CREDIT'
        """).fetchall()

        if mismatches:
            raise ValueError(
                f"Payout inconsistencies: {mismatches}"
            )

        # Verify foreign keys.
        fk_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk_errors:
            raise ValueError(
                f"Foreign key violations: {fk_errors}"
            )

        print("\nBANK STATEMENT GENERATION SUCCESSFUL")
        print("------------------------------------")
        print(f"Total bank lines: {actual_count}")
        print(f"Settlement payout lines: "
              f"{len(records) - max(0, actual_count - len(records))}")
        print(f"Foreign-key errors: {len(fk_errors)}")
        print("Payout amount validation: PASSED")
        print("Currency validation: PASSED")


# =====================================================
# MAIN PROGRAM
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description="Generate synthetic bank statements"
    )

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter"
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED
    )

    parser.add_argument(
        "--replace-existing",
        action="store_true"
    )

    args = parser.parse_args()

    if not DATABASE_PATH.exists():
        parser.error("Database does not exist.")

    rng = random.Random(args.seed)

    with sqlite3.connect(DATABASE_PATH) as connection:

        connection.execute("PRAGMA foreign_keys = ON")

        settlement_batches = load_settlements(connection)

        merchants = connection.execute("""
            SELECT merchant_id, default_currency
            FROM merchants
            ORDER BY merchant_id
        """).fetchall()

    if not settlement_batches:
        parser.error(
            "No settlement batches found. Generate settlements first."
        )

    target_count = max(
        LINE_CONFIG[args.scale],
        len(settlement_batches)
    )

    if target_count > 5000:
        parser.error(
            "This generator currently supports up to 5,000 "
            "bank statement lines. Adjust settlement batching "
            "before using full scale."
        )

    print("Starting bank statement generation...")
    print(f"Scale: {args.scale}")
    print(f"Seed: {args.seed}")
    print(f"Settlement batches: {len(settlement_batches)}")
    print(f"Target bank statement lines: {target_count}")

    payout_lines, next_number = generate_payout_lines(
        settlement_batches,
        1,
        rng
    )

    remaining_count = target_count - len(payout_lines)

    other_lines = generate_other_bank_lines(
        merchants,
        remaining_count,
        next_number,
        rng
    )

    all_records = payout_lines + other_lines

    save_bank_lines(
        sqlite3.connect(DATABASE_PATH),
        all_records,
        args.replace_existing
    )

    print(f"Settlement payout lines: {len(payout_lines)}")
    print(f"Other account activity lines: {len(other_lines)}")
    print("\nBank statement generation completed!")


if __name__ == "__main__":
    main()
