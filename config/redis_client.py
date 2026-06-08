import os
import json
import time
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client = None


def get_redis():
    global _client
    if _client is None:
        _client = redis.from_url()
    return _client


def push_to_inbound_queue(event: dict):
    get_redis().lpush("lz:inbound_queue", json.dumps(event))


def check_dedup(dedup_key: str) -> str | None:
    val = get_redis().get(f"lz:dedup:{dedup_key}")
    return val.decode() if val else None


def set_dedup(dedup_key: str, event_id: str):
    get_redis().set(f"lz:dedup:{dedup_key}", event_id, ex=86400)


def acquire_lock(platform: str, trace_id: str) -> bool:
    return get_redis().set(f"lz:agent1:lock:{platform}", trace_id, nx=True, px=30000)


def release_lock(platform: str):
    get_redis().delete(f"lz:agent1:lock:{platform}")


def increment_rate_limit(platform: str) -> int:
    window = int(time.time() // 60)
    key = f"lz:ratelimit:{platform}:{window}"
    count = get_redis().incr(key)
    if count == 1:
        get_redis().expire(key, 60)
    return count


def add_to_retry_queue(event_id: str, delay_seconds: int = 60):
    score = time.time() + delay_seconds
    get_redis().zadd("lz:retry_queue", {event_id: score})


def pop_retry_queue() -> list:
    now = time.time()
    r = get_redis()
    members = r.zrangebyscore("lz:retry_queue", 0, now)
    if members:
        r.zremrangebyscore("lz:retry_queue", 0, now)
    return [m.decode() for m in members]
