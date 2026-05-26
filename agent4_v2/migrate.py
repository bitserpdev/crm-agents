import os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

def migrate():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    # Add asked_availability column to sequences table
    cur.execute("""
        ALTER TABLE crm.crm_follow_up_sequences
        ADD COLUMN IF NOT EXISTS asked_availability BOOLEAN DEFAULT FALSE
    """)

    # Add awaiting_availability to valid statuses (just a comment — postgres varchar accepts any value)
    # Update any existing call_scheduled sequences that don't have teams_meeting_url
    # to awaiting_availability so they get handled correctly
    cur.execute("""
        UPDATE crm.crm_follow_up_sequences
        SET asked_availability = TRUE
        WHERE status = 'call_scheduled'
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[migrate] ✓ asked_availability column added")

if __name__ == "__main__":
    migrate()
