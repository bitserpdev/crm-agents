-- Create crm schema
CREATE SCHEMA IF NOT EXISTS crm;

-- Set search path
SET search_path TO crm, public;

-- 1. crm_companies
CREATE TABLE crm.crm_companies (
    company_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name    VARCHAR(200)  NOT NULL,
    domain          VARCHAR(253)  UNIQUE,
    industry        VARCHAR(100),
    company_size    VARCHAR(30),
    country         CHAR(2),
    city            VARCHAR(100),
    website_url     TEXT,
    linkedin_url    TEXT,
    annual_revenue  NUMERIC(18,2),
    crm_tier        VARCHAR(20),
    created_at      TIMESTAMPTZ   DEFAULT now(),
    updated_at      TIMESTAMPTZ   DEFAULT now()
);

-- 2. crm_users (seed one system agent user)
CREATE TABLE crm.crm_users (
    user_id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(150)  NOT NULL,
    email           VARCHAR(254)  NOT NULL UNIQUE,
    role            VARCHAR(30)   NOT NULL,
    is_active       BOOLEAN       DEFAULT TRUE,
    calendar_token  TEXT,
    smtp_alias      VARCHAR(254),
    created_at      TIMESTAMPTZ   DEFAULT now()
);

-- 3. crm_contacts
CREATE TABLE crm.crm_contacts (
    contact_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id        UUID          REFERENCES crm.crm_companies(company_id),
    first_name        VARCHAR(100)  NOT NULL,
    last_name         VARCHAR(100)  NOT NULL,
    email             VARCHAR(254)  NOT NULL UNIQUE,
    phone             VARCHAR(30),
    job_title         VARCHAR(150),
    linkedin_url      TEXT,
    contact_type      VARCHAR(30)   NOT NULL DEFAULT 'prospect',
    lifecycle_stage   VARCHAR(30)   NOT NULL DEFAULT 'subscriber',
    source_platform   VARCHAR(50),
    dedup_key         VARCHAR(64)   NOT NULL UNIQUE,
    lz_event_id       UUID,
    is_suppressed     BOOLEAN       DEFAULT FALSE,
    gdpr_consent      BOOLEAN       DEFAULT FALSE,
    gdpr_consent_at   TIMESTAMPTZ,
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now(),
    created_by_agent  VARCHAR(50)   DEFAULT 'agent-2-lead-creation'
);

-- 4. crm_contact_tags
CREATE TABLE crm.crm_contact_tags (
    tag_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id  UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    tag_name    VARCHAR(80)   NOT NULL,
    tagged_by   VARCHAR(50),
    created_at  TIMESTAMPTZ   DEFAULT now()
);

-- 5. crm_custom_field_values
CREATE TABLE crm.crm_custom_field_values (
    value_id     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type  VARCHAR(30)   NOT NULL,
    entity_id    UUID          NOT NULL,
    field_key    VARCHAR(80)   NOT NULL,
    field_value  TEXT,
    created_at   TIMESTAMPTZ   DEFAULT now()
);

-- 6. crm_leads
CREATE TABLE crm.crm_leads (
    lead_id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id         UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    company_id         UUID          REFERENCES crm.crm_companies(company_id),
    assigned_to        UUID          REFERENCES crm.crm_users(user_id),
    lz_event_id        UUID,
    lead_status        VARCHAR(30)   NOT NULL DEFAULT 'new',
    lead_score         SMALLINT      DEFAULT 0,
    source_platform    VARCHAR(50)   NOT NULL,
    source_detail      TEXT,
    initial_message    TEXT,
    budget_range       VARCHAR(50),
    project_scope      TEXT,
    estimated_value    NUMERIC(14,2),
    currency           CHAR(3)       DEFAULT 'USD',
    expected_close_at  DATE,
    last_activity_at   TIMESTAMPTZ,
    converted_at       TIMESTAMPTZ,
    created_by_agent   VARCHAR(50)   DEFAULT 'agent-2-lead-creation',
    created_at         TIMESTAMPTZ   DEFAULT now(),
    updated_at         TIMESTAMPTZ   DEFAULT now()
);

-- 7. crm_contact_scores
CREATE TABLE crm.crm_contact_scores (
    score_id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id        UUID          NOT NULL UNIQUE REFERENCES crm.crm_contacts(contact_id),
    lead_score        SMALLINT      DEFAULT 0,
    engagement_score  SMALLINT      DEFAULT 0,
    intent_score      FLOAT         DEFAULT 0,
    fit_score         SMALLINT      DEFAULT 0,
    overall_score     SMALLINT      DEFAULT 0,
    score_breakdown   JSONB,
    scored_by_agent   VARCHAR(50),
    last_scored_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now()
);

-- 8. crm_contact_score_history
CREATE TABLE crm.crm_contact_score_history (
    history_id  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id  UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    score_type  VARCHAR(30)   NOT NULL,
    old_score   SMALLINT,
    new_score   SMALLINT      NOT NULL,
    changed_by  VARCHAR(50),
    changed_at  TIMESTAMPTZ   DEFAULT now()
);

-- 9. crm_agent_actions
CREATE TABLE crm.crm_agent_actions (
    action_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id       VARCHAR(50)   NOT NULL,
    action_type    VARCHAR(80)   NOT NULL,
    entity_type    VARCHAR(30)   NOT NULL,
    entity_id      UUID          NOT NULL,
    action_detail  JSONB,
    outcome        VARCHAR(30),
    ran_at         TIMESTAMPTZ   DEFAULT now()
);

-- 10. crm_activity_log
CREATE TABLE crm.crm_activity_log (
    activity_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id       UUID          NOT NULL REFERENCES crm.crm_contacts(contact_id),
    lead_id          UUID          REFERENCES crm.crm_leads(lead_id),
    activity_type    VARCHAR(60)   NOT NULL,
    activity_source  VARCHAR(50)   NOT NULL,
    source_id        VARCHAR(80),
    summary          TEXT,
    metadata         JSONB,
    occurred_at      TIMESTAMPTZ   DEFAULT now()
);

-- Seed system agent user
INSERT INTO crm.crm_users (user_id, full_name, email, role)
VALUES (
    gen_random_uuid(),
    'Agent 2 System',
    'agent2@bits-crm.internal',
    'admin'
);
