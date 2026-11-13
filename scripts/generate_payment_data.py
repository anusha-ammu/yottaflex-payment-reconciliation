
import argparse
import random
import sqlite3

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


# =====================================================
# PROJECT CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

DEFAULT_SEED = 20261022

PAYMENT_CONFIG = {
    "starter": 500,
    "full": 50000
}

PROCESSORS = [
    "PROC_ALPHA",
    "PROC_BETA",
    "PROC_GAMMA"
]


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def format_timestamp(value):
    """Convert datetime into a consistent SQL timestamp."""

    return value.strftime("%Y-%m-%d %H:%M:%S")


def generate_amount_minor(rng):
    """
    Generate a realistic transaction amount.

    Amounts are stored in integer minor units.
    Example: INR 100.50 = 10050 paise.
    """

    amount_major = Decimal(
        str(min(
            50000,
            max(5, rng.lognormvariate(5.5, 0.9))
        ))
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    return int(amount_major * 100)


# =====================================================
# SAFE REGENERATION
# =====================================================

def clear_transaction_data(connection):
    """
    Clear synthetic transaction records before regeneration.
    Preserve merchants and application users.
    """

    tables = [
        "reconciliation_allocations",
        "reconciliation_matches",
        "exception_entity_links",
        "exception_events",
        "resolutions",
        "exceptions",
        "reconciliation_runs",
        "settlement_lines",
        "settlement_batches",
        "bank_statement_lines",
    ]

    for table in tables:
        connection.execute(f"DELETE FROM {table}")

    # Delete duplicate deliveries before canonical events.
    connection.execute("""
        DELETE FROM processor_events
        WHERE duplicate_of_event_id IS NOT NULL
    """)

    connection.execute("DELETE FROM processor_events")
    connection.execute("DELETE FROM payment_attempts")
    connection.execute("DELETE FROM payment_orders")
    connection.execute("DELETE FROM source_feed_manifests")


# =====================================================
# GENERATE PAYMENT ORDERS
# =====================================================

def generate_payment_records(
    merchant_records,
    payment_count,
    seed,
    one_processor_per_merchant=False
):
    """
    Generate linked payment orders, attempts
    and processor events.

    Baseline:
    80% first-attempt successful orders
    10% permanently failed orders
    10% successful retry orders
    """

    rng = random.Random(seed)

    # Simulate different merchant transaction volumes.
    merchant_weights = [
        rng.lognormvariate(0, 0.8)
        for _ in merchant_records
    ]

    if one_processor_per_merchant:

        if payment_count < len(merchant_records):
            raise ValueError(
                "Payment count must cover all selected merchants."
            )

        selected_merchants = list(merchant_records)

        selected_merchants.extend(
            rng.choices(
                merchant_records,
                weights=merchant_weights,
                k=payment_count - len(merchant_records)
            )
        )

        rng.shuffle(selected_merchants)

    else:

        selected_merchants = rng.choices(
            merchant_records,
            weights=merchant_weights,
            k=payment_count
        )


    merchant_processor_map = {
    merchant_id: PROCESSORS[index % len(PROCESSORS)]
    for index, (merchant_id, currency)
    in enumerate(merchant_records)
}

    # Exactly 10% of orders will require a retry.
    retry_count = round(payment_count * 0.10)

    retry_indices = set(
        rng.sample(range(payment_count), retry_count)
    )

        # Select permanently failed orders from
    # the remaining single-attempt orders.

    single_attempt_indices = [
        index
        for index in range(payment_count)
        if index not in retry_indices
    ]

    # Protect the first payment for every merchant.
    protected_indices = set()

    if one_processor_per_merchant:

        first_payment_by_merchant = {}

        for index, (merchant_id, currency) in enumerate(
            selected_merchants
        ):
            first_payment_by_merchant.setdefault(
                merchant_id,
                index
            )

        protected_indices = set(
            first_payment_by_merchant.values()
        )

    permanent_failure_count = round(
        payment_count * 0.10
    )

    permanent_failure_candidates = [
        index
        for index in single_attempt_indices
        if index not in protected_indices
    ]

    if permanent_failure_count > len(permanent_failure_candidates):
        raise ValueError(
            "Not enough eligible payments for permanent failures."
        )

    permanently_failed_indices = set(
        rng.sample(
            permanent_failure_candidates,
            permanent_failure_count
        )
    )

    payment_orders = []
    payment_attempts = []
    processor_events = []

    event_counter = 0

    # Fixed synthetic transaction period.
    base_time = datetime(2026, 11, 10, 8, 0, 0)

    for index in range(payment_count):

        payment_number = index + 1

        payment_id = (
            f"PAY-2026-{payment_number:08d}"
        )

        merchant_id, currency = selected_merchants[index]

        order_reference = (
            f"ORD-{payment_number:08d}"
        )

        amount_minor = generate_amount_minor(rng)

        if one_processor_per_merchant:
                processor_name = merchant_processor_map[merchant_id]
        else:
                processor_name = rng.choice(PROCESSORS)

        # All baseline payments occur after merchant activation.
        order_created = base_time + timedelta(
            days=rng.randint(0, 1),
            minutes=rng.randint(0, 720)
        )

        first_attempt_time = order_created + timedelta(
            seconds=rng.randint(10, 600)
        )

        is_retry_payment = index in retry_indices

        is_protected_payment = (
            index in protected_indices
        )

        is_permanently_failed = (
            index in permanently_failed_indices
            and not is_protected_payment
        )

        if is_retry_payment:

            order_outcome = "PAID"

            attempt_specs = [
                (1, "FAILED", first_attempt_time),
                (
                    2,
                    "CAPTURED",
                    first_attempt_time + timedelta(
                        minutes=rng.randint(5, 60)
                    )
                )
            ]

        elif is_permanently_failed:

            order_outcome = "FAILED"

            attempt_specs = [
                (1, "FAILED", first_attempt_time)
            ]

        else:

            order_outcome = "PAID"

            attempt_specs = [
                (1, "CAPTURED", first_attempt_time)
            ]

        last_event_time = None

        # -------------------------------------------------
        # Generate payment attempts and related events.
        # -------------------------------------------------

        for attempt_number, attempt_status, attempted_at in attempt_specs:

            attempt_id = (
                f"ATT-{payment_id}-{attempt_number:02d}"
            )

            attempt_reference = (
                f"ATTREF-{payment_number:08d}-{attempt_number:02d}"
            )

            if attempt_status == "CAPTURED":

                event_specs = [
                    (
                        "PAYMENT_AUTHORIZED",
                        attempted_at + timedelta(seconds=2)
                    ),
                    (
                        "PAYMENT_CAPTURED",
                        attempted_at + timedelta(seconds=30)
                    )
                ]

            else:

                event_specs = [
                    (
                        "PAYMENT_FAILED",
                        attempted_at + timedelta(seconds=15)
                    )
                ]

            last_event_time = event_specs[-1][1]

            payment_attempts.append((
                attempt_id,
                payment_id,
                attempt_number,
                processor_name,
                attempt_reference,
                amount_minor,
                currency,
                attempt_status,
                format_timestamp(attempted_at),
                format_timestamp(attempted_at),
                format_timestamp(last_event_time)
            ))

            # Create processor event records.
            for event_type, occurred_at in event_specs:

                event_counter += 1

                processor_event_id = (
                    f"PEV-{event_counter:06d}"
                )

                external_event_id = (
                    f"evt_{payment_number:08d}_"
                    f"{attempt_number:02d}_"
                    f"{event_type.lower()}"
                )

                received_at = occurred_at + timedelta(
                    seconds=rng.randint(1, 5)
                )

                processor_events.append((
                    processor_event_id,
                    processor_name,
                    external_event_id,
                    attempt_id,
                    event_type,
                    amount_minor,
                    currency,
                    format_timestamp(occurred_at),
                    format_timestamp(received_at),
                    None,
                    "PROCESSED",
                    None
                ))

        # -------------------------------------------------
        # Create payment order after deriving outcome
        # from its attempts.
        # -------------------------------------------------

        payment_orders.append((
            payment_id,
            merchant_id,
            order_reference,
            amount_minor,
            currency,
            order_outcome,
            format_timestamp(order_created),
            format_timestamp(last_event_time)
        ))

    return payment_orders, payment_attempts, processor_events


# =====================================================
# SAVE DATA INTO SQLITE
# =====================================================

def save_payment_data(
    payment_orders,
    payment_attempts,
    processor_events,
    replace_existing=False,
    database_path=DATABASE_PATH
):

    if not database_path.exists():
        raise FileNotFoundError(
            "Database not found. Run scripts/init_db.py first."
        )

    connection = sqlite3.connect(database_path)

    try:

        connection.execute("PRAGMA foreign_keys = ON")

        existing_count = connection.execute(
            "SELECT COUNT(*) FROM payment_orders"
        ).fetchone()[0]

        if existing_count > 0 and not replace_existing:
            raise ValueError(
                "Payment data already exists. "
                "Use --replace-existing to regenerate "
                "synthetic transaction data."
            )

        with connection:

            if replace_existing:
                clear_transaction_data(connection)

            connection.executemany("""
                INSERT INTO payment_orders (
                    payment_id,
                    merchant_id,
                    merchant_order_reference,
                    amount_minor,
                    currency_code,
                    order_status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, payment_orders)

            connection.executemany("""
                INSERT INTO payment_attempts (
                    attempt_id,
                    payment_id,
                    attempt_number,
                    processor_name,
                    processor_attempt_reference,
                    amount_minor,
                    currency_code,
                    attempt_status,
                    attempted_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, payment_attempts)

            connection.executemany("""
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
            """, processor_events)

            # Verify foreign key integrity.
            foreign_key_errors = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            if foreign_key_errors:
                raise ValueError(
                    f"Foreign key validation failed: "
                    f"{foreign_key_errors}"
                )

            # Calculate stored record counts.
            order_count = connection.execute(
                "SELECT COUNT(*) FROM payment_orders"
            ).fetchone()[0]

            attempt_count = connection.execute(
                "SELECT COUNT(*) FROM payment_attempts"
            ).fetchone()[0]

            event_count = connection.execute(
                "SELECT COUNT(*) FROM processor_events"
            ).fetchone()[0]

            paid_count = connection.execute("""
                SELECT COUNT(*) FROM payment_orders
                WHERE order_status = 'PAID'
            """).fetchone()[0]

            failed_count = connection.execute("""
                SELECT COUNT(*) FROM payment_orders
                WHERE order_status = 'FAILED'
            """).fetchone()[0]

            if (
                order_count != len(payment_orders)
                or attempt_count != len(payment_attempts)
                or event_count != len(processor_events)
            ):
                raise ValueError(
                    "Generated record count verification failed."
                )

            print("\nPayment data generated successfully!")
            print(f"Payment orders: {order_count}")
            print(f"Payment attempts: {attempt_count}")
            print(f"Processor events: {event_count}")
            print(f"Successful orders: {paid_count}")
            print(f"Failed orders: {failed_count}")
            print("Foreign-key validation: PASSED")

    finally:
        connection.close()


# =====================================================
# MAIN PROGRAM
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description="Generate YottaFlex payment data"
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
        action="store_true",
        help="Clear existing synthetic transaction data first."
    )
    parser.add_argument(
    "--database",
    type=Path,
    default=DATABASE_PATH,
    help="SQLite database path."
)

    args = parser.parse_args()

    payment_count = PAYMENT_CONFIG[args.scale]


    if not args.database.exists():
        parser.error(
            "Database not found. Run scripts/init_db.py first."
        )

    with sqlite3.connect(args.database) as connection:

        connection.execute("PRAGMA foreign_keys = ON")

        total_merchants = connection.execute(
            "SELECT COUNT(*) FROM merchants"
        ).fetchone()[0]

        merchant_records = connection.execute("""
            SELECT merchant_id, default_currency
            FROM merchants
            WHERE status = 'ACTIVE'
              AND effective_from <= '2026-11-10'
              AND (
                  effective_to IS NULL
                  OR effective_to >= '2026-11-10'
              )
            ORDER BY merchant_id
        """).fetchall()

    if not merchant_records:
        parser.error(
            "No active merchants available. "
            "Generate master data first."
        )
        if args.scale == "full" and total_merchants < 2000:
            parser.error(
            "Full scale needs 2,000 merchants. "
            "First run: python scripts/generate_master_data.py "
            "--scale full --seed 20261022"
        )

    if args.scale == "full":

        if len(merchant_records) < 1000:
            parser.error(
                "Full scale requires 1,000 active eligible merchants."
            )

        merchant_records = merchant_records[:1000]

    print("Starting payment data generation...")
    print(f"Scale: {args.scale}")
    print(f"Seed: {args.seed}")
    print(f"Payment orders requested: {payment_count}")
    print(f"Active merchants available: {len(merchant_records)}")

    orders, attempts, events = generate_payment_records(
        merchant_records,
        payment_count,
        args.seed,
        one_processor_per_merchant=(args.scale == "full")
    )

    save_payment_data(
        orders,
        attempts,
        events,
        args.replace_existing,
         args.database
    )

    print("\nPayment data generation completed!")


if __name__ == "__main__":
    main()
