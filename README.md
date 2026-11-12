
# YottaFlex Payment Reconciliation System

## Project Overview

This project is an end-to-end payment reconciliation system developed for the YottaFlex.ai Associate AI Forward Deployed Engineer Code Challenge.

The system reconciles payment instructions, payment processor events, settlement batches, and bank statement records.

It identifies unmatched transactions, amount discrepancies, duplicate events, and other payment anomalies.

## Objectives

- Generate realistic synthetic payment data.
- Manage merchants, payment orders, and payment attempts.
- Track payment processor events.
- Calculate settlement batches, fees, and refunds.
- Reconcile settlements against bank statements.
- Detect and manage exceptions.
- Maintain a complete audit history.
- Evaluate reconciliation accuracy using ground truth.

## Technology Stack

- Python
- SQLite
- Pandas
- NumPy
- Faker
- Streamlit
- Pytest

## Project Structure

```text
yottaflex-payment-reconciliation/
├── docs/
├── src/
│   ├── database/
│   ├── generator/
│   ├── reconciliation/
│   ├── exceptions/
│   └── validation/
├── data/
│   ├── generated/
│   └── ground_truth/
├── app/
├── tests/
├── scripts/
├── README.md
└── requirements.txt
```

## Synthetic Data

The project uses deterministic synthetic data.

Random seed: 20261022

Target dataset:

- 2,000 merchants
- 50,000 payment orders
- 55,000 payment attempts
- 1,000 settlement batches
- 5,000 bank statement lines

## Reconciliation Workflow

1. Generate merchants and payment orders.
2. Generate payment attempts and processor events.
3. Calculate captures, refunds, and fees.
4. Generate settlement batches and settlement lines.
5. Generate bank statement records.
6. Match settlement records with bank statements.
7. Create exceptions for unmatched or inconsistent records.
8. Record resolutions and maintain audit history.

## Required Anomaly Scenarios

1. Duplicate settlement line.
2. Bank amount differs by fee.
3. Refund appears before capture.
4. Missing source record.
5. Currency mismatch.
6. Duplicate processor event ingestion.

## Reproducibility

The same generator configuration and random seed should produce identical datasets.

Ground-truth labels are stored separately and are never used as reconciliation engine inputs.

## How to Run

Setup instructions and execution commands will be added as the project modules are implemented.

## Project Status

Under development.
