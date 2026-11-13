
# YottaFlex Payment Reconciliation System

An end-to-end synthetic payment reconciliation platform developed for the YottaFlex.ai Associate AI Forward Deployed Engineer Code Challenge.

The system processes payment orders, processor events, settlement batches, and bank statements. It identifies reconciliation discrepancies, detects anomalies, and supports exception investigation, resolution, and audit tracking.

## 1. Project Overview

YottaFlex Payment Reconciliation automates the comparison of payment processor settlements against bank statement transactions.

The platform supports:

- Synthetic merchant and payment data generation.
- Payment attempt and processor event tracking.
- Settlement batch generation.
- Processor fee and refund calculations.
- Bank statement ingestion and validation.
- Automated settlement reconciliation.
- Duplicate and financial anomaly detection.
- Exception assignment and resolution.
- Complete exception audit history.
- Independent ground-truth evaluation.
- CSV data exports.
- Interactive Streamlit dashboard.

All generated transaction data is synthetic.

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and data generation |
| SQLite | Relational database |
| Pandas | Data processing and analysis |
| Streamlit | Interactive dashboard |
| Faker | Synthetic merchant data |
| Pytest | Automated testing |
| CSV / JSON | Data exports and evaluation labels |

## 3. Project Structure

```text
yottaflex-payment-reconciliation/
|
|-- app/
|   |-- app.py
|
|-- data/
|   |-- reconciliation.db
|   |-- reconciliation_clean_backup.db
|   |-- reconciliation_anomaly_test.db
|   |-- reconciliation_full_scale.db
|   |-- reconciliation_full_scale_anomaly_test.db
|   |-- ground_truth/
|   |-- ground_truth_full_scale/
|
|-- docs/
|
|-- exports/
|   |-- full_scale_anomaly_test/
|
|-- scripts/
|   |-- init_db.py
|   |-- generate_master_data.py
|   |-- generate_payment_data.py
|   |-- generate_settlements.py
|   |-- generate_bank_statements.py
|   |-- generate_refunds.py
|   |-- inject_anomalies.py
|   |-- export_data.py
|   |-- verify_bank_statements.py
|   |-- verify_refunds.py
|   |-- verify_settlements.py
|   |-- smoke_test_db.py
|   |-- fix_missing_capture.py
|
|-- src/
|   |-- database/
|   |   |-- schema.sql
|   |
|   |-- reconciliation/
|   |   |-- matching.py
|   |
|   |-- exceptions/
|   |   |-- workflow.py
|   |
|   |-- generator/
|   |
|   |-- validation/
|
|-- tests/
|   |-- test_anomaly_detection.py
|   |-- test_exception_workflow.py
|
|-- README.md
|-- requirements.txt
|-- .gitignore
```

## 4. Full-Scale Synthetic Dataset

The full-scale dataset was generated using the deterministic seed:

`20261022`

| Dataset | Record Count |
|---|---:|
| Merchants | 2,000 |
| Payment orders | 50,000 |
| Payment attempts | 55,000 |
| Processor events | 100,001 |
| Settlement batches | 1,000 |
| Settlement lines | 90,002 |
| Bank statement lines | 5,000 |

The separate full-scale anomaly-testing database contains additional synthetic anomaly records.

### Bank Statement Distribution

| Transaction category | Records |
|---|---:|
| Settlement payout lines | 1,000 |
| Other account activity | 4,000 |
| Total | 5,000 |

## 5. System Architecture

The system consists of the following major components.

### Synthetic Data Generation

Generates merchants, payment orders, attempts, processor events, settlement batches, and bank statement records.

### Settlement Generation

Calculates processor fees using integer minor currency units and builds traceable settlement lines.

### Reconciliation Engine

Compares expected settlement payouts with actual bank statement credits using payout references, amounts, and currencies.

### Anomaly Detection

Identifies inconsistent or duplicate financial records and other reconciliation exceptions.

### Exception Management

Supports:

- Exception assignment.
- Investigation notes.
- Resolution.
- Closure.
- Audit event tracking.

### Dashboard

Provides an interactive Streamlit interface for monitoring reconciliation results and managing exceptions.

## 6. Reconciliation Workflow

1. Generate synthetic merchant master data.
2. Generate payment orders and payment attempts.
3. Record processor authorization, failure, and capture events.
4. Calculate settlement fees and net settlement amounts.
5. Generate settlement batches and settlement lines.
6. Generate synthetic bank statement records.
7. Reconcile settlements against bank transactions.
8. Identify discrepancies and create exceptions.
9. Assign and investigate exceptions.
10. Resolve and close exceptions.
11. Maintain an auditable record of exception lifecycle events.

## 7. Supported Anomaly Scenarios

The project implements six synthetic anomaly scenarios.

| ID | Anomaly | Expected Exception |
|---|---|---|
| A1 | Duplicate settlement line | DUPLICATE_SETTLEMENT_LINE |
| A2 | Bank amount differs by processor fee | FEE_VARIANCE |
| A3 | Refund before capture | REFUND_BEFORE_CAPTURE |
| A4 | Missing source record | MISSING_SOURCE_RECORD |
| A5 | Currency mismatch | CURRENCY_MISMATCH |
| A6 | Duplicate processor event | DUPLICATE_PROCESSOR_EVENT |

Ground-truth labels are maintained separately from reconciliation engine inputs.

The refund-before-capture full-scale test uses an intentionally inserted synthetic refund event because the clean full-scale baseline contains no refund events.

## 8. Database Organization

Three important database roles are maintained:

| Database | Purpose |
|---|---|
| reconciliation.db | Original starter database |
| reconciliation_full_scale.db | Clean full-scale baseline |
| reconciliation_full_scale_anomaly_test.db | Full-scale anomaly evaluation |

The clean full-scale database is preserved independently from anomaly injection.

## 9. Validation Results

### Clean Full-Scale Reconciliation

| Metric | Result |
|---|---:|
| Settlement batches processed | 1,000 |
| Matched settlements | 1,000 |
| Review required | 0 |
| Exceptions | 0 |
| Foreign-key errors | 0 |

### Full-Scale Anomaly Testing

| Metric | Result |
|---|---:|
| Settlement batches processed | 1,000 |
| Matched | 999 |
| Review required | 1 |
| Detected exceptions | 6 |
| Expected exception types | 6 |
| Actual exception types | 6 |
| Ground-truth agreement | Exact match |
| Foreign-key errors | 0 |

### Database Integrity

Both full-scale databases passed SQLite integrity checks.

## 10. Automated Testing

Run the complete test suite:

```powershell
python -m pytest -v
```

Latest verified result:

```text
4 passed in 0.44s
```

Tests cover:

- Clean database reconciliation.
- Detection of all six anomaly scenarios.
- Ground-truth scenario uniqueness.
- Complete exception lifecycle.

## 11. Running the Application

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the Streamlit dashboard:

```powershell
python -m streamlit run .\app\app.py
```

Open:

http://localhost:8501

The dashboard uses the SQLite database path configured in `app/app.py`.

## 12. Running Full-Scale Reconciliation

Clean baseline:

```powershell
python .\src\reconciliation\matching.py --database .\data\reconciliation_full_scale.db --replace-existing
```

Full-scale anomaly testing:

```powershell
python .\src\reconciliation\matching.py --database .\data\reconciliation_full_scale_anomaly_test.db --replace-existing
```

The anomaly-testing database must contain the injected anomalies before running the second command.

## 13. CSV Data Exports

Generate the full-scale CSV exports:

```powershell
python .\scripts\export_data.py --database .\data\reconciliation_full_scale_anomaly_test.db --output-dir .\exports\full_scale_anomaly_test
```

The export process creates CSV files for:

- Merchants.
- Payment orders.
- Payment attempts.
- Processor events.
- Settlement batches.
- Settlement lines.
- Bank statement lines.
- Reconciliation runs and matches.
- Exceptions and exception history.
- Supporting relationships and feed manifests.

The latest verified export contains:

- 16 exported database tables.
- 305,035 exported records.
- A dataset summary.
- Export notes.

## 14. Financial Data Handling

Financial amounts are represented using integer minor currency units.

Examples:

- INR 100.50 = 10,050 paise.
- USD 100.50 = 10,050 cents.
- EUR 100.50 = 10,050 cents.

Integer arithmetic is used to avoid floating-point rounding errors in financial calculations.

Processor fees are calculated using basis points.

## 15. Reproducibility and Ground Truth

Synthetic data generation uses a fixed random seed.

Ground-truth evaluation files are stored separately:

```text
data/
|-- ground_truth/
|-- ground_truth_full_scale/
```

Ground-truth labels are used only to evaluate detected exceptions.

They are never supplied to the reconciliation engine as input.

## 16. Project Limitations

- The datasets are synthetic and do not represent real payment transactions.
- Processor and bank integrations are simulated.
- Refund-before-capture testing uses an intentionally injected synthetic event.
- The dashboard is a local demonstration application.
- The full-scale data represents a deterministic test scenario, not a live production environment.

## 17. Future Improvements

Potential extensions include:

- Real payment processor integrations.
- Automated bank feed ingestion.
- Advanced reconciliation matching strategies.
- Risk scoring and anomaly prioritization.
- Additional automated regression tests.
- Production deployment and authentication.
- Improved dashboard analytics and exports.

## 18. Project Status

Core full-scale data generation, reconciliation, anomaly detection, exception management, and CSV exports have been implemented and validated.

The latest verified regression suite contains four passing tests.

Documentation and final submission preparation are in progress.

---

Developed for the YottaFlex.ai Associate AI Forward Deployed Engineer Code Challenge.
