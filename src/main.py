from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from core.exception_handler import setup_exception_handlers
from core.database import get_conn, release_conn
from core.redis import get_redis
from core.qdrant import get_qdrant


@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    from scheduler.cron import start as start_scheduler

    threading.Thread(target=start_scheduler, daemon=True).start()
    yield


app = FastAPI(
    title="BITS CRM Agent API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

setup_exception_handlers(app)

# ── Domain routers ────────────────────────────────────────────────────────────
from domains.campaigns.router import router as campaigns_router
from domains.connectors.router import router as connectors_router
from domains.ingestion.router import router as raw_data_router
from domains.crm.router import router as crm_router
from domains.upwork.router import router as upwork_router
from domains.zoom.router import router as zoom_router

app.include_router(campaigns_router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(connectors_router, prefix="/api/connectors", tags=["Connectors"])
app.include_router(raw_data_router, prefix="/api/data", tags=["Raw Data"])
app.include_router(crm_router, prefix="/api/crm", tags=["CRM"])
app.include_router(upwork_router, prefix="/api/upwork", tags=["Upwork"])
app.include_router(zoom_router, prefix="/api/zoom")


# ── System routes ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health():
    status = {}

    try:
        conn = get_conn()
        release_conn(conn)
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = str(e)

    try:
        get_redis().ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = str(e)

    try:
        get_qdrant().get_collections()
        status["qdrant"] = "ok"
    except Exception as e:
        status["qdrant"] = str(e)

    status["ollama"] = "local"
    all_ok = all(v in ("ok", "local") for v in status.values())
    return {"status": "healthy" if all_ok else "degraded", "services": status}


@app.get("/", tags=["System"])
def root():
    return {"message": "BITS CRM Agent API", "docs": "/docs"}


@app.post("/dev/run-agent3")
def run_agent3_manual(campaign_id: str):
    from agents.agent3.nodes.moniter import monitor_replies

    monitor_replies(campaign_id)
    return {"status": "done"}


@app.post("/dev/run-agent4")
def run_agent4():
    from services.reply import reply_service

    reply_service.run_agent4_worker()
    return {"status": "done"}
