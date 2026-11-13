
import argparse
import random
import sqlite3

from datetime import date, timedelta
from pathlib import Path
from faker import Faker


# --------------------------------------------------
# PROJECT CONFIGURATION
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

DEFAULT_SEED = 20261022

SCALE_CONFIG = {
    "starter": 20,
    "full": 2000
}

COUNTRY_CURRENCIES = [
    ("IN", "INR"),
    ("US", "USD"),
    ("GB", "GBP"),
    ("DE", "EUR")
]


# --------------------------------------------------
# GENERATE MERCHANT RECORDS
# --------------------------------------------------

def generate_merchants(count, seed):

    rng = random.Random(seed)

    fake = Faker("en_IN")
    fake.seed_instance(seed)

    merchants = []

    start_date = date(2026, 1, 1)

    for number in range(1, count + 1):

        merchant_id = f"MER-{number:06d}"

        merchant_name = fake.company()

        country_code, currency = rng.choice(
            COUNTRY_CURRENCIES
        )

        status = rng.choices(
            ["ACTIVE", "INACTIVE", "SUSPENDED"],
            weights=[95, 3, 2],
            k=1
        )[0]

        effective_date = start_date + timedelta(
            days=rng.randint(0, 310)
        )

        created_at = (
            effective_date.isoformat() + "T09:00:00"
        )

        merchants.append((
            merchant_id,
            merchant_name,
            country_code,
            currency,
            status,
            effective_date.isoformat(),
            None,
            created_at
        ))

    return merchants


# --------------------------------------------------
# GENERATE SAMPLE APPLICATION USERS
# --------------------------------------------------

def generate_users():

    return [
        (
            "USR-CUSTOMER-001",
            "Sample Customer",
            "CUSTOMER",
            1,
            "2026-01-01T09:00:00"
        ),
        (
            "USR-OPS-001",
            "Operations Analyst",
            "OPS_ANALYST",
            1,
            "2026-01-01T09:00:00"
        ),
        (
            "USR-RISK-001",
            "Risk Reviewer",
            "RISK_COMPLIANCE_REVIEWER",
            1,
            "2026-01-01T09:00:00"
        ),
        (
            "USR-ADMIN-001",
            "System Administrator",
            "SYSTEM_ADMIN",
            1,
            "2026-01-01T09:00:00"
        )
    ]


# --------------------------------------------------
# SAVE DATA IN SQLITE
# --------------------------------------------------

def save_master_data(merchants, users,
    database_path=DATABASE_PATH):

    if not database_path.exists():
        raise FileNotFoundError(
            "Database not found. Run scripts/init_db.py first."
        )

    with sqlite3.connect(database_path) as connection:

        connection.execute("PRAGMA foreign_keys = ON")

        connection.executemany("""
            INSERT OR IGNORE INTO merchants (
                merchant_id,
                merchant_name,
                country_code,
                default_currency,
                status,
                effective_from,
                effective_to,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, merchants)

        connection.executemany("""
            INSERT OR IGNORE INTO app_users (
                user_id,
                display_name,
                role,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, users)

        merchant_count = connection.execute(
            "SELECT COUNT(*) FROM merchants"
        ).fetchone()[0]

        user_count = connection.execute(
            "SELECT COUNT(*) FROM app_users"
        ).fetchone()[0]

    print("\nMaster data saved successfully!")

    print(f"Merchants in database: {merchant_count}")
    print(f"Application users: {user_count}")


# --------------------------------------------------
# MAIN PROGRAM
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="YottaFlex synthetic master data generator"
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
        "--merchants",
        type=int,
        default=None
    )

    parser.add_argument(
    "--database",
    type=Path,
    default=DATABASE_PATH,
    help="SQLite database path."
)
    args = parser.parse_args()

    merchant_count = (
        args.merchants
        if args.merchants is not None
        else SCALE_CONFIG[args.scale]
    )

    if merchant_count < 1:
        parser.error("--merchants must be at least 1")

    print("Starting master data generation...")
    print(f"Scale: {args.scale}")
    print(f"Random seed: {args.seed}")
    print(f"Merchants to generate: {merchant_count}")

    merchants = generate_merchants(
        merchant_count,
        args.seed
    )

    users = generate_users()

    save_master_data(merchants, users,args.database)

    print("\nMaster data generation completed!")


if __name__ == "__main__":
    main()
