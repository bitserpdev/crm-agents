import os
import uuid
import time
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

scheduler = BackgroundScheduler()

def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def run_campaign(campaign_id: str):
    print(f"\n[scheduler] Starting campaign: {campaign_id}")
    try:
        from agent.graph import build_graph
        graph = build_graph()
        graph.invoke({
            "campaign_id":       campaign_id,
            "campaign_config":   {},
            "sources_pending":   [],
            "current_source":    None,
            "raw_records":       [],
            "validated_records": [],
            "errors":            [],
            "agent_trace_id":    str(uuid.uuid4()),
            "run_status":        "running",
        })
        _update_last_run(campaign_id)
        print(f"[scheduler] ✓ Campaign {campaign_id} completed")
    except Exception as e:
        print(f"[scheduler] ✗ Campaign {campaign_id} failed: {e}")

def _update_last_run(campaign_id: str):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE lz_campaigns
        SET last_run_at = NOW(), updated_at = NOW()
        WHERE campaign_id = %s
    """, (campaign_id,))
    conn.commit()
    cur.close()
    conn.close()

def register_campaign(campaign: dict):
    parts = campaign["cron_expression"].split()
    if len(parts) != 5:
        print(f"[scheduler] Invalid CRON: {campaign['cron_expression']}")
        return
    scheduler.add_job(
        func=run_campaign,
        trigger=CronTrigger(
            minute=parts[0], hour=parts[1],
            day=parts[2],    month=parts[3],
            day_of_week=parts[4]
        ),
        id=str(campaign["campaign_id"]),
        replace_existing=True,
        args=[str(campaign["campaign_id"])]
    )
    print(f"[scheduler] Registered: {campaign['campaign_name']} ({campaign['cron_expression']})")

def process_retry_queue():
    from landing.redis_client import pop_retry_queue
    items = pop_retry_queue()
    for campaign_id in items:
        print(f"[scheduler] Retrying campaign: {campaign_id}")
        run_campaign(campaign_id)

def load_all_campaigns():
    conn = get_conn()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT campaign_id, campaign_name, cron_expression
        FROM lz_campaigns
        WHERE is_active = TRUE
    """)
    campaigns = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(c) for c in campaigns]

def send_due_followups():
    """Send proactive follow-ups for sequences due today."""
    try:
        from agent4.nodes.followup_sender import send_due_followups as _send
        _send()
    except Exception as e:
        print(f"[scheduler] Followup sender error: {e}")

def run_agent4_worker():
    """Process all pending replies in the queue."""
    try:
        import redis
        from agent4.graph import run_agent4
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        count = 0
        while r.llen("op:reply_queue") > 0:
            result = run_agent4()
            if result.get("run_status") == "skipped":
                break
            count += 1
        if count:
            print(f"[scheduler] Agent 4 processed {count} replies")
    except Exception as e:
        print(f"[scheduler] Agent 4 worker error: {e}")

def run_agent2_batch():
    print("\n[scheduler] Agent 2 batch starting...")
    try:
        from agent2.graph import build_agent2_graph
        graph = build_agent2_graph()
        result = graph.invoke({
            "trigger_type":      "batch",
            "raw_events":        [],
            "extracted_records": [],
            "enriched_records":  [],
            "loaded_records":    [],
            "errors":            [],
            "agent_trace_id":    str(uuid.uuid4()),
            "run_status":        "running",
            "stats":             {},
        })
        print(f"[scheduler] Agent 2 batch done. Stats: {result.get('stats')}")
    except Exception as e:
        print(f"[scheduler] Agent 2 batch error: {e}")

def run_agent2_realtime():
    """Called when high-intent events are in op:lead_score_queue."""
    from agent2.graph import build_agent2_graph
    graph = build_agent2_graph()
    graph.invoke({
        "trigger_type":      "realtime",
        "raw_events":        [],
        "extracted_records": [],
        "enriched_records":  [],
        "loaded_records":    [],
        "errors":            [],
        "agent_trace_id":    str(uuid.uuid4()),
        "run_status":        "running",
        "stats":             {},
    })

def monitor_campaign_replies():
    """Check Outlook inbox for replies to all active campaigns."""
    from agent3.nodes.monitor import monitor_replies
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT campaign_id FROM crm.crm_campaigns
        WHERE campaign_type = 'email'
          AND azure_token IS NOT NULL
          AND campaign_status != 'draft'
    """)
    campaigns = cur.fetchall()
    cur.close(); conn.close()
    for c in campaigns:
        monitor_replies(str(c["campaign_id"]))

def start():
    print("[scheduler] Loading campaigns from DB...")
    campaigns = load_all_campaigns()

    if not campaigns:
        print("[scheduler] No active campaigns found — scheduler waiting")
    else:
        for c in campaigns:
            register_campaign(c)

    # Retry queue consumer every 30 seconds
    scheduler.add_job(
        func=process_retry_queue,
        trigger="interval",
        seconds=30,
        id="retry_queue_consumer",
        max_instances=1,
        coalesce=True,
    )

    # Agent 4 reply worker every 10 seconds
    scheduler.add_job(
        func=run_agent4_worker,
        trigger="interval",
        seconds=10,
        id="agent4_reply_worker",
        max_instances=1,
        coalesce=True,
    )

    # Agent 4 proactive follow-up sender — check every hour
    scheduler.add_job(
        func=send_due_followups,
        trigger="interval",
        minutes=60,
        id="agent4_followup_sender"
    )

    # Agent 3 reply monitor every 30 minutes
    scheduler.add_job(
        func=monitor_campaign_replies,
        trigger="interval",
        minutes=30,
        id="agent3_reply_monitor",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    print(f"[scheduler] Started with {len(campaigns)} campaign(s)")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("[scheduler] Stopped")

if __name__ == "__main__":
    start()
