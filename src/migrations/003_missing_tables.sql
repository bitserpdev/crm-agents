-- =============================================================================
-- BITS CRM — Operational Database
-- Migration 003 — Missing 18 tables
-- Run AFTER migration 002
-- =============================================================================

SET search_path TO crm, public;

-- -----------------------------------------------------------------------------
-- 11. crm_segments
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_segments (
    segment_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_name      VARCHAR(200)  NOT NULL UNIQUE,
    segment_type      VARCHAR(30)   NOT NULL,   -- static | dynamic | ai_generated
    description       TEXT,
    filter_rules      JSONB,
    qdrant_filter     JSONB,
    contact_count     INTEGER       DEFAULT 0,
    last_computed_at  TIMESTAMPTZ,
    created_by        UUID          NOT NULL REFERENCES crm.crm_users (user_id),
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 12. crm_templates
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_templates (
    template_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    template_name    VARCHAR(200)  NOT NULL,
    template_type    VARCHAR(30)   NOT NULL,   -- email | sms | proposal_section
    subject_line     VARCHAR(500),
    body_text        TEXT,
    body_html        TEXT,
    merge_variables  JSONB,
    qdrant_point_id  UUID,
    created_by       UUID          NOT NULL REFERENCES crm.crm_users (user_id),
    created_at       TIMESTAMPTZ   DEFAULT now(),
    updated_at       TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 13. crm_opportunities
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_opportunities (
    opportunity_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id           UUID          NOT NULL REFERENCES crm.crm_leads    (lead_id),
    contact_id        UUID          NOT NULL REFERENCES crm.crm_contacts (contact_id),
    company_id        UUID          REFERENCES crm.crm_companies         (company_id),
    assigned_to       UUID          REFERENCES crm.crm_users             (user_id),
    opp_name          VARCHAR(200)  NOT NULL,
    opp_stage         VARCHAR(50)   NOT NULL,
        -- qualification | proposal_required | proposal_sent | negotiation | won | lost
    deal_value        NUMERIC(14,2),
    currency          CHAR(3)       DEFAULT 'USD',
    probability_pct   SMALLINT,
    win_reason        TEXT,
    loss_reason       TEXT,
    expected_close_at DATE,
    closed_at         TIMESTAMPTZ,
    won_at            TIMESTAMPTZ,
    created_by_agent  VARCHAR(50),
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now()
);

-- Deferred FK on crm_leads.converted_to_opp
ALTER TABLE crm.crm_leads
    ADD COLUMN IF NOT EXISTS converted_to_opp UUID,
    ADD CONSTRAINT fk_leads_converted_to_opp
        FOREIGN KEY (converted_to_opp) REFERENCES crm.crm_opportunities (opportunity_id);

-- -----------------------------------------------------------------------------
-- 14. crm_lead_stage_history
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_lead_stage_history (
    history_id     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id        UUID          NOT NULL REFERENCES crm.crm_leads (lead_id),
    from_stage     VARCHAR(30),
    to_stage       VARCHAR(30)   NOT NULL,
    changed_by     VARCHAR(80),
    change_reason  TEXT,
    changed_at     TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 15. crm_proposals
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_proposals (
    proposal_id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id      UUID          NOT NULL REFERENCES crm.crm_opportunities (opportunity_id),
    contact_id          UUID          NOT NULL REFERENCES crm.crm_contacts      (contact_id),
    created_by_user     UUID          REFERENCES crm.crm_users                  (user_id),
    proposal_title      VARCHAR(200)  NOT NULL,
    proposal_status     VARCHAR(30)   NOT NULL,
        -- draft | under_review | approved | sent | accepted | rejected
    cover_text          TEXT,
    scope_text          TEXT,
    timeline_text       TEXT,
    milestones          JSONB,
    pricing_details     JSONB,
    total_value         NUMERIC(14,2),
    currency            CHAR(3)       DEFAULT 'USD',
    terms_text          TEXT,
    rag_context_used    JSONB,
    sent_at             TIMESTAMPTZ,
    accepted_at         TIMESTAMPTZ,
    rejected_at         TIMESTAMPTZ,
    generated_by_agent  VARCHAR(50),
    created_at          TIMESTAMPTZ   DEFAULT now(),
    updated_at          TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 16. crm_proposal_approvals
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_proposal_approvals (
    approval_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id      UUID          NOT NULL REFERENCES crm.crm_proposals (proposal_id),
    reviewed_by      UUID          NOT NULL REFERENCES crm.crm_users     (user_id),
    approval_status  VARCHAR(20)   NOT NULL,   -- pending | approved | rejected
    review_notes     TEXT,
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 17. crm_scheduled_meetings
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_scheduled_meetings (
    meeting_id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id             UUID          REFERENCES crm.crm_leads         (lead_id),
    opportunity_id      UUID          REFERENCES crm.crm_opportunities (opportunity_id),
    contact_id          UUID          NOT NULL REFERENCES crm.crm_contacts (contact_id),
    rep_user_id         UUID          NOT NULL REFERENCES crm.crm_users    (user_id),
    meeting_title       VARCHAR(200)  NOT NULL,
    scheduled_at        TIMESTAMPTZ   NOT NULL,
    duration_minutes    SMALLINT      DEFAULT 30,
    meeting_status      VARCHAR(20)   NOT NULL,
        -- scheduled | completed | cancelled | rescheduled
    meeting_link        TEXT,
    calendar_event_id   VARCHAR(200),
    scheduled_by_agent  VARCHAR(50),
    created_at          TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 18. crm_email_threads
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_email_threads (
    thread_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id          UUID          REFERENCES crm.crm_leads         (lead_id),
    opportunity_id   UUID          REFERENCES crm.crm_opportunities (opportunity_id),
    contact_id       UUID          NOT NULL REFERENCES crm.crm_contacts (contact_id),
    rep_user_id      UUID          REFERENCES crm.crm_users            (user_id),
    imap_thread_id   VARCHAR(200)  NOT NULL,
    subject          VARCHAR(500),
    thread_status    VARCHAR(30)   NOT NULL,
        -- active | agent_handling | rep_took_over | closed
    last_message_at  TIMESTAMPTZ,
    created_at       TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 19. crm_email_messages
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_email_messages (
    message_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id        UUID          NOT NULL REFERENCES crm.crm_email_threads (thread_id),
    direction        VARCHAR(10)   NOT NULL,   -- inbound | outbound
    from_address     VARCHAR(254)  NOT NULL,
    to_addresses     TEXT[]        NOT NULL,
    subject          VARCHAR(500),
    body_text        TEXT,
    body_html        TEXT,
    sent_at          TIMESTAMPTZ,
    received_at      TIMESTAMPTZ,
    sent_by_agent    VARCHAR(50),
    imap_message_id  VARCHAR(200)
);

-- -----------------------------------------------------------------------------
-- 20. crm_lead_notifications
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_lead_notifications (
    notification_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID          NOT NULL REFERENCES crm.crm_users (user_id),
    entity_type        VARCHAR(30)   NOT NULL,
    entity_id          UUID          NOT NULL,
    notification_type  VARCHAR(60)   NOT NULL,
        -- new_lead | proposal_ready | meeting_booked | opp_won
    message_text       TEXT,
    is_read            BOOLEAN       DEFAULT FALSE,
    created_at         TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 21. crm_campaigns
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_campaigns (
    campaign_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_name     VARCHAR(200)  NOT NULL,
    campaign_type     VARCHAR(30)   NOT NULL,   -- email | sms | push | multi_channel
    campaign_status   VARCHAR(30)   NOT NULL,
        -- draft | scheduled | running | paused | completed
    segment_id        UUID          REFERENCES crm.crm_segments  (segment_id),
    schedule_type     VARCHAR(20)   NOT NULL,   -- immediate | scheduled | recurring
    scheduled_at      TIMESTAMPTZ,
    recurrence_rule   VARCHAR(200),
    from_address      VARCHAR(254)  NOT NULL,
    reply_to          VARCHAR(254),
    subject_template  VARCHAR(500),
    body_template_id  UUID          REFERENCES crm.crm_templates (template_id),
    goal_type         VARCHAR(50),              -- awareness | lead_gen | nurture | win_back
    created_by        UUID          NOT NULL REFERENCES crm.crm_users (user_id),
    created_at        TIMESTAMPTZ   DEFAULT now(),
    updated_at        TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 22. crm_campaign_runs
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_campaign_runs (
    run_id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id       UUID          NOT NULL REFERENCES crm.crm_campaigns (campaign_id),
    run_status        VARCHAR(30)   NOT NULL,   -- pending | running | completed | failed
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

-- -----------------------------------------------------------------------------
-- 23. crm_campaign_recipients
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_campaign_recipients (
    recipient_id     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID          NOT NULL REFERENCES crm.crm_campaign_runs (run_id),
    contact_id       UUID          NOT NULL REFERENCES crm.crm_contacts      (contact_id),
    delivery_status  VARCHAR(30)   NOT NULL,   -- pending | sent | failed | bounced
    sent_at          TIMESTAMPTZ,
    opened_at        TIMESTAMPTZ,
    clicked_at       TIMESTAMPTZ,
    unsubscribed_at  TIMESTAMPTZ,
    error_message    TEXT
);

-- -----------------------------------------------------------------------------
-- 24. crm_campaign_events
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_campaign_events (
    event_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id    UUID          NOT NULL REFERENCES crm.crm_campaign_recipients (recipient_id),
    run_id          UUID          NOT NULL REFERENCES crm.crm_campaign_runs       (run_id),
    event_type      VARCHAR(30)   NOT NULL,
        -- open | click | bounce | unsubscribe | spam_report
    event_metadata  JSONB,
    occurred_at     TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 25. crm_campaign_responses
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_campaign_responses (
    response_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id            UUID          NOT NULL REFERENCES crm.crm_campaign_runs (run_id),
    contact_id        UUID          NOT NULL REFERENCES crm.crm_contacts      (contact_id),
    reply_body        TEXT          NOT NULL,
    intent_score      FLOAT,
    intent_label      VARCHAR(50),  -- hot | warm | cold | unsubscribe
    promoted_to_lead  BOOLEAN       DEFAULT FALSE,
    promoted_lead_id  UUID          REFERENCES crm.crm_leads (lead_id),
    responded_at      TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 26. crm_segment_members
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_segment_members (
    member_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_id  UUID          NOT NULL REFERENCES crm.crm_segments (segment_id),
    contact_id  UUID          NOT NULL REFERENCES crm.crm_contacts (contact_id),
    added_at    TIMESTAMPTZ   DEFAULT now(),
    removed_at  TIMESTAMPTZ   -- soft delete
);

-- -----------------------------------------------------------------------------
-- 27. crm_suppression_list
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_suppression_list (
    suppression_id    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    email             VARCHAR(254)  NOT NULL UNIQUE,
    suppression_type  VARCHAR(30)   NOT NULL,   -- unsubscribe | bounce | spam | manual
    contact_id        UUID          REFERENCES crm.crm_contacts (contact_id),
    reason            TEXT,
    suppressed_at     TIMESTAMPTZ   DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- 28. crm_notes
-- -----------------------------------------------------------------------------
CREATE TABLE crm.crm_notes (
    note_id     UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id  UUID          REFERENCES crm.crm_contacts      (contact_id),
    lead_id     UUID          REFERENCES crm.crm_leads         (lead_id),
    opp_id      UUID          REFERENCES crm.crm_opportunities (opportunity_id),
    created_by  UUID          NOT NULL REFERENCES crm.crm_users (user_id),
    note_text   TEXT          NOT NULL,
    is_pinned   BOOLEAN       DEFAULT FALSE,
    created_at  TIMESTAMPTZ   DEFAULT now()
);

