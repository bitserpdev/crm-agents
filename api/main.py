import os
import uuid
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api.routers import campaigns, connectors, runs, data, crm, agent3, email_campaigns, agent4, agent5, agent6

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler on app startup
    from scheduler.cron import start as start_scheduler
    import threading
    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()
    print("[api] Scheduler started in background")
    yield
    print("[api] Shutting down")

app = FastAPI(
    title="BITS CRM Agent API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://56.228.70.10:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaigns.router,  prefix="/api/campaigns",  tags=["Campaigns"])
app.include_router(connectors.router, prefix="/api/connectors", tags=["Connectors"])
app.include_router(runs.router,       prefix="/api/runs",       tags=["Runs"])
app.include_router(agent3.router,   prefix="/api/agent3",   tags=["Agent3"])
app.include_router(agent4.router)
app.include_router(crm.router,       prefix="/api/crm",       tags=["CRM"])
app.include_router(data.router,       prefix="/api/data",       tags=["Data"])
app.include_router(email_campaigns.router, prefix="/api/email-campaigns", tags=["Email Campaigns"])
app.include_router(agent5.router, tags=["Agent5"])
app.include_router(agent6.router, tags=["Agent6"])

@app.get("/health")
def health():
    import psycopg2, redis as redis_lib
    from qdrant_client import QdrantClient
    status = {}

    # PostgreSQL
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        conn.close()
        status["postgres"] = "ok"
    except Exception as e:
        status["postgres"] = str(e)

    # Redis
    try:
        r = redis_lib.from_url(os.getenv("REDIS_URL"))
        r.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = str(e)

    # Qdrant
    try:
        q = QdrantClient(url=os.getenv("QDRANT_URL"))
        q.get_collections()
        status["qdrant"] = "ok"
    except Exception as e:
        status["qdrant"] = str(e)

    status["ollama"] = "local"
    all_ok = all(v == "ok" or v == "local" for v in status.values())
    return {"status": "healthy" if all_ok else "degraded", "services": status}

@app.get("/")
def root():
    return {"message": "BITS CRM Agent API", "docs": "/docs"}
