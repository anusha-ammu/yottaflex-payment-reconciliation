
from pathlib import Path
import sqlite3

# Find project location
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Find SQL schema
SCHEMA_PATH = PROJECT_ROOT / "src" / "database" / "schema.sql"


def run_smoke_test():

    print("Starting database smoke test...")

    # Create temporary in-memory database
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        # Load database schema
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)

        # 1. Create merchant
        connection.execute("""
            INSERT INTO merchants (
                merchant_id, merchant_name, country_code,
                default_currency, status, effective_from,
                effective_to, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "MER-000001",
            "Test Fashion Store",
            "IN",
            "INR",
            "ACTIVE",
            "2026-11-12",
            None,
            "2026-11-12 10:00:00"
        ))

        # 2. Create payment order
        connection.execute("""
            INSERT INTO payment_orders (
                payment_id, merchant_id, merchant_order_reference,
                amount_minor, currency_code, order_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "PAY-2026-00000001",
            "MER-000001",
            "ORDER-001",
            100000,
            "INR",
            "PAID",
            "2026-11-12 10:00:00",
            "2026-11-12 10:00:00"
        ))

        # 3. Create payment attempt
        connection.execute("""
            INSERT INTO payment_attempts (
                attempt_id, payment_id, attempt_number,
                processor_name, processor_attempt_reference,
                amount_minor, currency_code, attempt_status,
                attempted_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "ATT-PAY-2026-00000001-01",
            "PAY-2026-00000001",
            1,
            "TEST_PROCESSOR",
            "ATTEMPT-001",
            100000,
            "INR",
            "CAPTURED",
            "2026-11-12 10:01:00",
            "2026-11-12 10:01:00",
            "2026-11-12 10:01:00"
        ))

        # 4. Create processor capture event
        connection.execute("""
            INSERT INTO processor_events (
                processor_event_id, processor_name,
                external_event_id, attempt_id, event_type,
                amount_minor, currency_code, occurred_at,
                received_at, duplicate_of_event_id,
                processing_status, feed_manifest_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "PEV-000001",
            "TEST_PROCESSOR",
            "EVT-001",
            "ATT-PAY-2026-00000001-01",
            "PAYMENT_CAPTURED",
            100000,
            "INR",
            "2026-11-12 10:01:00",
            "2026-11-12 10:02:00",
            None,
            "PROCESSED",
            None
        ))

        # 5. Create settlement batch
        connection.execute("""
            INSERT INTO settlement_batches (
                settlement_batch_id, merchant_id,
                processor_name, payout_reference,
                currency_code, period_start, period_end,
                expected_payout_date, settled_at,
                batch_status, gross_capture_minor,
                refund_total_minor, fee_total_minor,
                adjustment_total_minor, net_amount_minor,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "SET-2026-000001",
            "MER-000001",
            "TEST_PROCESSOR",
            "PAYOUT-001",
            "INR",
            "2026-11-12",
            "2026-11-12",
            "2026-11-13",
            "2026-11-13 09:00:00",
            "SETTLED",
            100000,
            0,
            2000,
            0,
            98000,
            "2026-11-12 10:05:00"
        ))

        # 6. Create capture settlement line
        connection.execute("""
            INSERT INTO settlement_lines (
                settlement_line_id, settlement_batch_id,
                attempt_id, processor_event_id,
                line_type, amount_minor, currency_code,
                source_transaction_reference, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "STL-SET-2026-000001-001",
            "SET-2026-000001",
            "ATT-PAY-2026-00000001-01",
            "PEV-000001",
            "CAPTURE",
            100000,
            "INR",
            "CAPTURE-001",
            "2026-11-12 10:05:00"
        ))

        # 7. Create fee settlement line
        connection.execute("""
            INSERT INTO settlement_lines (
                settlement_line_id, settlement_batch_id,
                attempt_id, processor_event_id,
                line_type, amount_minor, currency_code,
                source_transaction_reference, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "STL-SET-2026-000001-002",
            "SET-2026-000001",
            None,
            None,
            "FEE",
            -2000,
            "INR",
            "FEE-001",
            "2026-11-12 10:05:00"
        ))

        # 8. Create bank statement line
        connection.execute("""
            INSERT INTO bank_statement_lines (
                bank_line_id, merchant_id,
                bank_account_reference, bank_reference,
                external_bank_transaction_id,
                transaction_type, signed_amount_minor,
                currency_code, transaction_at,
                description, feed_manifest_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "BANK-2026-000001",
            "MER-000001",
            "BANK-ACC-001",
            "PAYOUT-001",
            "BANK-TXN-001",
            "CREDIT",
            98000,
            "INR",
            "2026-11-13 09:00:00",
            "Settlement payout",
            None,
            "2026-11-13 09:01:00"
        ))

        # 9. Create reconciliation run
        connection.execute("""
            INSERT INTO reconciliation_runs (
                run_id, rule_version, run_status,
                started_at, completed_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "RUN-001",
            "RULE-V1",
            "COMPLETED",
            "2026-11-13 10:00:00",
            "2026-11-13 10:01:00",
            None
        ))

        # 10. Record reconciliation decision
        connection.execute("""
            INSERT INTO reconciliation_matches (
                reconciliation_id, run_id,
                settlement_batch_id, bank_line_id,
                match_status, match_method,
                expected_amount_minor, actual_amount_minor,
                difference_minor, decision_reason,
                rule_version, evaluated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "REC-2026-000001",
            "RUN-001",
            "SET-2026-000001",
            "BANK-2026-000001",
            "MATCHED",
            "REFERENCE_AMOUNT_CURRENCY_DATE",
            98000,
            98000,
            0,
            "Reference and amount match",
            "RULE-V1",
            "2026-11-13 10:01:00",
            None
        ))

        # Verify settlement arithmetic from actual lines
        line_total = connection.execute("""
            SELECT SUM(amount_minor)
            FROM settlement_lines
            WHERE settlement_batch_id = ?
        """, ("SET-2026-000001",)).fetchone()[0]

        assert line_total == 98000, "Settlement line total incorrect"

        # Verify batch calculations
        batch = connection.execute("""
            SELECT net_amount_minor
            FROM settlement_batches
            WHERE settlement_batch_id = ?
        """, ("SET-2026-000001",)).fetchone()

        assert batch[0] == line_total

        # Verify match
        match = connection.execute("""
            SELECT match_status, difference_minor
            FROM reconciliation_matches
            WHERE reconciliation_id = ?
        """, ("REC-2026-000001",)).fetchone()

        assert match == ("MATCHED", 0)

        # Verify foreign keys
        errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert not errors, f"Foreign key errors: {errors}"

        # Verify invalid foreign key is rejected
        try:
            connection.execute("""
                INSERT INTO payment_orders (
                    payment_id, merchant_id,
                    merchant_order_reference,
                    amount_minor, currency_code,
                    order_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "PAY-INVALID",
                "MER-DOES-NOT-EXIST",
                "INVALID-ORDER",
                1000,
                "INR",
                "CREATED",
                "2026-11-12",
                "2026-11-12"
            ))

            raise AssertionError("Invalid foreign key was accepted!")

        except sqlite3.IntegrityError:
            print("Foreign key rejection: PASSED")

        print("\nALL SMOKE TESTS PASSED!")
        print("Merchant: MER-000001")
        print("Payment: PAY-2026-00000001")
        print("Settlement: SET-2026-000001")
        print("Capture: 100000 paise")
        print("Fee: 2000 paise")
        print("Expected payout: 98000 paise")
        print("Actual bank credit: 98000 paise")
        print("Reconciliation: MATCHED")
        print("Difference: 0 paise")
        print("Settlement arithmetic: PASSED")
        print("Foreign-key validation: PASSED")

    finally:
        connection.close()


if __name__ == "__main__":
    run_smoke_test()
