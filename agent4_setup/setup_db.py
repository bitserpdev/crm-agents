import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def setup():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    # 1. crm_follow_up_sequences — tracks follow-up schedule per contact/campaign
    cur.execute("""
        CREATE TABLE IF NOT EXISTS crm.crm_follow_up_sequences (
            sequence_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id         UUID NOT NULL,
            contact_id          UUID NOT NULL,
            run_id              UUID NOT NULL,
            original_response_id UUID,
            current_step        INTEGER DEFAULT 0,       -- 0=initial reply, 1-5=follow-ups
            max_steps           INTEGER DEFAULT 5,
            status              VARCHAR(30) DEFAULT 'active',
                                                         -- active|paused|completed|exhausted|unsubscribed|call_scheduled
            next_followup_at    TIMESTAMPTZ,
            last_reply_at       TIMESTAMPTZ,
            last_intent_label   VARCHAR(20),
            teams_meeting_url   TEXT,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(campaign_id, contact_id)
        )
    """)

    # 2. crm_follow_up_emails — logs every follow-up email sent
    cur.execute("""
        CREATE TABLE IF NOT EXISTS crm.crm_follow_up_emails (
            followup_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sequence_id         UUID NOT NULL REFERENCES crm.crm_follow_up_sequences(sequence_id),
            contact_id          UUID NOT NULL,
            campaign_id         UUID NOT NULL,
            step_number         INTEGER NOT NULL,        -- 1-5
            direction           VARCHAR(10) DEFAULT 'outbound', -- outbound|inbound
            subject             TEXT,
            body                TEXT,
            intent_label        VARCHAR(20),
            intent_score        FLOAT,
            sent_at             TIMESTAMPTZ,
            received_at         TIMESTAMPTZ,
            delivery_status     VARCHAR(20) DEFAULT 'pending',
            error_message       TEXT,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # 3. crm_teams_meetings — stores Teams meeting links
    cur.execute("""
        CREATE TABLE IF NOT EXISTS crm.crm_teams_meetings (
            meeting_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sequence_id         UUID REFERENCES crm.crm_follow_up_sequences(sequence_id),
            contact_id          UUID NOT NULL,
            campaign_id         UUID NOT NULL,
            teams_meeting_id    TEXT,
            join_url            TEXT NOT NULL,
            subject             TEXT,
            scheduled_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # 4. Add reply_queue_key column to crm_campaign_responses if not exists
    cur.execute("""
        ALTER TABLE crm.crm_campaign_responses
        ADD COLUMN IF NOT EXISTS queued_for_agent4 BOOLEAN DEFAULT FALSE
    """)

    # 5. Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_followup_seq_contact ON crm.crm_follow_up_sequences(contact_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_followup_seq_status ON crm.crm_follow_up_sequences(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_followup_seq_next ON crm.crm_follow_up_sequences(next_followup_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_followup_emails_seq ON crm.crm_follow_up_emails(sequence_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_teams_meetings_contact ON crm.crm_teams_meetings(contact_id)")

    conn.commit()
    cur.close()
    conn.close()
    print("[agent4/setup] ✓ All tables created or already exist")

if __name__ == "__main__":
    setup()
