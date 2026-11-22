from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from secrets import compare_digest
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException

from src.agents.root_agent import run_triage
from src.api.schemas import AlertInput, TraceSummary, TriageResponse
from src.observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tracing()
    yield


app = FastAPI(title="SentinelOps", version="0.1.0", description="Evidence-grounded incident triage with deterministic safety controls.", lifespan=lifespan)


async def authenticate(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_KEY")
    if not expected and os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if expected and (not x_api_key or not compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
def health():
    return {"status": "ok", "service": "sentinelops", "time": datetime.now(timezone.utc)}


@app.post("/v1/triage", response_model=TriageResponse, dependencies=[Depends(authenticate)])
def triage(alert: AlertInput):
    started = time.perf_counter()
    report, trace_id = run_triage(alert)
    duration_ms = (time.perf_counter() - started) * 1000
    return TriageResponse(report=report, trace=TraceSummary(
        trace_id=trace_id, duration_ms=duration_ms, model=os.getenv("TRIAGE_MODEL", "local-deterministic"),
        estimated_cost_usd=0,
    ), metadata={"mode": "local_fallback", "generated_at": datetime.now(timezone.utc).isoformat()})
