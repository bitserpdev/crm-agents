SET search_path TO crm, public;

-- Add email-specific columns to crm_campaigns
ALTER TABLE crm.crm_campaigns
    ADD COLUMN IF NOT EXISTS service_description TEXT,
    ADD COLUMN IF NOT EXISTS filter_region       VARCHAR(100),
    ADD COLUMN IF NOT EXISTS filter_industry     VARCHAR(100),
    ADD COLUMN IF NOT EXISTS filter_company_size VARCHAR(30),
    ADD COLUMN IF NOT EXISTS filter_min_score    SMALLINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS filter_max_score    SMALLINT DEFAULT 100,
    ADD COLUMN IF NOT EXISTS filter_stage        VARCHAR(30),
    ADD COLUMN IF NOT EXISTS scheduled_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS from_address        VARCHAR(254),
    ADD COLUMN IF NOT EXISTS azure_token         TEXT,
    ADD COLUMN IF NOT EXISTS azure_refresh_token TEXT,
    ADD COLUMN IF NOT EXISTS azure_token_expiry  TIMESTAMPTZ;

-- Email threads table
CREATE TABLE IF NOT EXISTS crm.crm_email_threads (
    thread_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID          REFERENCES crm.crm_leads(lead_id),
    contact_id      UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    rep_user_id     UUID          REFERENCES crm.crm_users(user_id),
    imap_thread_id  VARCHAR(200)  NOT NULL,
    subject         VARCHAR(500),
    thread_status   VARCHAR(30)   NOT NULL DEFAULT 'active',
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   DEFAULT now()
);

-- Email messages table
CREATE TABLE IF NOT EXISTS crm.crm_email_messages (
    message_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       UUID          NOT NULL REFERENCES crm.crm_email_threads(thread_id),
    direction       VARCHAR(10)   NOT NULL,
    from_address    VARCHAR(254)  NOT NULL,
    to_addresses    TEXT[]        NOT NULL,
    subject         VARCHAR(500),
    body_text       TEXT,
    body_html       TEXT,
    sent_at         TIMESTAMPTZ,
    received_at     TIMESTAMPTZ,
    sent_by_agent   VARCHAR(50),
    imap_message_id VARCHAR(200)
);

-- Campaign runs
CREATE TABLE IF NOT EXISTS crm.crm_campaign_runs (
    run_id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id       UUID          NOT NULL REFERENCES crm.crm_campaigns(campaign_id),
    run_status        VARCHAR(30)   NOT NULL DEFAULT 'pending',
    total_recipients  INTEGER       DEFAULT 0,
    sent_count        INTEGER       DEFAULT 0,
    failed_count      INTEGER       DEFAULT 0,
    open_count        INTEGER       DEFAULT 0,
    click_count       INTEGER       DEFAULT 0,
    unsubscribe_cnt   INTEGER       DEFAULT 0,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    redis_job_key     VARCHAR(200),
    created_at        TIMESTAMPTZ   DEFAULT now()
);

-- Campaign recipients
CREATE TABLE IF NOT EXISTS crm.crm_campaign_recipients (
    recipient_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID          NOT NULL REFERENCES crm.crm_campaign_runs(run_id),
    contact_id      UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    delivery_status VARCHAR(30)   NOT NULL DEFAULT 'pending',
    sent_at         TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ,
    clicked_at      TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    error_message   TEXT
);

-- Campaign responses
CREATE TABLE IF NOT EXISTS crm.crm_campaign_responses (
    response_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID          NOT NULL REFERENCES crm.crm_campaign_runs(run_id),
    contact_id       UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    reply_body       TEXT          NOT NULL,
    intent_score     FLOAT,
    intent_label     VARCHAR(50),
    promoted_to_lead BOOLEAN       DEFAULT FALSE,
    promoted_lead_id UUID          REFERENCES crm.crm_leads(lead_id),
    responded_at     TIMESTAMPTZ   DEFAULT now()
);

-- Campaign events (open/click tracking)
CREATE TABLE IF NOT EXISTS crm.crm_campaign_events (
    event_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id    UUID          NOT NULL REFERENCES crm.crm_campaign_recipients(recipient_id),
    run_id          UUID          NOT NULL REFERENCES crm.crm_campaign_runs(run_id),
    event_type      VARCHAR(30)   NOT NULL,
    event_metadata  JSONB,
    occurred_at     TIMESTAMPTZ   DEFAULT now()
);
