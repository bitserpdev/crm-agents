CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. lz_platform_integrations
CREATE TABLE lz_platform_integrations (
    integration_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_name         VARCHAR(50)   NOT NULL UNIQUE,
    api_key_encrypted     TEXT,
    webhook_url           TEXT,
    polling_interval_sec  INTEGER       DEFAULT 300,
    last_synced_at        TIMESTAMPTZ,
    is_active             BOOLEAN       DEFAULT TRUE,
    auth_type             VARCHAR(20)   DEFAULT 'oauth2',
    oauth_access_token    TEXT,
    oauth_refresh_token   TEXT,
    oauth_expires_at      TIMESTAMPTZ,
    oauth_scopes          TEXT[],
    created_at            TIMESTAMPTZ   DEFAULT now(),
    updated_at            TIMESTAMPTZ   DEFAULT now()
);

-- 2. lz_campaigns
CREATE TABLE lz_campaigns (
    campaign_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_name    VARCHAR(100)  NOT NULL,
    cron_expression  VARCHAR(50)   NOT NULL,
    source_configs   JSONB         NOT NULL,
    is_active        BOOLEAN       DEFAULT TRUE,
    last_run_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   DEFAULT now(),
    updated_at       TIMESTAMPTZ   DEFAULT now()
);

-- 3. lz_raw_events
CREATE TABLE lz_raw_events (
    event_id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    received_at        TIMESTAMPTZ   NOT NULL,
    source_platform    VARCHAR(50)   NOT NULL,
    raw_payload        JSONB         NOT NULL,
    dedup_key          VARCHAR(64)   NOT NULL,
    processing_status  VARCHAR(20)   NOT NULL DEFAULT 'new',
    duplicate_of       UUID          REFERENCES lz_raw_events (event_id),
    agent_trace_id     UUID,
    campaign_id        UUID          REFERENCES lz_campaigns (campaign_id),
    created_at         TIMESTAMPTZ   DEFAULT now()
);

-- 4. lz_lead_sources
CREATE TABLE lz_lead_sources (
    source_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID          NOT NULL REFERENCES lz_raw_events (event_id),
    integration_id  UUID          REFERENCES lz_platform_integrations (integration_id),
    source_type     VARCHAR(50)   NOT NULL,
    source_url      TEXT,
    dedup_key       VARCHAR(64)   NOT NULL,
    first_seen_at   TIMESTAMPTZ   NOT NULL,
    merge_count     INTEGER       DEFAULT 0,
    extra_meta      JSONB,
    created_at      TIMESTAMPTZ   DEFAULT now()
);

-- 5. lz_extraction_logs
CREATE TABLE lz_extraction_logs (
    log_id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id           UUID          NOT NULL REFERENCES lz_raw_events (event_id),
    agent_id           VARCHAR(50)   NOT NULL,
    extraction_status  VARCHAR(20)   NOT NULL,
    extracted_fields   JSONB,
    error_message      TEXT,
    duration_ms        INTEGER,
    ran_at             TIMESTAMPTZ   DEFAULT now()
);

-- 6. lz_dedup_registry
CREATE TABLE lz_dedup_registry (
    dedup_id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    dedup_key         VARCHAR(64)   NOT NULL UNIQUE,
    first_event_id    UUID          NOT NULL REFERENCES lz_raw_events (event_id),
    latest_event_id   UUID          NOT NULL REFERENCES lz_raw_events (event_id),
    occurrence_count  INTEGER       DEFAULT 1,
    sources_seen      TEXT[],
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now()
);

-- 7. lz_raw_attachments
CREATE TABLE lz_raw_attachments (
    attachment_id    UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id         UUID           NOT NULL REFERENCES lz_raw_events (event_id),
    file_name        VARCHAR(255)   NOT NULL,
    file_size_bytes  INTEGER,
    mime_type        VARCHAR(100),
    storage_path     TEXT           NOT NULL,
    created_at       TIMESTAMPTZ    DEFAULT now()
);

-- 8. Seed LinkedIn platform
INSERT INTO lz_platform_integrations (
    platform_name, auth_type, polling_interval_sec, is_active
) VALUES (
    'linkedin', 'oauth2', 300, TRUE
);
