import os
import sys
import structlog
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_AS_JSON = os.getenv("LOG_JSON", "false").lower() == "true"

LOG_DIR.mkdir(parents=True, exist_ok=True)


# ── stdlib handlers ───────────────────────────────────────────────────────────


def _build_stdlib_logger(name: str) -> logging.Logger:
    std_logger = logging.getLogger(name)
    std_logger.setLevel(LOG_LEVEL)

    if std_logger.handlers:
        return std_logger  # already configured (e.g. uvicorn reload)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        filename=LOG_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    std_logger.addHandler(file_handler)
    std_logger.addHandler(console_handler)
    return std_logger


# ── structlog config ──────────────────────────────────────────────────────────


def _configure_structlog():
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # request-scoped fields
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if LOG_AS_JSON:
        # Machine-readable — great for Datadog / Loki / CloudWatch
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-readable in dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, LOG_LEVEL, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


_build_stdlib_logger("crm-agent")
_configure_structlog()

logger = structlog.get_logger("crm-agent")
