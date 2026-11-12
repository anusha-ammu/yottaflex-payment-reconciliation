
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

with sqlite3.connect(DATABASE_PATH) as connection:

    print("\nREFUND DATA VALIDATION")
    print("----------------------")

    refund_events = connection.execute("""
        SELECT COUNT(*)
        FROM processor_events
        WHERE event_type = 'REFUND_SUCCEEDED'
    """).fetchone()[0]

    refunded_orders = connection.execute("""
        SELECT COUNT(*)
        FROM payment_orders
        WHERE order_status = 'PARTIALLY_REFUNDED'
    """).fetchone()[0]

    refund_total = connection.execute("""
        SELECT COALESCE(SUM(amount_minor), 0)
        FROM processor_events
        WHERE event_type = 'REFUND_SUCCEEDED'
    """).fetchone()[0]

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    print(f"Refund events: {refund_events}")
    print(f"Partially refunded orders: {refunded_orders}")
    print(f"Refund total (minor units): {refund_total}")
    print(f"Foreign key errors: {len(foreign_key_errors)}")

    if foreign_key_errors:
        print("Validation: FAILED")
        print(f"Errors: {foreign_key_errors}")
    else:
        print("Validation: PASSED")
