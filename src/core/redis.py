import os
import json
import time
import redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import BusyLoadingError, ConnectionError, TimeoutError
from core.logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_CONN = int(os.getenv("REDIS_POOL_MAX", 20))
SOCKET_TO = int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))
CONNECT_TO = int(os.getenv("REDIS_CONNECT_TIMEOUT", 5))

_client = None


def get_redis():
    global _client
    if _client is None:
        retry = Retry(
            ExponentialBackoff(cap=10, base=1),
            retries=3,
            supported_errors=(BusyLoadingError, ConnectionError, TimeoutError),
        )
        pool = redis.ConnectionPool.from_url(
            REDIS_URL,
            max_connections=MAX_CONN,
            socket_timeout=SOCKET_TO,
            socket_connect_timeout=CONNECT_TO,
            decode_responses=False,
        )
        _client = redis.Redis(
            connection_pool=pool,
            retry=retry,
            retry_on_error=[BusyLoadingError, ConnectionError, TimeoutError],
        )
        logger.info(f"[redis] Pool initialized (max_connections={MAX_CONN})")
    return _client


# ── Queue ops ────────────────────────────────────────────────────────────────


def push_to_inbound_queue(event: dict):
    get_redis().lpush("lz:inbound_queue", json.dumps(event))


def pop_from_inbound_queue(block_seconds: int = 5) -> dict | None:
    """Blocking pop — better than polling in workers."""
    result = get_redis().brpop("lz:inbound_queue", timeout=block_seconds)
    if result:
        _, raw = result
        return json.loads(raw)
    return None


def push_batch_to_inbound_queue(events: list[dict]):
    """Push multiple events atomically via pipeline."""
    pipe = get_redis().pipeline()
    for event in events:
        pipe.lpush("lz:inbound_queue", json.dumps(event))
    pipe.execute()
    logger.debug(f"[redis] Pushed {len(events)} events to inbound queue")


# ── Dedup ────────────────────────────────────────────────────────────────────


def check_dedup(dedup_key: str) -> str | None:
    val = get_redis().get(f"lz:dedup:{dedup_key}")
    return val.decode() if val else None


def set_dedup(dedup_key: str, event_id: str):
    get_redis().set(f"lz:dedup:{dedup_key}", event_id, ex=86400)


# ── Locks ────────────────────────────────────────────────────────────────────


def acquire_lock(platform: str, trace_id: str, ttl_ms: int = 30000) -> bool:
    return get_redis().set(f"lz:agent1:lock:{platform}", trace_id, nx=True, px=ttl_ms)


def release_lock(platform: str):
    get_redis().delete(f"lz:agent1:lock:{platform}")


# ── Rate limiting ────────────────────────────────────────────────────────────


def increment_rate_limit(platform: str, window_seconds: int = 60) -> int:
    window = int(time.time() // window_seconds)
    key = f"lz:ratelimit:{platform}:{window}"
    pipe = get_redis().pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    count, _ = pipe.execute()
    return count


# ── Retry queue ──────────────────────────────────────────────────────────────


def add_to_retry_queue(event_id: str, delay_seconds: int = 60):
    score = time.time() + delay_seconds
    get_redis().zadd("lz:retry_queue", {event_id: score})


def pop_retry_queue() -> list[str]:
    r = get_redis()
    now = time.time()
    pipe = r.pipeline()
    pipe.zrangebyscore("lz:retry_queue", 0, now)
    pipe.zremrangebyscore("lz:retry_queue", 0, now)
    members, _ = pipe.execute()
    return [m.decode() for m in members]
