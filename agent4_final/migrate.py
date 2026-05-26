import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def migrate():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    # Add imap_message_id to crm_campaign_responses for dedup
    cur.execute("""
        ALTER TABLE crm.crm_campaign_responses
        ADD COLUMN IF NOT EXISTS imap_message_id TEXT
    """)

    # Add index for fast dedup lookup
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_campaign_responses_imap_id
        ON crm.crm_campaign_responses(imap_message_id)
        WHERE imap_message_id IS NOT NULL
    """)

    # Add asked_availability if not exists (from previous migration)
    cur.execute("""
        ALTER TABLE crm.crm_follow_up_sequences
        ADD COLUMN IF NOT EXISTS asked_availability BOOLEAN DEFAULT FALSE
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[migrate] ✓ imap_message_id column added to crm_campaign_responses")

if __name__ == "__main__":
    migrate()
