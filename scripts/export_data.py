
import argparse
import csv
import sqlite3

from pathlib import Path


# =====================================================
# PROJECT CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATABASE = (
    PROJECT_ROOT
    / "data"
    / "reconciliation_full_scale_anomaly_test.db"
)

DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "exports"
    / "full_scale_anomaly_test"
)

# All application tables to export.
EXPORT_TABLES = [
    "app_users",
    "merchants",
    "payment_orders",
    "payment_attempts",
    "processor_events",
    "settlement_batches",
    "settlement_lines",
    "bank_statement_lines",
    "source_feed_manifests",
    "reconciliation_runs",
    "reconciliation_matches",
    "reconciliation_allocations",
    "exceptions",
    "exception_events",
    "resolutions",
    "exception_entity_links"
]


# =====================================================
# EXPORT ONE TABLE TO CSV
# =====================================================

def export_table(connection, table_name, output_dir):

    output_file = output_dir / f"{table_name}.csv"

    query = f'SELECT * FROM "{table_name}"'

    cursor = connection.execute(query)

    headers = [
        description[0]
        for description in cursor.description
    ]

    exported_count = 0

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        # Export in batches to avoid loading large
        # database tables entirely into memory.
        while True:

            rows = cursor.fetchmany(5000)

            if not rows:
                break

            writer.writerows(rows)

            exported_count += len(rows)

    expected_count = connection.execute(
        f'SELECT COUNT(*) FROM "{table_name}"'
    ).fetchone()[0]

    if exported_count != expected_count:
        raise RuntimeError(
            f"Export verification failed for {table_name}: "
            f"expected {expected_count}, exported {exported_count}."
        )

    return output_file, exported_count


# =====================================================
# VERIFY DATABASE TABLES
# =====================================================

def validate_tables(connection):

    available_tables = {
        row[0]
        for row in connection.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
        """).fetchall()
    }

    missing_tables = [
        table
        for table in EXPORT_TABLES
        if table not in available_tables
    ]

    if missing_tables:
        raise RuntimeError(
            f"Required database tables missing: {missing_tables}"
        )


# =====================================================
# EXPORT SUMMARY
# =====================================================

def write_export_summary(export_results, output_dir):

    summary_file = output_dir / "dataset_summary.csv"

    with open(
        summary_file,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "table_name",
            "record_count",
            "export_file",
            "export_status"
        ])

        for table_name, count, filename in export_results:

            writer.writerow([
                table_name,
                count,
                filename,
                "SUCCESS"
            ])

    return summary_file


# =====================================================
# EXPORT NOTES
# =====================================================

def write_export_notes(database_path, output_dir):

    notes_file = output_dir / "EXPORT_NOTES.txt"

    notes = f"""
YOTTAFLEX PAYMENT RECONCILIATION
CSV EXPORT INFORMATION
================================

Source database:
{database_path}

Export format:
CSV (UTF-8 with BOM)

Encoding:
UTF-8-SIG

Financial amounts:
Stored in integer minor currency units.

Examples:
INR 100.50 = 10050 paise
USD 100.50 = 10050 cents

Dataset:
Full-scale anomaly-testing dataset.

Important:
- These exports are synthetic project data.
- Ground-truth labels are maintained separately.
- Ground-truth data is not reconciliation engine input.
- The original clean full-scale database is unchanged.
"""

    notes_file.write_text(
        notes.strip() + "\n",
        encoding="utf-8"
    )

    return notes_file


# =====================================================
# MAIN EXPORT PROGRAM
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Export YottaFlex reconciliation database "
            "tables into individual CSV files."
        )
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="SQLite database to export."
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for exported CSV files."
    )

    args = parser.parse_args()

    database_path = args.database
    output_dir = args.output_dir

    if not database_path.exists():
        parser.error(
            f"Database does not exist: {database_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(database_path)

    try:

        # Prevent accidental database modifications.
        connection.execute(
            "PRAGMA query_only = ON"
        )

        validate_tables(connection)

        print("\nYOTTAFLEX CSV EXPORT")
        print("====================")
        print(f"Source database: {database_path}")
        print(f"Export directory: {output_dir}")

        export_results = []

        for table_name in EXPORT_TABLES:

            output_file, record_count = export_table(
                connection,
                table_name,
                output_dir
            )

            export_results.append((
                table_name,
                record_count,
                output_file.name
            ))

            print(
                f"EXPORTED: {table_name}.csv "
                f"({record_count} records)"
            )

        summary_file = write_export_summary(
            export_results,
            output_dir
        )

        notes_file = write_export_notes(
            database_path,
            output_dir
        )

        total_records = sum(
            count
            for _, count, _ in export_results
        )

        print("\nEXPORT VALIDATION")
        print("-----------------")

        print(
            f"Tables exported: {len(export_results)}"
        )

        print(
            f"Total records exported: {total_records}"
        )

        print(
            f"Summary file: {summary_file}"
        )

        print(
            f"Export notes: {notes_file}"
        )

        print("\nCSV EXPORT: PASSED")

    finally:

        connection.close()


if __name__ == "__main__":
    main()
