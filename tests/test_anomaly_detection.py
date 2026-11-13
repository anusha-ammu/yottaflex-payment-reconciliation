
import csv
import json
import shutil
import sqlite3
import sys

from collections import Counter
from pathlib import Path

import pytest


# =====================================================
# PROJECT PATHS AND IMPORTS
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(
    0,
    str(PROJECT_ROOT / "src" / "reconciliation")
)

import matching
from scripts import inject_anomalies


CLEAN_DATABASE = (
    PROJECT_ROOT / "data" / "reconciliation_clean_backup.db"
)


# =====================================================
# TEST 1: CLEAN DATABASE
# =====================================================

def test_clean_database_reconciliation(tmp_path):

    test_database = tmp_path / "clean_test.db"

    shutil.copy2(
        CLEAN_DATABASE,
        test_database
    )

    matching.run_reconciliation(
        replace_existing=True,
        database_path=test_database
    )

    connection = sqlite3.connect(test_database)

    try:

        exception_count = connection.execute("""
            SELECT COUNT(*) FROM exceptions
        """).fetchone()[0]

        match_count = connection.execute("""
            SELECT COUNT(*) FROM reconciliation_matches
        """).fetchone()[0]

        statuses = {
            row[0]
            for row in connection.execute("""
                SELECT DISTINCT match_status
                FROM reconciliation_matches
            """)
        }

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert exception_count == 0

        assert match_count > 0

        assert statuses == {"MATCHED"}

        assert foreign_key_errors == []

    finally:
        connection.close()


# =====================================================
# TEST 2: ALL SIX ANOMALIES
# =====================================================

def test_all_six_anomalies_detected(
    tmp_path,
    monkeypatch
):

    test_database = (
        tmp_path / "anomaly_test.db"
    )

    ground_truth_dir = (
        tmp_path / "ground_truth"
    )

    ground_truth_json = (
        ground_truth_dir / "anomaly_ground_truth.json"
    )

    ground_truth_csv = (
        ground_truth_dir / "anomaly_ground_truth.csv"
    )

    # Direct the injection script to temporary files.
    monkeypatch.setattr(
        inject_anomalies,
        "CLEAN_DATABASE",
        CLEAN_DATABASE
    )

    monkeypatch.setattr(
        inject_anomalies,
        "TEST_DATABASE",
        test_database
    )

    monkeypatch.setattr(
        inject_anomalies,
        "GROUND_TRUTH_DIR",
        ground_truth_dir
    )

    monkeypatch.setattr(
        inject_anomalies,
        "GROUND_TRUTH_JSON",
        ground_truth_json
    )

    monkeypatch.setattr(
        inject_anomalies,
        "GROUND_TRUTH_CSV",
        ground_truth_csv
    )

    # Step 1: Inject all six anomalies.
    inject_anomalies.main()

    # Step 2: Run reconciliation.
    matching.run_reconciliation(
        replace_existing=True,
        database_path=test_database
    )

    # Step 3: Read ground-truth labels.
    with open(
        ground_truth_json,
        "r",
        encoding="utf-8"
    ) as file:

        ground_truth = json.load(file)

    expected_types = Counter(
        item["expected_exception_type"]
        for item in ground_truth["anomalies"]
    )

    # Step 4: Read actual engine exceptions.
    connection = sqlite3.connect(test_database)

    try:

        actual_types = Counter(
            row[0]
            for row in connection.execute("""
                SELECT exception_type
                FROM exceptions
            """)
        )

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    finally:
        connection.close()

    # Step 5: Compare expected and actual results.
    assert len(ground_truth["anomalies"]) == 6

    assert expected_types == actual_types, (
        f"Expected exceptions: {expected_types}\n"
        f"Actual exceptions: {actual_types}"
    )

    assert ground_truth_json.exists()
    assert ground_truth_csv.exists()

    assert foreign_key_errors == []


# =====================================================
# TEST 3: GROUND TRUTH STRUCTURE
# =====================================================

def test_ground_truth_contains_six_unique_scenarios():

    ground_truth_path = (
        PROJECT_ROOT
        / "data"
        / "ground_truth"
        / "anomaly_ground_truth.json"
    )

    with open(
        ground_truth_path,
        "r",
        encoding="utf-8"
    ) as file:

        ground_truth = json.load(file)

    anomaly_ids = [
        item["anomaly_id"]
        for item in ground_truth["anomalies"]
    ]

    expected_types = {
        "DUPLICATE_SETTLEMENT_LINE",
        "FEE_VARIANCE",
        "REFUND_BEFORE_CAPTURE",
        "MISSING_SOURCE_RECORD",
        "CURRENCY_MISMATCH",
        "DUPLICATE_PROCESSOR_EVENT"
    }

    actual_types = {
        item["expected_exception_type"]
        for item in ground_truth["anomalies"]
    }

    assert len(anomaly_ids) == 6
    assert len(set(anomaly_ids)) == 6
    assert actual_types == expected_types
    assert ground_truth["engine_input"] is False
