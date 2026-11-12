
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "reconciliation.db"

with sqlite3.connect(DB) as connection:

    errors = connection.execute("""
        SELECT
            b.settlement_batch_id,
            b.net_amount_minor,
            COALESCE(SUM(l.amount_minor), 0)
        FROM settlement_batches b
        LEFT JOIN settlement_lines l
            ON l.settlement_batch_id = b.settlement_batch_id
        GROUP BY b.settlement_batch_id
        HAVING b.net_amount_minor <>
               COALESCE(SUM(l.amount_minor), 0)
    """).fetchall()

    print("Settlement batches:",
          connection.execute(
              "SELECT COUNT(*) FROM settlement_batches"
          ).fetchone()[0])

    print("Settlement lines:",
          connection.execute(
              "SELECT COUNT(*) FROM settlement_lines"
          ).fetchone()[0])

    print("Arithmetic mismatches:", len(errors))

    print("Foreign key errors:",
          len(connection.execute(
              "PRAGMA foreign_key_check"
          ).fetchall()))

    currency_totals = connection.execute("""
        SELECT
            currency_code,
            SUM(net_amount_minor)
        FROM settlement_batches
        GROUP BY currency_code
        ORDER BY currency_code
    """).fetchall()

    print("Settlement totals by currency:")

    for currency, amount in currency_totals:
        print(currency, amount, "minor units")

    print(
        "VALIDATION:",
        "PASSED" if not errors else "FAILED"
    )
