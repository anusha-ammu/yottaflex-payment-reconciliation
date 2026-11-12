
import argparse
import random
import sqlite3

from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

DEFAULT_SEED = 20261022
DEFAULT_REFUND_RATE = 0.05


def generate_partial_refunds(seed, refund_rate, replace_existing=False):

    rng = random.Random(seed)

    if not 0 < refund_rate < 1:
        raise ValueError("Refund rate must be between 0 and 1.")

    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Database does not exist.")

    with sqlite3.connect(DATABASE_PATH) as connection:

        connection.execute("PRAGMA foreign_keys = ON")

        existing_refunds = connection.execute("""
            SELECT COUNT(*)
            FROM processor_events
            WHERE event_type = 'REFUND_SUCCEEDED'
        """).fetchone()[0]

        if existing_refunds and not replace_existing:
            raise ValueError(
                "Refund events already exist. "
                "Use --replace-existing to regenerate them."
            )

        with connection:

            # Remove previous generated refunds when explicitly requested.
            if replace_existing:

                refunded_payments = connection.execute("""
                    SELECT DISTINCT pa.payment_id
                    FROM processor_events pe
                    JOIN payment_attempts pa
                        ON pa.attempt_id = pe.attempt_id
                    WHERE pe.event_type = 'REFUND_SUCCEEDED'
                """).fetchall()

                connection.execute("""
                    DELETE FROM processor_events
                    WHERE event_type = 'REFUND_SUCCEEDED'
                """)

                for (payment_id,) in refunded_payments:
                    connection.execute("""
                        UPDATE payment_orders
                        SET order_status = 'PAID'
                        WHERE payment_id = ?
                          AND order_status = 'PARTIALLY_REFUNDED'
                    """, (payment_id,))

            # Find successfully captured payments.
            candidates = connection.execute("""
                SELECT
                    po.payment_id,
                    pa.attempt_id,
                    pa.processor_name,
                    pa.amount_minor,
                    pa.currency_code,
                    pe.occurred_at
                FROM payment_orders po
                JOIN payment_attempts pa
                    ON pa.payment_id = po.payment_id
                JOIN processor_events pe
                    ON pe.attempt_id = pa.attempt_id
                WHERE pa.attempt_status = 'CAPTURED'
                  AND po.order_status = 'PAID'
                  AND pe.event_type = 'PAYMENT_CAPTURED'
                  AND pe.duplicate_of_event_id IS NULL
                  AND pe.processing_status = 'PROCESSED'
                ORDER BY po.payment_id
            """).fetchall()

            if not candidates:
                raise ValueError("No eligible captured payments found.")

            refund_count = max(
                1,
                int(len(candidates) * refund_rate + 0.5)
            )

            selected = rng.sample(candidates, refund_count)

            # Continue the existing processor event ID counter.
            existing_ids = connection.execute("""
                SELECT processor_event_id
                FROM processor_events
            """).fetchall()

            maximum_id = max(
                (
                    int(event_id.split("-")[1])
                    for (event_id,) in existing_ids
                    if event_id.startswith("PEV-")
                ),
                default=0
            )

            next_event_number = maximum_id + 1

            for (
                payment_id,
                attempt_id,
                processor_name,
                capture_amount,
                currency,
                capture_time
            ) in selected:

                # Refund between 10% and 70% of capture.
                percentage = rng.randint(10, 70)

                refund_amount = (
                    capture_amount * percentage // 100
                )

                refund_amount = min(
                    refund_amount,
                    capture_amount - 1
                )

                if refund_amount <= 0:
                    raise ValueError("Invalid partial refund amount.")

                captured_at = datetime.strptime(
                    capture_time,
                    "%Y-%m-%d %H:%M:%S"
                )

                # A valid refund occurs after the capture.
                refund_time = captured_at + timedelta(
                    hours=rng.randint(1, 48)
                )

                received_at = refund_time + timedelta(
                    seconds=rng.randint(1, 300)
                )

                event_id = (
                    f"PEV-{next_event_number:06d}"
                )

                next_event_number += 1

                external_event_id = (
                    f"evt_refund_{payment_id.lower()}"
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    processor_name,
                    external_event_id,
                    attempt_id,
                    "REFUND_SUCCEEDED",
                    refund_amount,
                    currency,
                    refund_time.strftime("%Y-%m-%d %H:%M:%S"),
                    received_at.strftime("%Y-%m-%d %H:%M:%S"),
                    None,
                    "PROCESSED",
                    None
                ))

                # Derive order status from the successful partial refund.
                connection.execute("""
                    UPDATE payment_orders
                    SET order_status = 'PARTIALLY_REFUNDED',
                        updated_at = ?
                    WHERE payment_id = ?
                """, (
                    received_at.strftime("%Y-%m-%d %H:%M:%S"),
                    payment_id
                ))

            # Verify total refunds do not exceed captured amounts.
            refund_errors = connection.execute("""
                SELECT
                    pa.attempt_id,
                    pa.amount_minor,
                    SUM(pe.amount_minor) AS refunded_amount
                FROM payment_attempts pa
                JOIN processor_events pe
                    ON pe.attempt_id = pa.attempt_id
                WHERE pe.event_type = 'REFUND_SUCCEEDED'
                GROUP BY pa.attempt_id, pa.amount_minor
                HAVING SUM(pe.amount_minor) > pa.amount_minor
            """).fetchall()

            if refund_errors:
                raise ValueError(
                    f"Refund validation failed: {refund_errors}"
                )

            # Verify foreign keys.
            fk_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if fk_errors:
                raise ValueError(
                    f"Foreign key errors: {fk_errors}"
                )

            total_refunds = connection.execute("""
                SELECT COUNT(*)
                FROM processor_events
                WHERE event_type = 'REFUND_SUCCEEDED'
            """).fetchone()[0]

            total_refund_amount = connection.execute("""
                SELECT COALESCE(SUM(amount_minor), 0)
                FROM processor_events
                WHERE event_type = 'REFUND_SUCCEEDED'
            """).fetchone()[0]

            partially_refunded_orders = connection.execute("""
                SELECT COUNT(*)
                FROM payment_orders
                WHERE order_status = 'PARTIALLY_REFUNDED'
            """).fetchone()[0]

    print("\nPartial refund generation completed!")
    print(f"Refund events generated: {total_refunds}")
    print(f"Total refunded minor units: {total_refund_amount}")
    print(f"Partially refunded orders: {partially_refunded_orders}")
    print("Refund amount validation: PASSED")
    print("Foreign-key validation: PASSED")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=DEFAULT_REFUND_RATE
    )

    parser.add_argument(
        "--replace-existing",
        action="store_true"
    )

    args = parser.parse_args()

    generate_partial_refunds(
        args.seed,
        args.rate,
        args.replace_existing
    )


if __name__ == "__main__":
    main()
