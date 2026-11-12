
from pathlib import Path
import sqlite3
import sys

# Find the main project directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Database and SQL schema locations
SCHEMA_PATH = PROJECT_ROOT / "src" / "database" / "schema.sql"
DATABASE_PATH = PROJECT_ROOT / "data" / "reconciliation.db"

def initialize_database():
    print("Starting database initialization...")

    # Check whether the SQL file exists
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"SQL schema not found: {SCHEMA_PATH}"
        )

    # Ensure the data folder exists
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Read SQL instructions
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    if not schema_sql.strip():
        raise ValueError("schema.sql is empty!")

    # Connect to SQLite
    with sqlite3.connect(DATABASE_PATH) as connection:

        # Enforce foreign key relationships
        connection.execute("PRAGMA foreign_keys = ON")

        # Execute all SQL statements
        connection.executescript(schema_sql)

        # Verify foreign key integrity
        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        # Get all created tables
        tables = connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

    # Display database results
    print("\nDatabase created successfully!")
    print(f"Database location: {DATABASE_PATH}")

    print("\nTables created:")

    for index, (table_name,) in enumerate(tables, start=1):
        print(f"{index}. {table_name}")

    print(f"\nTotal tables: {len(tables)}")

    if foreign_key_errors:
        print("\nForeign key validation FAILED:")
        for error in foreign_key_errors:
            print(error)
        return False

    print("\nForeign key validation: PASSED")

    if len(tables) != 16:
        print("WARNING: Expected 16 tables.")
        return False

    print("Schema table-count validation: PASSED")
    print("\nDatabase initialization completed!")
    return True


if __name__ == "__main__":
    try:
        success = initialize_database()
        if not success:
            sys.exit(1)
    except Exception as error:
        print(f"\nDatabase initialization failed: {error}")
        sys.exit(1)
