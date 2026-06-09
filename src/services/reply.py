from core.database import get_db, get_dict_cursor
from core.redis import get_redis
from core.logger import logger


class ReplyService:

    def run_agent4_worker(self):
        """Process all pending replies sitting in op:reply_queue."""
        logger.info("[reply] Agent 4 worker starting")
        try:
            from agents.agent4.graph import run_agent4
            from agents.agent4.queue import normalize_reply_queue
            r     = get_redis()
            remaining = normalize_reply_queue(r)
            if remaining:
                logger.info("[reply] Reply queue normalized", pending=remaining)
            count = 0
            while r.llen("op:reply_queue") > 0:
                result = run_agent4()
                if result.get("run_status") == "skipped":
                    break
                count += 1
            if count:
                logger.info("[reply] Agent 4 processed replies", count=count)
        except Exception as e:
            logger.error("[reply] Agent 4 worker error", error=str(e))
            raise

    def send_due_followups(self):
        """Send proactive follow-ups for sequences due today."""
        logger.info("[reply] Sending due follow-ups")
        try:
            from agents.agent4.nodes.followup_sender import send_due_followups as _send
            _send()
            logger.info("[reply] Follow-ups sent")
        except Exception as e:
            logger.error("[reply] Follow-up sender error", error=str(e))
            raise

    def monitor_campaign_replies(self):
        """Check inbox for replies across all active email campaigns."""
        logger.info("[reply] Monitoring campaign replies")
        try:
            from agents.agent3.nodes.moniter import monitor_replies
            for campaign in self._load_email_campaigns():
                monitor_replies(str(campaign["campaign_id"]))
        except Exception as e:
            logger.error("[reply] Monitor error", error=str(e))
            raise

    def _load_email_campaigns(self) -> list:
        with get_db() as conn:
            cur = get_dict_cursor(conn)
            cur.execute(
                """
                SELECT DISTINCT campaign_id
                FROM crm.crm_campaigns
                WHERE campaign_type = 'email'
                  AND campaign_status = 'draft'
                """
            )
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]


reply_service = ReplyService()