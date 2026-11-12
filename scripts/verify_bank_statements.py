
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "reconciliation.db"

with sqlite3.connect(DB) as connection:

    total = connection.execute("""
        SELECT COUNT(*)
        FROM bank_statement_lines
    """).fetchone()[0]

    payout_count = connection.execute("""
        SELECT COUNT(*)
        FROM bank_statement_lines
        WHERE description = 'SETTLEMENT_PAYOUT'
    """).fetchone()[0]

    other_count = connection.execute("""
        SELECT COUNT(*)
        FROM bank_statement_lines
        WHERE description = 'OTHER_ACCOUNT_ACTIVITY'
    """).fetchone()[0]

    missing_payouts = connection.execute("""
        SELECT COUNT(*)
        FROM settlement_batches b
        LEFT JOIN bank_statement_lines s
            ON s.bank_reference = b.payout_reference
        WHERE s.bank_line_id IS NULL
    """).fetchone()[0]

    payout_mismatches = connection.execute("""
        SELECT COUNT(*)
        FROM settlement_batches b
        JOIN bank_statement_lines s
            ON s.bank_reference = b.payout_reference
        WHERE b.net_amount_minor <> s.signed_amount_minor
           OR b.currency_code <> s.currency_code
    """).fetchone()[0]

    fk_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    print("\nBANK STATEMENT VALIDATION")
    print("-------------------------")
    print("Total bank lines:", total)
    print("Settlement payout lines:", payout_count)
    print("Other account activity:", other_count)
    print("Missing payout records:", missing_payouts)
    print("Payout mismatches:", payout_mismatches)
    print("Foreign-key errors:", len(fk_errors))

    passed = (
        total == payout_count + other_count
        and payout_count > 0
        and missing_payouts == 0
        and payout_mismatches == 0
        and len(fk_errors) == 0
    )

    print(
        "VALIDATION:",
        "PASSED" if passed else "FAILED"
    )
