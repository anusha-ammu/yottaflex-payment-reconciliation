# YottaFlex Payment Reconciliation System
# Database Schema Documentation

## 1. Introduction

The YottaFlex Payment Reconciliation System uses SQLite as its relational database.

The database stores merchant information, payment transactions, processor events, settlement records, bank statement transactions, reconciliation decisions, and exception management records.

The database schema is defined in:

`src/database/schema.sql`

The schema contains 16 relational tables connected through primary keys, foreign keys, unique constraints, check constraints, and indexes.

## 2. Database Design Overview

The database is organized into six functional groups.

| Group | Purpose |
|---|---|
| Master Data | Merchants and application users |
| Payment Processing | Payment orders, attempts, and processor events |
| Settlement Processing | Settlement batches and settlement lines |
| Bank Integration | Bank statement lines and source feed manifests |
| Reconciliation | Reconciliation runs, matches, and allocations |
| Exception Management | Exceptions, relationships, events, and resolutions |

## 3. Complete Table Inventory

The schema contains the following 16 tables.

| No. | Table | Purpose |
|---:|---|---|
| 1 | merchants | Merchant master records |
| 2 | app_users | Application users and roles |
| 3 | source_feed_manifests | Source file control totals |
| 4 | payment_orders | Customer payment instructions |
| 5 | payment_attempts | Individual payment processing attempts |
| 6 | processor_events | Processor webhook events |
| 7 | settlement_batches | Merchant settlement summaries |
| 8 | settlement_lines | Individual settlement transactions |
| 9 | bank_statement_lines | Bank credits and debits |
| 10 | reconciliation_runs | Reconciliation execution records |
| 11 | reconciliation_matches | Reconciliation decisions |
| 12 | reconciliation_allocations | Partial and many-to-many allocations |
| 13 | exceptions | Detected reconciliation exceptions |
| 14 | exception_entity_links | Links exceptions to affected records |
| 15 | exception_events | Exception lifecycle audit history |
| 16 | resolutions | Investigation and resolution records |

## 4. Master Data Tables

### 4.1 merchants

Stores merchant information.

**Primary key:** `merchant_id`

Important columns:

- merchant_id
- merchant_name
- country_code
- default_currency
- status
- effective_from
- effective_to
- created_at

Constraints:

- Merchant name cannot be empty.
- Country code must contain two characters.
- Currency code must contain three characters.
- Status must be ACTIVE, INACTIVE, or SUSPENDED.
- Effective end date cannot precede the effective start date.

Relationships:

- One merchant can have many payment orders.
- One merchant can have many settlement batches.
- One merchant can have many bank statement lines.

### 4.2 app_users

Stores application users and their roles.

**Primary key:** `user_id`

Important columns:

- user_id
- display_name
- role
- is_active
- created_at

Supported roles:

- CUSTOMER
- OPS_ANALYST
- RISK_COMPLIANCE_REVIEWER
- SYSTEM_ADMIN

Application users can be associated with reconciliation runs, exception events, and exception resolutions.

## 5. Payment Processing Tables

### 5.1 payment_orders

Stores customer payment instructions.

**Primary key:** `payment_id`

**Foreign key:** `merchant_id` references `merchants.merchant_id`.

Important columns:

- payment_id
- merchant_id
- merchant_order_reference
- amount_minor
- currency_code
- order_status
- created_at
- updated_at

Supported payment statuses:

- CREATED
- PENDING
- AUTHORIZED
- PAID
- PARTIALLY_REFUNDED
- REFUNDED
- FAILED
- CANCELLED

A payment order belongs to one merchant and can contain multiple payment attempts.

### 5.2 payment_attempts

Stores individual attempts to process a payment.

**Primary key:** `attempt_id`

**Foreign key:** `payment_id` references `payment_orders.payment_id`.

Important columns:

- attempt_id
- payment_id
- attempt_number
- processor_name
- processor_attempt_reference
- amount_minor
- currency_code
- attempt_status
- attempted_at
- created_at
- updated_at

Supported statuses:

- CREATED
- PENDING
- AUTHORIZED
- CAPTURED
- FAILED
- CANCELLED
- REVERSED

Constraints:

- Attempt number must be positive.
- Amount must be positive.
- Attempt number is unique within a payment.
- Processor attempt reference is unique within a processor when provided.

A payment order can have multiple attempts, such as an initial failure followed by a successful retry.

### 5.3 processor_events

Stores processor webhook deliveries and their processing information.

**Primary key:** `processor_event_id`

Foreign keys:

- `attempt_id` references `payment_attempts.attempt_id`.
- `duplicate_of_event_id` references another processor event.
- `feed_manifest_id` references `source_feed_manifests.feed_manifest_id`.

Important columns:

- processor_event_id
- processor_name
- external_event_id
- attempt_id
- event_type
- amount_minor
- currency_code
- occurred_at
- received_at
- duplicate_of_event_id
- processing_status
- feed_manifest_id

Supported event types:

- PAYMENT_AUTHORIZED
- PAYMENT_CAPTURED
- PAYMENT_FAILED
- REFUND_INITIATED
- REFUND_SUCCEEDED
- PAYMENT_REVERSED

Supported processing statuses:

- RECEIVED
- PROCESSED
- DUPLICATE
- REJECTED

The partial unique index `uq_canonical_processor_event` allows only one canonical event per processor and external event ID.

Duplicate deliveries are preserved as separate records and linked to their original event.

## 6. Settlement Tables

### 6.1 settlement_batches

Stores merchant settlement summaries.

**Primary key:** `settlement_batch_id`

**Foreign key:** `merchant_id` references `merchants.merchant_id`.

Important columns:

- settlement_batch_id
- merchant_id
- processor_name
- payout_reference
- currency_code
- period_start
- period_end
- expected_payout_date
- settled_at
- batch_status
- gross_capture_minor
- refund_total_minor
- fee_total_minor
- adjustment_total_minor
- net_amount_minor
- created_at

Supported statuses:

- CREATED
- SUBMITTED
- SETTLED
- FAILED
- CANCELLED

The processor name and payout reference form a unique combination.

The database enforces the settlement calculation:

Net Settlement = Gross Captures - Refunds - Processor Fees + Adjustments.

Settlement amounts are stored in integer minor currency units.

### 6.2 settlement_lines

Stores detailed financial components of settlement batches.

**Primary key:** `settlement_line_id`

Foreign keys:

- `settlement_batch_id` references `settlement_batches.settlement_batch_id`.
- `attempt_id` references `payment_attempts.attempt_id`.
- `processor_event_id` references `processor_events.processor_event_id`.

Supported line types:

- CAPTURE
- REFUND
- FEE
- ADJUSTMENT

Amount constraints:

- CAPTURE amounts must be positive.
- REFUND amounts must be negative.
- FEE amounts must be negative.
- ADJUSTMENT amounts must be non-zero.

Duplicate source transaction references are intentionally permitted so that duplicate settlement lines can be detected.

## 7. Bank Integration Tables

### 7.1 bank_statement_lines

Stores individual bank transaction records.

**Primary key:** `bank_line_id`

Foreign keys:

- `merchant_id` references `merchants.merchant_id`.
- `feed_manifest_id` references `source_feed_manifests.feed_manifest_id`.

Important columns:

- bank_line_id
- merchant_id
- bank_account_reference
- bank_reference
- external_bank_transaction_id
- transaction_type
- signed_amount_minor
- currency_code
- transaction_at
- description
- feed_manifest_id
- created_at

Supported transaction types:

- CREDIT
- DEBIT

Sign constraints:

- CREDIT amounts must be positive.
- DEBIT amounts must be negative.

### 7.2 source_feed_manifests

Stores source file ingestion metadata and control information.

**Primary key:** `feed_manifest_id`

Important columns:

- feed_manifest_id
- source_system
- feed_type
- file_name
- currency_code
- expected_record_count
- ingested_record_count
- expected_total_minor
- ingested_total_minor
- sha256_checksum
- feed_status
- received_at

Supported feed statuses:

- RECEIVED
- PROCESSED
- PARTIAL
- FAILED

The table supports source feed completeness checks using expected and ingested record counts and totals.

It is referenced by processor events and bank statement lines.

## 8. Reconciliation Tables

### 8.1 reconciliation_runs

Stores each execution of the reconciliation engine.

**Primary key:** `run_id`

**Foreign key:** `created_by` references `app_users.user_id`.

Important columns:

- run_id
- rule_version
- run_status
- started_at
- completed_at
- created_by

Supported statuses:

- RUNNING
- COMPLETED
- FAILED

One reconciliation run can produce many reconciliation decisions.

### 8.2 reconciliation_matches

Stores settlement-to-bank matching decisions.

**Primary key:** `reconciliation_id`

Foreign keys:

- `run_id` references `reconciliation_runs.run_id`.
- `settlement_batch_id` references `settlement_batches.settlement_batch_id`.
- `bank_line_id` references `bank_statement_lines.bank_line_id`.
- `created_by` references `app_users.user_id`.

Important columns:

- reconciliation_id
- run_id
- settlement_batch_id
- bank_line_id
- match_status
- match_method
- expected_amount_minor
- actual_amount_minor
- difference_minor
- decision_reason
- rule_version
- evaluated_at
- created_by

Supported statuses:

- MATCHED
- PARTIAL
- UNMATCHED
- REVIEW_REQUIRED
- REJECTED

The table supports unmatched records by allowing either the settlement or bank reference to be absent.

A MATCHED result requires both references.

### 8.3 reconciliation_allocations

Provides a bridge for partial and many-to-many reconciliation.

**Primary key:** `allocation_id`

Foreign keys:

- `reconciliation_id` references `reconciliation_matches.reconciliation_id`.
- `settlement_batch_id` references `settlement_batches.settlement_batch_id`.
- `bank_line_id` references `bank_statement_lines.bank_line_id`.

Important columns:

- allocation_id
- reconciliation_id
- settlement_batch_id
- bank_line_id
- allocated_amount_minor
- currency_code
- created_at

The combination of reconciliation ID, settlement batch ID, and bank line ID must be unique.

Allocated amounts must be positive.

## 9. Exception Management Tables

### 9.1 exceptions

Stores detected reconciliation issues.

**Primary key:** `exception_id`

Important columns:

- exception_id
- exception_type
- severity
- exception_status
- title
- description
- detected_at
- closed_at

Supported exception types:

- DUPLICATE_SETTLEMENT_LINE
- FEE_VARIANCE
- REFUND_BEFORE_CAPTURE
- MISSING_SOURCE_RECORD
- CURRENCY_MISMATCH
- DUPLICATE_PROCESSOR_EVENT
- AMOUNT_MISMATCH
- UNMATCHED_SETTLEMENT
- UNMATCHED_BANK_LINE
- INVALID_LIFECYCLE

Severity levels:

- LOW
- MEDIUM
- HIGH
- CRITICAL

Exception lifecycle statuses:

- OPEN
- IN_REVIEW
- RESOLVED
- CLOSED

### 9.2 exception_entity_links

Links exceptions to their affected business records.

**Primary key:** `exception_link_id`

**Foreign key:** `exception_id` references `exceptions.exception_id`.

Optional foreign-key relationships:

- payment_id
- attempt_id
- processor_event_id
- settlement_batch_id
- settlement_line_id
- bank_line_id
- reconciliation_id

A check constraint requires exactly one affected-record reference per link.

This allows one exception to be associated with multiple affected entities through multiple rows.

### 9.3 exception_events

Stores exception lifecycle audit history.

**Primary key:** `exception_event_id`

Foreign keys:

- `exception_id` references `exceptions.exception_id`.
- `actor_user_id` references `app_users.user_id`.

Important columns:

- exception_event_id
- exception_id
- previous_status
- new_status
- action_type
- actor_user_id
- notes
- created_at

Records actions such as:

- DETECTED
- ASSIGNED
- NOTE_ADDED
- RESOLVED
- CLOSED

The table maintains the historical status transition and associated user activity.

### 9.4 resolutions

Stores resolution and investigation records.

**Primary key:** `resolution_id`

Foreign keys:

- `exception_id` references `exceptions.exception_id`.
- `resolved_by` references `app_users.user_id`.

Important columns:

- resolution_id
- exception_id
- action
- outcome
- notes
- resolved_by
- created_at

One exception can have multiple recorded resolution actions.

## 10. Entity Relationships

The following diagram describes the main relationships.

```text
MERCHANTS
   |
   | 1:N
   v
PAYMENT_ORDERS
   |
   | 1:N
   v
PAYMENT_ATTEMPTS
   |
   | 1:N
   v
PROCESSOR_EVENTS
   |
   | Used to derive
   v
SETTLEMENT_LINES
   |
   | N:1
   v
SETTLEMENT_BATCHES
   |
   | Merchant payout reference
   v
BANK_STATEMENT_LINES
   |
   v
RECONCILIATION_MATCHES
   |
   | 1:N
   v
RECONCILIATION_ALLOCATIONS


SOURCE_FEED_MANIFESTS
   |
   +---- PROCESSOR_EVENTS
   |
   +---- BANK_STATEMENT_LINES


EXCEPTIONS
   |
   +---- EXCEPTION_ENTITY_LINKS
   |
   +---- EXCEPTION_EVENTS
   |
   +---- RESOLUTIONS


APP_USERS
   |
   +---- RECONCILIATION_RUNS
   |
   +---- RECONCILIATION_MATCHES
   |
   +---- EXCEPTION_EVENTS
   |
   +---- RESOLUTIONS
```

## 11. Database Indexing

The schema defines indexes to improve frequent lookups and joins.

| Index | Indexed columns |
|---|---|
| uq_canonical_processor_event | processor_name, external_event_id (partial unique index) |
| idx_payment_orders_merchant | merchant_id |
| idx_payment_orders_status | order_status |
| idx_attempts_payment | payment_id |
| idx_events_attempt_time | attempt_id, occurred_at |
| idx_events_received | received_at |
| idx_batches_merchant_date | merchant_id, expected_payout_date |
| idx_settlement_lines_batch | settlement_batch_id |
| idx_settlement_source_reference | source_transaction_reference |
| idx_bank_merchant_date | merchant_id, transaction_at |
| idx_bank_reference | bank_reference |
| idx_matches_status | match_status |
| idx_exceptions_status | exception_status |
| idx_exceptions_type | exception_type |
| idx_exception_events_exception | exception_id, created_at |
| idx_resolutions_exception | exception_id, created_at |

## 12. Referential Integrity

The database enables SQLite foreign-key enforcement using:

`PRAGMA foreign_keys = ON;`

The schema uses foreign keys to maintain relationships between:

- Merchants and payments.
- Payments and attempts.
- Attempts and processor events.
- Merchants and settlement batches.
- Settlement batches and settlement lines.
- Merchants and bank statement lines.
- Reconciliation runs and reconciliation decisions.
- Exceptions and affected business records.
- Exceptions and their event and resolution histories.

The application validates relationships using:

`PRAGMA foreign_key_check;`

Full database integrity can be checked using:

`PRAGMA integrity_check;`

## 13. Financial Data Representation

The database stores financial values as integers in the smallest currency unit.

Examples:

| Currency | Major amount | Stored amount |
|---|---:|---:|
| INR | 100.50 | 10,050 paise |
| USD | 100.50 | 10,050 cents |
| EUR | 100.50 | 10,050 cents |
| GBP | 100.50 | 10,050 pence |

This avoids floating-point precision errors in financial calculations.

## 14. Full-Scale Database Validation

The full-scale dataset has been verified with the following record counts:

| Table | Records |
|---|---:|
| merchants | 2,000 |
| payment_orders | 50,000 |
| payment_attempts | 55,000 |
| settlement_batches | 1,000 |
| bank_statement_lines | 5,000 |

The clean full-scale database passed:

- Foreign-key validation.
- Settlement arithmetic validation.
- Bank payout amount validation.
- Currency validation.
- SQLite integrity validation.

The separate full-scale anomaly database also passed its six-scenario evaluation.

## 15. Summary

The YottaFlex database schema provides a relational foundation for end-to-end payment reconciliation.

It supports merchant and payment management, processor event tracking, settlement processing, bank statement ingestion, reconciliation decisions, exception tracking, and audit history.

The schema uses relational constraints and indexes to maintain data integrity and support efficient record retrieval.

---

**Project:** YottaFlex Payment Reconciliation System  
**Database:** SQLite  
**Schema File:** `src/database/schema.sql`