# YottaFlex Payment Reconciliation System
# System Architecture

## 1. Introduction

YottaFlex Payment Reconciliation is a synthetic payment reconciliation platform that automates the comparison of payment processor settlements against bank statement transactions.

The architecture is organized into data generation, database storage, settlement processing, reconciliation, exception management, evaluation, and presentation layers.

The system is implemented using Python, SQLite, and Streamlit.

## 2. High-Level Architecture

```text
                 SYNTHETIC DATA SOURCES
                          |
          +---------------+---------------+
          |               |               |
       Merchants        Payments       Bank Data
          |               |               |
          +---------------+---------------+
                          |
                          v
                 PAYMENT PROCESSING
                          |
                 Processor Events
                          |
                          v
                 SETTLEMENT ENGINE
                          |
                 Settlement Batches
                 Settlement Lines
                          |
                          v
                 BANK STATEMENT DATA
                          |
                          v
                RECONCILIATION ENGINE
                          |
              +-----------+-----------+
              |                       |
              v                       v
           MATCHED               EXCEPTIONS
                                      |
                                      v
                            EXCEPTION MANAGEMENT
                                      |
                           Assignment / Investigation
                                      |
                              Resolution / Closure
                                      |
                                      v
                                AUDIT HISTORY

              +-----------------------------+
              |       PRESENTATION          |
              |                             |
              |   Streamlit Dashboard       |
              |   CSV Exports               |
              |   Ground Truth Evaluation   |
              +-----------------------------+
```

## 3. Architecture Components

### 3.1 Data Generation Layer

Location: `scripts/`

Responsible for creating deterministic synthetic payment and settlement data.

Main modules:

- `generate_master_data.py`: Generates merchant records and application users.
- `generate_payment_data.py`: Generates payment orders, attempts, and processor events.
- `generate_settlements.py`: Calculates fees and creates settlement batches and settlement lines.
- `generate_bank_statements.py`: Generates synthetic bank transactions.
- `generate_refunds.py`: Supports refund data generation.

The default random seed is 20261022.

### 3.2 Database Layer

Location: `src/database/`

The application uses SQLite for relational storage.

Main schema file:

`src/database/schema.sql`

The database contains entities for:

- Merchants and application users.
- Payment orders and payment attempts.
- Processor events.
- Settlement batches and settlement lines.
- Bank statement lines.
- Source feed manifests.
- Reconciliation runs and matches.
- Exceptions and exception events.
- Exception resolutions and entity relationships.

Foreign-key relationships maintain referential integrity between related records.

### 3.3 Settlement Processing Layer

Location: `scripts/generate_settlements.py`

The settlement engine groups eligible financial events by:

- Merchant.
- Payment processor.
- Currency.

It calculates gross captures, refunds, processor fees, adjustments, and net settlement amounts.

Processor fees use a basis-point calculation.

The configured processor fee is 200 basis points, equivalent to 2%.

Financial amounts are stored as integer minor currency units to avoid floating-point rounding errors.

### 3.4 Bank Statement Layer

Location: `scripts/generate_bank_statements.py`

The bank statement generator creates synthetic bank transactions.

For the full-scale dataset:

- 1,000 settlement payout lines.
- 4,000 other bank activity lines.
- 5,000 total bank statement lines.

Each settlement payout is associated with its corresponding payout reference, amount, currency, and merchant.

### 3.5 Reconciliation Layer

Location: `src/reconciliation/matching.py`

The reconciliation engine compares expected settlement batches with eligible bank payout transactions.

It evaluates settlement and bank records using their financial values and identifying references.

Possible reconciliation outcomes include:

- MATCHED
- REVIEW_REQUIRED

The engine records reconciliation decisions and creates exception records when discrepancies are detected.

### 3.6 Exception Management Layer

Location: `src/exceptions/workflow.py`

This component manages the exception lifecycle.

Supported operations:

1. Exception assignment.
2. Investigation note creation.
3. Exception resolution.
4. Exception closure.
5. Audit event tracking.

The audit history records previous status, new status, action type, actor, notes, and timestamps.

### 3.7 Anomaly Injection and Evaluation

Location: `scripts/inject_anomalies.py`

The anomaly injector introduces controlled synthetic data inconsistencies for testing.

The six supported scenarios are:

1. Duplicate settlement line.
2. Fee variance.
3. Refund before capture.
4. Missing source record.
5. Currency mismatch.
6. Duplicate processor event.

Ground-truth labels are stored separately in JSON and CSV formats.

Ground truth is evaluation data and is not used as input to the reconciliation engine.

### 3.8 Presentation Layer

Location: `app/app.py`

The Streamlit dashboard provides:

- Reconciliation overview.
- Settlement and payment metrics.
- Exception management.
- Investigation controls.
- Exception resolution.
- Audit history.

The dashboard is intended for local demonstration.

### 3.9 Export Layer

Location: `scripts/export_data.py`

Exports database tables into individual CSV files.

Exported records include merchants, payments, attempts, processor events, settlements, bank transactions, reconciliation results, exceptions, resolutions, and audit history.

## 4. Database Environment Separation

The project maintains separate database environments.

| Database | Purpose |
|---|---|
| `data/reconciliation.db` | Original starter database |
| `data/reconciliation_clean_backup.db` | Clean starter test fixture |
| `data/reconciliation_anomaly_test.db` | Starter anomaly test database |
| `data/reconciliation_full_scale.db` | Clean full-scale dataset |
| `data/reconciliation_full_scale_anomaly_test.db` | Full-scale anomaly evaluation |

The clean full-scale database is preserved separately from the full-scale anomaly-testing database.

## 5. Full-Scale Dataset

The full-scale baseline contains:

| Dataset | Records |
|---|---:|
| Merchants | 2,000 |
| Payment orders | 50,000 |
| Payment attempts | 55,000 |
| Processor events | 100,001 |
| Settlement batches | 1,000 |
| Settlement lines | 90,002 |
| Bank statement lines | 5,000 |

The anomaly-testing database contains additional records introduced by controlled anomaly injection.

## 6. Reconciliation Results

### Clean Full-Scale Baseline

| Metric | Result |
|---|---:|
| Settlement batches | 1,000 |
| Matched settlements | 1,000 |
| Review required | 0 |
| Exceptions | 0 |
| Foreign-key errors | 0 |

### Full-Scale Anomaly Evaluation

| Metric | Result |
|---|---:|
| Settlement batches | 1,000 |
| Matched | 999 |
| Review required | 1 |
| Detected exceptions | 6 |
| Ground-truth agreement | Exact match |
| Foreign-key errors | 0 |

## 7. Validation and Testing

The project includes automated tests implemented using Pytest.

The latest verified regression test result was:

`4 passed in 0.44s`

Additional full-scale validation confirmed:

- Dataset target counts.
- Settlement arithmetic.
- Bank payout amount consistency.
- Currency consistency.
- Foreign-key integrity.
- SQLite database integrity.
- Six anomaly detections.
- Exact agreement with independent ground truth.

The four automated regression tests primarily exercise the starter test fixtures. Full-scale behavior is additionally verified through dedicated database checks and reconciliation runs.

## 8. Execution Flow

The recommended execution sequence is:

1. Initialize the database.
2. Generate merchant master data.
3. Generate payment data.
4. Generate settlement batches.
5. Generate bank statement data.
6. Run baseline reconciliation.
7. Create a separate anomaly-testing database.
8. Inject synthetic anomalies.
9. Run anomaly reconciliation.
10. Compare detected exceptions against ground truth.
11. Export database tables.
12. Review results through the Streamlit dashboard.

## 9. Technology Stack

| Technology | Application |
|---|---|
| Python | Business logic and data generation |
| SQLite | Relational database |
| Streamlit | Dashboard |
| Pandas | Data processing |
| Faker | Synthetic merchant data |
| Pytest | Automated tests |
| CSV | Data exports |
| JSON | Ground-truth evaluation labels |

## 10. Limitations

- All transaction data is synthetic.
- Processor and banking integrations are simulated.
- The dashboard runs locally.
- The project is a demonstration implementation rather than a production payment platform.
- Production authentication, cloud deployment, real bank connectivity, and real processor integrations are outside the current implementation.

## 11. Conclusion

The architecture demonstrates an end-to-end payment reconciliation workflow, including synthetic data generation, settlement processing, bank matching, anomaly detection, exception lifecycle management, audit history, and independent evaluation.

The clean full-scale reconciliation and full-scale anomaly evaluation have both been executed successfully.

---

**Project:** YottaFlex Payment Reconciliation System  
**Challenge:** YottaFlex.ai Associate AI Forward Deployed Engineer Code Challenge