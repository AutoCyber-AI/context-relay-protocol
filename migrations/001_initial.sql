-- CRP Auth Migration — Initial Schema
-- Apply to BOTH crp_gateway and crp_comply logical databases
-- Run: psql $DATABASE_URL -f 001_initial.sql

-- ============================================================
-- Shared: tenants (links Clerk identity to app state)
-- ============================================================
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id         TEXT PRIMARY KEY,
    clerk_org_id      TEXT UNIQUE,
    clerk_user_id     TEXT NOT NULL,
    account_type      TEXT NOT NULL
                      CHECK (account_type IN ('org', 'personal'))
                      DEFAULT 'org',
    name              TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenants_org ON tenants(clerk_org_id)
    WHERE clerk_org_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tenants_user ON tenants(clerk_user_id);

-- ============================================================
-- Shared: api_keys (hashed, per-tenant)
-- ============================================================
CREATE TABLE IF NOT EXISTS api_keys (
    key_id            TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    key_hash          TEXT NOT NULL,
    key_prefix        TEXT,
    name              TEXT DEFAULT 'default',
    scopes            TEXT[] DEFAULT '{}',
    revoked           BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    last_used_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)
    WHERE revoked = FALSE;

-- ============================================================
-- Comply: github_installations
-- ============================================================
CREATE TABLE IF NOT EXISTS github_installations (
    installation_id   BIGINT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    account_login     TEXT NOT NULL,
    account_type      TEXT NOT NULL DEFAULT 'Organization'
                      CHECK (account_type IN ('User', 'Organization')),
    suspended         BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_github_install_tenant ON github_installations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_github_install_login ON github_installations(account_login);

-- ============================================================
-- Comply: github_repos
-- ============================================================
CREATE TABLE IF NOT EXISTS github_repos (
    repo_internal_id  BIGSERIAL PRIMARY KEY,
    installation_id   BIGINT NOT NULL REFERENCES github_installations(installation_id)
                      ON DELETE CASCADE,
    repo_id           BIGINT NOT NULL,
    full_name         TEXT NOT NULL,
    private           BOOLEAN NOT NULL DEFAULT TRUE,
    connected         BOOLEAN DEFAULT FALSE,
    last_scanned_at   TIMESTAMPTZ,
    findings_count    INT DEFAULT 0,
    UNIQUE(installation_id, repo_id)
);

CREATE INDEX IF NOT EXISTS idx_github_repos_install ON github_repos(installation_id);
CREATE INDEX IF NOT EXISTS idx_github_repos_connected ON github_repos(connected)
    WHERE connected = TRUE;

-- ============================================================
-- Comply: scan_results
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_results (
    scan_id           BIGSERIAL PRIMARY KEY,
    repo_id           BIGINT NOT NULL REFERENCES github_repos(repo_internal_id)
                      ON DELETE CASCADE,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    commit_sha        TEXT,
    findings          JSONB DEFAULT '[]',
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scan_results_repo ON scan_results(repo_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_results_tenant ON scan_results(tenant_id, status);

-- ============================================================
-- Comply: compliance_reports
-- ============================================================
CREATE TABLE IF NOT EXISTS compliance_reports (
    report_id         TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    kind              TEXT NOT NULL
                      CHECK (kind IN ('risk', 'dpia', 'transparency', 'technical')),
    system_name       TEXT,
    markdown          TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_reports_tenant ON compliance_reports(tenant_id, kind);

-- ============================================================
-- Comply: evidence_packs
-- ============================================================
CREATE TABLE IF NOT EXISTS evidence_packs (
    pack_id           TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending', 'building', 'ready', 'failed')),
    download_url      TEXT,
    hmac_signature    TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_packs_tenant ON evidence_packs(tenant_id, status);

-- ============================================================
-- Gateway: gateway_systems
-- ============================================================
CREATE TABLE IF NOT EXISTS gateway_systems (
    system_id         TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    name              TEXT NOT NULL,
    domain            TEXT,
    intended_purpose  TEXT,
    eu_ai_act_class   TEXT
                      CHECK (eu_ai_act_class IN ('MINIMAL', 'LIMITED', 'HIGH', 'UNACCEPTABLE')),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gateway_systems_tenant ON gateway_systems(tenant_id);

-- ============================================================
-- Gateway: gateway_providers
-- ============================================================
CREATE TABLE IF NOT EXISTS gateway_providers (
    provider_id       TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    provider_type     TEXT NOT NULL
                      CHECK (provider_type IN ('openai', 'anthropic', 'ollama', 'custom')),
    api_key_encrypted TEXT NOT NULL,
    default_model     TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gateway_providers_tenant ON gateway_providers(tenant_id);

-- ============================================================
-- Gateway: gateway_documents
-- ============================================================
CREATE TABLE IF NOT EXISTS gateway_documents (
    document_id       TEXT PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    title             TEXT,
    source_uri        TEXT,
    content_hash      TEXT,
    status            TEXT DEFAULT 'pending'
                      CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    estimated_facts   INT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gateway_docs_tenant ON gateway_documents(tenant_id, status);

-- ============================================================
-- Gateway: gateway_usage (per-call detail)
-- ============================================================
CREATE TABLE IF NOT EXISTS gateway_usage (
    usage_id          BIGSERIAL PRIMARY KEY,
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    call_type         TEXT
                      CHECK (call_type IN ('chat', 'completion', 'embedding')),
    model             TEXT,
    tokens_in         INT DEFAULT 0,
    tokens_out        INT DEFAULT 0,
    risk_class        TEXT,
    halted            BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gateway_usage_tenant_time ON gateway_usage(tenant_id, created_at DESC);

-- ============================================================
-- Gateway: usage_stats (aggregated per-hour, for quota checks)
-- ============================================================
CREATE TABLE IF NOT EXISTS usage_stats (
    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id)
                      ON DELETE CASCADE,
    calls             INT DEFAULT 0,
    tokens            INT DEFAULT 0,
    period            TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, period)
);

-- ============================================================
-- Shared: webhook event idempotency (Stripe + GitHub)
-- ============================================================
CREATE TABLE IF NOT EXISTS webhook_events (
    event_id          TEXT PRIMARY KEY,
    source            TEXT NOT NULL CHECK (source IN ('stripe', 'github')),
    event_type        TEXT NOT NULL,
    processed_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_source ON webhook_events(source, processed_at DESC);
