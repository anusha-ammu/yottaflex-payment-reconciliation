
import sys
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# =====================================================
# PROJECT CONFIGURATION
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from exceptions.workflow import (
    connect_database,
    list_exceptions,
    assign_exception,
    add_note,
    resolve_exception,
    close_exception,
    get_exception_history
)


DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "exception_workflow_test.db"
)


# =====================================================
# STREAMLIT PAGE
# =====================================================

st.set_page_config(
    page_title="YottaFlex Reconciliation",
    page_icon="💳",
    layout="wide"
)

st.title("YottaFlex.ai")
st.subheader("Payment Reconciliation & Exception Management")

st.caption(
    "Monitor settlement reconciliation, investigate anomalies "
    "and manage exception resolution."
)

if not DATABASE_PATH.exists():

    st.error(
        f"Database not found: {DATABASE_PATH}"
    )

    st.stop()


# =====================================================
# DATABASE CONNECTION
# =====================================================

try:

    connection = connect_database(DATABASE_PATH)

except Exception as error:

    st.error(f"Database connection failed: {error}")
    st.stop()


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select a page",
    [
        "Overview",
        "Exception Management",
        "Audit History"
    ]
)

st.sidebar.divider()

st.sidebar.caption("Database")

st.sidebar.success(
    "Anomaly demonstration database connected"
)


# =====================================================
# OVERVIEW DATA
# =====================================================

def get_scalar(query, parameters=()):

    return connection.execute(
        query,
        parameters
    ).fetchone()[0]


if page == "Overview":

    st.header("Reconciliation Overview")

    total_batches = get_scalar("""
        SELECT COUNT(*) FROM settlement_batches
    """)

    total_bank_lines = get_scalar("""
        SELECT COUNT(*) FROM bank_statement_lines
        WHERE description = 'SETTLEMENT_PAYOUT'
    """)

    total_matches = get_scalar("""
        SELECT COUNT(*) FROM reconciliation_matches
    """)

    matched = get_scalar("""
        SELECT COUNT(*)
        FROM reconciliation_matches
        WHERE match_status = 'MATCHED'
    """)

    review = get_scalar("""
        SELECT COUNT(*)
        FROM reconciliation_matches
        WHERE match_status = 'REVIEW_REQUIRED'
    """)

    total_exceptions = get_scalar("""
        SELECT COUNT(*) FROM exceptions
    """)

    open_exceptions = get_scalar("""
        SELECT COUNT(*) FROM exceptions
        WHERE exception_status = 'OPEN'
    """)

    in_review = get_scalar("""
        SELECT COUNT(*) FROM exceptions
        WHERE exception_status = 'IN_REVIEW'
    """)

    resolved = get_scalar("""
        SELECT COUNT(*) FROM exceptions
        WHERE exception_status = 'RESOLVED'
    """)

    closed = get_scalar("""
        SELECT COUNT(*) FROM exceptions
        WHERE exception_status = 'CLOSED'
    """)

    # ---------------------------------------------
    # KPI CARDS
    # ---------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Settlement Batches",
        total_batches
    )

    col2.metric(
        "Bank Payout Lines",
        total_bank_lines
    )

    col3.metric(
        "Matched",
        matched
    )

    col4.metric(
        "Review Required",
        review
    )

    st.divider()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Exceptions",
        total_exceptions
    )

    col2.metric(
        "Open",
        open_exceptions
    )

    col3.metric(
        "In Review",
        in_review
    )

    col4.metric(
        "Resolved / Closed",
        resolved + closed
    )

    st.divider()

    # ---------------------------------------------
    # EXCEPTION BREAKDOWN
    # ---------------------------------------------

    st.subheader("Exception Type Breakdown")

    exception_data = pd.read_sql_query("""
        SELECT
            exception_type,
            COUNT(*) AS total
        FROM exceptions
        GROUP BY exception_type
        ORDER BY total DESC
    """, connection)

    if not exception_data.empty:

        st.bar_chart(
            exception_data.set_index("exception_type")
        )

    else:

        st.info("No exceptions available.")

    # ---------------------------------------------
    # STATUS BREAKDOWN
    # ---------------------------------------------

    st.subheader("Exception Status Breakdown")

    status_data = pd.read_sql_query("""
        SELECT
            exception_status,
            COUNT(*) AS total
        FROM exceptions
        GROUP BY exception_status
    """, connection)

    if not status_data.empty:

        st.bar_chart(
            status_data.set_index("exception_status")
        )

    st.caption(
        "Dashboard figures are read directly from the selected "
        "SQLite database."
    )


# =====================================================
# EXCEPTION MANAGEMENT
# =====================================================

elif page == "Exception Management":

    st.header("Exception Management")

    status_filter = st.selectbox(
        "Filter by status",
        [
            "ALL",
            "OPEN",
            "IN_REVIEW",
            "RESOLVED",
            "CLOSED"
        ]
    )

    selected_status = (
        None if status_filter == "ALL"
        else status_filter
    )

    exceptions = list_exceptions(
        connection,
        selected_status
    )

    if not exceptions:

        st.info("No exceptions found for this filter.")

    else:

        exception_table = pd.DataFrame(exceptions)

        display_columns = [
            "exception_id",
            "exception_type",
            "severity",
            "exception_status",
            "assigned_to_name"
        ]

        st.dataframe(
            exception_table[display_columns],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Investigate an Exception")

        selected_exception_id = st.selectbox(
            "Choose exception",
            [
                item["exception_id"]
                for item in exceptions
            ],
            format_func=lambda value: (
                next(
                    (
                        item["exception_type"]
                        + " — "
                        + item["exception_id"]
                        for item in exceptions
                        if item["exception_id"] == value
                    ),
                    value
                )
            )
        )

        selected_exception = next(
            item
            for item in exceptions
            if item["exception_id"] == selected_exception_id
        )

        st.write(
            "**Description:**",
            selected_exception["description"]
        )

        st.write(
            "**Severity:**",
            selected_exception["severity"]
        )

        st.write(
            "**Current status:**",
            selected_exception["exception_status"]
        )

        st.write(
            "**Assigned to:**",
            selected_exception.get("assigned_to_name") or "Unassigned"
        )

        st.divider()

        # -----------------------------------------
        # USER LIST
        # -----------------------------------------

        users = connection.execute("""
            SELECT user_id, display_name, role
            FROM app_users
            WHERE is_active = 1
              AND role IN (
                  'OPS_ANALYST',
                  'RISK_COMPLIANCE_REVIEWER',
                  'SYSTEM_ADMIN'
              )
            ORDER BY display_name
        """).fetchall()

        user_map = {
            row["display_name"]: row["user_id"]
            for row in users
        }

        actor_map = {
            row["user_id"]: row["display_name"]
            for row in users
        }

        actor_name = st.selectbox(
            "Acting user",
            list(actor_map.values()),
            key="actor_user"
        )

        actor_id = next(
            key
            for key, value in actor_map.items()
            if value == actor_name
        )

        current_status = selected_exception["exception_status"]

        # -----------------------------------------
        # ASSIGNMENT
        # -----------------------------------------

        if current_status in ("OPEN", "IN_REVIEW"):

            st.subheader("Assign Exception")

            with st.form("assign_form"):

                assignee_name = st.selectbox(
                    "Assign to",
                    list(user_map.keys())
                )

                assignment_notes = st.text_input(
                    "Assignment note",
                    value="Assigned for investigation."
                )

                assign_button = st.form_submit_button(
                    "Assign Exception"
                )

                if assign_button:

                    try:

                        result = assign_exception(
                            connection,
                            selected_exception_id,
                            user_map[assignee_name],
                            actor_id,
                            assignment_notes
                        )

                        st.success(
                            f"Assigned to {result['assigned_to']}"
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(str(error))

        # -----------------------------------------
        # INVESTIGATION NOTES
        # -----------------------------------------

        if current_status in ("OPEN", "IN_REVIEW"):

            st.subheader("Investigation Notes")

            with st.form("note_form"):

                investigation_note = st.text_area(
                    "Enter investigation findings"
                )

                note_button = st.form_submit_button(
                    "Save Investigation Note"
                )

                if note_button:

                    try:

                        add_note(
                            connection,
                            selected_exception_id,
                            actor_id,
                            investigation_note
                        )

                        st.success("Investigation note saved.")

                        st.rerun()

                    except Exception as error:

                        st.error(str(error))

        # -----------------------------------------
        # RESOLUTION
        # -----------------------------------------

        if current_status == "IN_REVIEW":

            st.subheader("Resolve Exception")

            with st.form("resolution_form"):

                action = st.text_input(
                    "Resolution action",
                    "INVESTIGATE_AND_VERIFY"
                )

                outcome = st.text_input(
                    "Resolution outcome",
                    "EXCEPTION_VERIFIED"
                )

                resolution_notes = st.text_area(
                    "Resolution notes"
                )

                resolve_button = st.form_submit_button(
                    "Resolve Exception"
                )

                if resolve_button:

                    try:

                        resolve_exception(
                            connection,
                            selected_exception_id,
                            actor_id,
                            action,
                            outcome,
                            resolution_notes
                        )

                        st.success("Exception resolved.")

                        st.rerun()

                    except Exception as error:

                        st.error(str(error))

        # -----------------------------------------
        # CLOSURE
        # -----------------------------------------

        if current_status == "RESOLVED":

            st.subheader("Close Exception")

            closure_notes = st.text_input(
                "Closure notes",
                "Resolution reviewed and verified."
            )

            if st.button("Close Exception"):

                try:

                    close_exception(
                        connection,
                        selected_exception_id,
                        actor_id,
                        closure_notes
                    )

                    st.success("Exception closed.")

                    st.rerun()

                except Exception as error:

                    st.error(str(error))


# =====================================================
# AUDIT HISTORY
# =====================================================

elif page == "Audit History":

    st.header("Exception Audit History")

    history_ids = connection.execute("""
        SELECT exception_id
        FROM exceptions
        ORDER BY detected_at DESC
    """).fetchall()

    if not history_ids:

        st.info("No audit records available.")

    else:

        exception_id = st.selectbox(
            "Select exception",
            [row["exception_id"] for row in history_ids]
        )

        history = get_exception_history(
            connection,
            exception_id
        )

        if history:

            history_df = pd.DataFrame(history)

            st.dataframe(
                history_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info("No audit history available.")


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "YottaFlex.ai | Synthetic Payment Reconciliation Demo"
)

connection.close()
