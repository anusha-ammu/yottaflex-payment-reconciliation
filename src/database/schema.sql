
-- =========================================================
-- YOTTAFLEX PAYMENT RECONCILIATION SYSTEM
-- SQLite database schema
-- =========================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------
-- 1. MERCHANTS
-- One merchant can have many payment orders and batches.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY,
    merchant_name TEXT NOT NULL
        CHECK(length(trim(merchant_name)) > 0),
    country_code TEXT NOT NULL
        CHECK(length(country_code) = 2),
    default_currency TEXT NOT NULL
        CHECK(length(default_currency) = 3),
    status TEXT NOT NULL
        CHECK(status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    created_at TEXT NOT NULL,
    CHECK(effective_to IS NULL OR effective_to >= effective_from)
);

-- ---------------------------------------------------------
-- 2. APPLICATION USERS
-- Supporting table for operations, risk and administrators.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS app_users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN (
        'CUSTOMER',
        'OPS_ANALYST',
        'RISK_COMPLIANCE_REVIEWER',
        'SYSTEM_ADMIN'
    )),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

-- ---------------------------------------------------------
-- 3. SOURCE FEED MANIFESTS
-- Independent control counts and totals help detect
-- missing records in imported files.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS source_feed_manifests (
    feed_manifest_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    feed_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    currency_code TEXT
        CHECK(currency_code IS NULL OR length(currency_code) = 3),
    expected_record_count INTEGER NOT NULL
        CHECK(expected_record_count >= 0),
    ingested_record_count INTEGER NOT NULL
        CHECK(ingested_record_count >= 0),
    expected_total_minor INTEGER,
    ingested_total_minor INTEGER,
    sha256_checksum TEXT,
    feed_status TEXT NOT NULL CHECK(feed_status IN (
        'RECEIVED', 'PROCESSED', 'PARTIAL', 'FAILED'
    )),
    received_at TEXT NOT NULL
);

-- ---------------------------------------------------------
-- 4. PAYMENT ORDERS
-- One merchant can create many payment orders.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS payment_orders (
    payment_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    merchant_order_reference TEXT,
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    order_status TEXT NOT NULL CHECK(order_status IN (
        'CREATED',
        'PENDING',
        'AUTHORIZED',
        'PAID',
        'PARTIALLY_REFUNDED',
        'REFUNDED',
        'FAILED',
        'CANCELLED'
    )),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (merchant_id)
        REFERENCES merchants(merchant_id),

    UNIQUE (merchant_id, merchant_order_reference)
);

-- ---------------------------------------------------------
-- 5. PAYMENT ATTEMPTS
-- One payment order can have multiple attempts.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS payment_attempts (
    attempt_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK(attempt_number > 0),
    processor_name TEXT NOT NULL,
    processor_attempt_reference TEXT,
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    attempt_status TEXT NOT NULL CHECK(attempt_status IN (
        'CREATED',
        'PENDING',
        'AUTHORIZED',
        'CAPTURED',
        'FAILED',
        'CANCELLED',
        'REVERSED'
    )),
    attempted_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (payment_id)
        REFERENCES payment_orders(payment_id),

    UNIQUE (payment_id, attempt_number),
    UNIQUE (processor_name, processor_attempt_reference)
);

-- ---------------------------------------------------------
-- 6. PROCESSOR EVENTS
-- Stores received webhook deliveries, including duplicates.
-- Duplicate deliveries reference the original event.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS processor_events (
    processor_event_id TEXT PRIMARY KEY,
    processor_name TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN (
        'PAYMENT_AUTHORIZED',
        'PAYMENT_CAPTURED',
        'PAYMENT_FAILED',
        'REFUND_INITIATED',
        'REFUND_SUCCEEDED',
        'PAYMENT_REVERSED'
    )),
    amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0),
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    duplicate_of_event_id TEXT,
    processing_status TEXT NOT NULL CHECK(processing_status IN (
        'RECEIVED',
        'PROCESSED',
        'DUPLICATE',
        'REJECTED'
    )),
    feed_manifest_id TEXT,

    FOREIGN KEY (attempt_id)
        REFERENCES payment_attempts(attempt_id),

    FOREIGN KEY (duplicate_of_event_id)
        REFERENCES processor_events(processor_event_id),

    FOREIGN KEY (feed_manifest_id)
        REFERENCES source_feed_manifests(feed_manifest_id),

    CHECK (
        duplicate_of_event_id IS NULL
        OR (
            duplicate_of_event_id <> processor_event_id
            AND processing_status = 'DUPLICATE'
        )
    )
);

-- Only one canonical event per processor external event ID.
-- Duplicate deliveries are preserved as separate rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_processor_event
ON processor_events(processor_name, external_event_id)
WHERE duplicate_of_event_id IS NULL;

-- ---------------------------------------------------------
-- 7. SETTLEMENT BATCHES
-- Each batch belongs to one merchant.
-- Amounts are derived from settlement lines.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS settlement_batches (
    settlement_batch_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    processor_name TEXT NOT NULL,
    payout_reference TEXT NOT NULL,
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    expected_payout_date TEXT NOT NULL,
    settled_at TEXT,
    batch_status TEXT NOT NULL CHECK(batch_status IN (
        'CREATED', 'SUBMITTED', 'SETTLED', 'FAILED', 'CANCELLED'
    )),
    gross_capture_minor INTEGER NOT NULL DEFAULT 0
        CHECK(gross_capture_minor >= 0),
    refund_total_minor INTEGER NOT NULL DEFAULT 0
        CHECK(refund_total_minor >= 0),
    fee_total_minor INTEGER NOT NULL DEFAULT 0
        CHECK(fee_total_minor >= 0),
    adjustment_total_minor INTEGER NOT NULL DEFAULT 0,
    net_amount_minor INTEGER NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (merchant_id)
        REFERENCES merchants(merchant_id),

    UNIQUE (processor_name, payout_reference),

    CHECK(period_end >= period_start),

    CHECK(
        net_amount_minor =
        gross_capture_minor
        - refund_total_minor
        - fee_total_minor
        + adjustment_total_minor
    )
);

-- ---------------------------------------------------------
-- 8. SETTLEMENT LINES
-- One batch can contain many financial lines.
-- Captures are positive; refunds and fees are negative.
-- No uniqueness constraint on source reference because
-- duplicate settlement lines must be detectable.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS settlement_lines (
    settlement_line_id TEXT PRIMARY KEY,
    settlement_batch_id TEXT NOT NULL,
    attempt_id TEXT,
    processor_event_id TEXT,
    line_type TEXT NOT NULL CHECK(line_type IN (
        'CAPTURE', 'REFUND', 'FEE', 'ADJUSTMENT'
    )),
    amount_minor INTEGER NOT NULL,
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    source_transaction_reference TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (settlement_batch_id)
        REFERENCES settlement_batches(settlement_batch_id),

    FOREIGN KEY (attempt_id)
        REFERENCES payment_attempts(attempt_id),

    FOREIGN KEY (processor_event_id)
        REFERENCES processor_events(processor_event_id),

    CHECK(
        (line_type = 'CAPTURE' AND amount_minor > 0)
        OR
        (line_type IN ('REFUND', 'FEE') AND amount_minor < 0)
        OR
        (line_type = 'ADJUSTMENT' AND amount_minor <> 0)
    ),

    CHECK(
        attempt_id IS NOT NULL
        OR processor_event_id IS NOT NULL
        OR line_type IN ('FEE', 'ADJUSTMENT')
    )
);

-- ---------------------------------------------------------
-- 9. BANK STATEMENT LINES
-- Represents actual bank credits and debits.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS bank_statement_lines (
    bank_line_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL,
    bank_account_reference TEXT NOT NULL,
    bank_reference TEXT,
    external_bank_transaction_id TEXT,
    transaction_type TEXT NOT NULL
        CHECK(transaction_type IN ('CREDIT', 'DEBIT')),
    signed_amount_minor INTEGER NOT NULL
        CHECK(signed_amount_minor <> 0),
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    transaction_at TEXT NOT NULL,
    description TEXT,
    feed_manifest_id TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (merchant_id)
        REFERENCES merchants(merchant_id),

    FOREIGN KEY (feed_manifest_id)
        REFERENCES source_feed_manifests(feed_manifest_id),

    CHECK(
        (transaction_type = 'CREDIT' AND signed_amount_minor > 0)
        OR
        (transaction_type = 'DEBIT' AND signed_amount_minor < 0)
    )
);

-- ---------------------------------------------------------
-- 10. RECONCILIATION RUNS
-- Records each execution of the matching engine.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id TEXT PRIMARY KEY,
    rule_version TEXT NOT NULL,
    run_status TEXT NOT NULL CHECK(run_status IN (
        'RUNNING', 'COMPLETED', 'FAILED'
    )),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_by TEXT,

    FOREIGN KEY (created_by)
        REFERENCES app_users(user_id)
);

-- ---------------------------------------------------------
-- 11. RECONCILIATION MATCHES
-- Records matching decisions and their reasons.
-- The batch and bank references are optional to support
-- unmatched records.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS reconciliation_matches (
    reconciliation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    settlement_batch_id TEXT,
    bank_line_id TEXT,
    match_status TEXT NOT NULL CHECK(match_status IN (
        'MATCHED',
        'PARTIAL',
        'UNMATCHED',
        'REVIEW_REQUIRED',
        'REJECTED'
    )),
    match_method TEXT,
    expected_amount_minor INTEGER,
    actual_amount_minor INTEGER,
    difference_minor INTEGER,
    decision_reason TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    created_by TEXT,

    FOREIGN KEY (run_id)
        REFERENCES reconciliation_runs(run_id),

    FOREIGN KEY (settlement_batch_id)
        REFERENCES settlement_batches(settlement_batch_id),

    FOREIGN KEY (bank_line_id)
        REFERENCES bank_statement_lines(bank_line_id),

    FOREIGN KEY (created_by)
        REFERENCES app_users(user_id),

    CHECK(
        settlement_batch_id IS NOT NULL
        OR bank_line_id IS NOT NULL
    ),

    CHECK(
        match_status <> 'MATCHED'
        OR (
            settlement_batch_id IS NOT NULL
            AND bank_line_id IS NOT NULL
        )
    )
);

-- ---------------------------------------------------------
-- 12. RECONCILIATION ALLOCATIONS
-- Bridge table for partial and many-to-many matching.
-- One reconciliation decision can involve multiple pairs.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS reconciliation_allocations (
    allocation_id TEXT PRIMARY KEY,
    reconciliation_id TEXT NOT NULL,
    settlement_batch_id TEXT NOT NULL,
    bank_line_id TEXT NOT NULL,
    allocated_amount_minor INTEGER NOT NULL
        CHECK(allocated_amount_minor > 0),
    currency_code TEXT NOT NULL CHECK(length(currency_code) = 3),
    created_at TEXT NOT NULL,

    FOREIGN KEY (reconciliation_id)
        REFERENCES reconciliation_matches(reconciliation_id),

    FOREIGN KEY (settlement_batch_id)
        REFERENCES settlement_batches(settlement_batch_id),

    FOREIGN KEY (bank_line_id)
        REFERENCES bank_statement_lines(bank_line_id),

    UNIQUE (
        reconciliation_id,
        settlement_batch_id,
        bank_line_id
    )
);

-- ---------------------------------------------------------
-- 13. EXCEPTIONS
-- One exception can be associated with multiple records
-- through the exception_entity_links bridge table.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id TEXT PRIMARY KEY,
    exception_type TEXT NOT NULL CHECK(exception_type IN (
        'DUPLICATE_SETTLEMENT_LINE',
        'FEE_VARIANCE',
        'REFUND_BEFORE_CAPTURE',
        'MISSING_SOURCE_RECORD',
        'CURRENCY_MISMATCH',
        'DUPLICATE_PROCESSOR_EVENT',
        'AMOUNT_MISMATCH',
        'UNMATCHED_SETTLEMENT',
        'UNMATCHED_BANK_LINE',
        'INVALID_LIFECYCLE'
    )),
    severity TEXT NOT NULL CHECK(severity IN (
        'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    )),
    exception_status TEXT NOT NULL CHECK(exception_status IN (
        'OPEN', 'IN_REVIEW', 'RESOLVED', 'CLOSED'
    )),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    closed_at TEXT
);

-- ---------------------------------------------------------
-- 14. EXCEPTION ENTITY LINKS
-- Each row links an exception to exactly one affected record.
-- Every possible target has a real foreign key.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS exception_entity_links (
    exception_link_id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL,
    payment_id TEXT,
    attempt_id TEXT,
    processor_event_id TEXT,
    settlement_batch_id TEXT,
    settlement_line_id TEXT,
    bank_line_id TEXT,
    reconciliation_id TEXT,

    FOREIGN KEY (exception_id)
        REFERENCES exceptions(exception_id),

    FOREIGN KEY (payment_id)
        REFERENCES payment_orders(payment_id),

    FOREIGN KEY (attempt_id)
        REFERENCES payment_attempts(attempt_id),

    FOREIGN KEY (processor_event_id)
        REFERENCES processor_events(processor_event_id),

    FOREIGN KEY (settlement_batch_id)
        REFERENCES settlement_batches(settlement_batch_id),

    FOREIGN KEY (settlement_line_id)
        REFERENCES settlement_lines(settlement_line_id),

    FOREIGN KEY (bank_line_id)
        REFERENCES bank_statement_lines(bank_line_id),

    FOREIGN KEY (reconciliation_id)
        REFERENCES reconciliation_matches(reconciliation_id),

    CHECK(
        (payment_id IS NOT NULL)
        + (attempt_id IS NOT NULL)
        + (processor_event_id IS NOT NULL)
        + (settlement_batch_id IS NOT NULL)
        + (settlement_line_id IS NOT NULL)
        + (bank_line_id IS NOT NULL)
        + (reconciliation_id IS NOT NULL) = 1
    )
);

-- ---------------------------------------------------------
-- 15. EXCEPTION EVENTS
-- Append-only history of exception status changes.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS exception_events (
    exception_event_id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL CHECK(new_status IN (
        'OPEN', 'IN_REVIEW', 'RESOLVED', 'CLOSED'
    )),
    action_type TEXT NOT NULL,
    actor_user_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (exception_id)
        REFERENCES exceptions(exception_id),

    FOREIGN KEY (actor_user_id)
        REFERENCES app_users(user_id)
);

-- ---------------------------------------------------------
-- 16. RESOLUTIONS
-- One exception can have multiple recorded actions.
-- ---------------------------------------------------------

CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    notes TEXT NOT NULL,
    resolved_by TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (exception_id)
        REFERENCES exceptions(exception_id),

    FOREIGN KEY (resolved_by)
        REFERENCES app_users(user_id)
);

-- ---------------------------------------------------------
-- INDEXES
-- Improve common search and join operations.
-- ---------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_payment_orders_merchant
ON payment_orders(merchant_id);

CREATE INDEX IF NOT EXISTS idx_payment_orders_status
ON payment_orders(order_status);

CREATE INDEX IF NOT EXISTS idx_attempts_payment
ON payment_attempts(payment_id);

CREATE INDEX IF NOT EXISTS idx_events_attempt_time
ON processor_events(attempt_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_events_received
ON processor_events(received_at);

CREATE INDEX IF NOT EXISTS idx_batches_merchant_date
ON settlement_batches(merchant_id, expected_payout_date);

CREATE INDEX IF NOT EXISTS idx_settlement_lines_batch
ON settlement_lines(settlement_batch_id);

CREATE INDEX IF NOT EXISTS idx_settlement_source_reference
ON settlement_lines(source_transaction_reference);

CREATE INDEX IF NOT EXISTS idx_bank_merchant_date
ON bank_statement_lines(merchant_id, transaction_at);

CREATE INDEX IF NOT EXISTS idx_bank_reference
ON bank_statement_lines(bank_reference);

CREATE INDEX IF NOT EXISTS idx_matches_status
ON reconciliation_matches(match_status);

CREATE INDEX IF NOT EXISTS idx_exceptions_status
ON exceptions(exception_status);

CREATE INDEX IF NOT EXISTS idx_exceptions_type
ON exceptions(exception_type);

CREATE INDEX IF NOT EXISTS idx_exception_events_exception
ON exception_events(exception_id, created_at);

CREATE INDEX IF NOT EXISTS idx_resolutions_exception
ON resolutions(exception_id, created_at);
