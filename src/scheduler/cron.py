import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.database import get_conn, release_conn, get_dict_cursor
from core.redis import pop_retry_queue
from core.logger import logger
from services.campaign import run_campaign, load_all_campaigns
from services.digest import run_daily_digest
from services.reply import reply_service

scheduler = BackgroundScheduler()


# ── Wrappers — scheduler only knows when, services know how ──────────────────


def _run_campaign(campaign_id: str):
    run_campaign(campaign_id)


def _run_daily_digest():
    run_daily_digest()


def _process_retry_queue():
    for campaign_id in pop_retry_queue():
        logger.info("[scheduler] Retrying campaign", campaign_id=campaign_id)
        run_campaign(campaign_id)


def _run_agent4_worker():
    reply_service.run_agent4_worker()


def _send_due_followups():
    reply_service.send_due_followups()


def _monitor_campaign_replies():
    reply_service.monitor_campaign_replies()


# ── Registration ──────────────────────────────────────────────────────────────


def register_campaign(campaign: dict):
    parts = campaign["cron_expression"].split()
    if len(parts) != 5:
        logger.warning(
            "[scheduler] Invalid CRON", expression=campaign["cron_expression"]
        )
        return
    scheduler.add_job(
        func=_run_campaign,
        trigger=CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        ),
        id=str(campaign["campaign_id"]),
        replace_existing=True,
        args=[str(campaign["campaign_id"])],
    )
    logger.info(
        "[scheduler] Campaign registered",
        name=campaign["campaign_name"],
        cron=campaign["cron_expression"],
    )


# ── Bootstrap ─────────────────────────────────────────────────────────────────


def start():
    campaigns = load_all_campaigns()
    for c in campaigns:
        register_campaign(c)

    scheduler.add_job(
        _process_retry_queue,
        "interval",
        minutes=60,
        id="retry_queue_consumer",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_agent4_worker,
        "interval",
        minutes=60,
        id="agent4_reply_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _send_due_followups,
        "interval",
        minutes=60,
        id="agent4_followup_sender",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _monitor_campaign_replies,
        "interval",
        seconds=100000,
        id="agent3_reply_monitor",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_daily_digest,
        trigger=CronTrigger(hour=0, minute=5),
        id="daily_upwork_digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[scheduler] Started", campaigns=len(campaigns))

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("[scheduler] Stopped")


if __name__ == "__main__":
    start()
