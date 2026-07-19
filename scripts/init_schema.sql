-- Database initialization SQL (extracted from alembic/versions/0001_initial_schema.py)
-- Run this against the xwawa_db database

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(32),
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(64),
    kyc_level VARCHAR(32) NOT NULL DEFAULT 'none',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_locked BOOLEAN NOT NULL DEFAULT false,
    locked_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT uq_users_phone UNIQUE (phone)
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_phone ON users (phone);

CREATE TABLE IF NOT EXISTS wallets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    balance NUMERIC(12, 4) NOT NULL DEFAULT 0,
    credit_limit NUMERIC(12, 4) NOT NULL DEFAULT 0,
    used_this_month NUMERIC(12, 4) NOT NULL DEFAULT 0,
    daily_limit NUMERIC(12, 4) NOT NULL DEFAULT 10,
    per_call_limit NUMERIC(12, 4) NOT NULL DEFAULT 0.50,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_wallets_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT uq_wallets_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    wallet_id BIGINT NOT NULL,
    type VARCHAR(32) NOT NULL,
    amount NUMERIC(12, 4) NOT NULL,
    balance_after NUMERIC(12, 4) NOT NULL,
    reference VARCHAR(128),
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_transactions_wallet FOREIGN KEY (wallet_id) REFERENCES wallets(id)
);

CREATE INDEX IF NOT EXISTS ix_transactions_wallet_id ON transactions (wallet_id);
CREATE INDEX IF NOT EXISTS ix_transactions_created_at ON transactions (created_at);
CREATE INDEX IF NOT EXISTS ix_transactions_type ON transactions (type);

CREATE TABLE IF NOT EXISTS api_keys (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(16) NOT NULL,
    name VARCHAR(64) NOT NULL,
    scope_chat BOOLEAN NOT NULL DEFAULT true,
    scope_images BOOLEAN NOT NULL DEFAULT true,
    scope_music BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_api_keys_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT uq_api_keys_hash UNIQUE (key_hash)
);

CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id);
CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON api_keys (key_prefix);

CREATE TABLE IF NOT EXISTS agents (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    did VARCHAR(128) NOT NULL,
    name VARCHAR(64) NOT NULL,
    agent_type VARCHAR(32) NOT NULL,
    per_call_limit NUMERIC(12, 4) NOT NULL DEFAULT 0.50,
    daily_limit NUMERIC(12, 4) NOT NULL DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_agents_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT uq_agents_did UNIQUE (did)
);

CREATE INDEX IF NOT EXISTS ix_agents_user_id ON agents (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_agents_did ON agents (did);

CREATE TABLE IF NOT EXISTS usage_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    agent_id BIGINT,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(64) NOT NULL,
    endpoint VARCHAR(128) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_provider NUMERIC(12, 6) NOT NULL,
    cost_user NUMERIC(12, 6) NOT NULL,
    is_anomalous BOOLEAN NOT NULL DEFAULT false,
    anomaly_reason VARCHAR(256),
    request_id VARCHAR(64) NOT NULL,
    client_ip VARCHAR(45),
    duration_ms BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_usage_logs_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_usage_logs_agent FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE INDEX IF NOT EXISTS ix_usage_logs_user_id ON usage_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_usage_logs_agent_id ON usage_logs (agent_id);
CREATE INDEX IF NOT EXISTS ix_usage_logs_provider ON usage_logs (provider);
CREATE INDEX IF NOT EXISTS ix_usage_logs_created_at ON usage_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_usage_logs_anomalous ON usage_logs (is_anomalous);
CREATE INDEX IF NOT EXISTS ix_usage_logs_request_id ON usage_logs (request_id);
