from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from secrets import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from src.agents.root_agent import run_triage
from src.api.schemas import AlertInput, TraceSummary, TriageResponse
from src.observability.tracing import configure_tracing, request_span


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
    return {"status": "ok", "service": "sentinelops", "time": datetime.now(UTC)}


@app.post("/v1/triage", response_model=TriageResponse, dependencies=[Depends(authenticate)])
async def triage(alert: AlertInput):
    started = time.perf_counter()
    mode = os.getenv("AGENT_BACKEND", "local").lower()
    usage = {}
    actual_mode = mode
    with request_span(alert.service, alert.alert_id) as trace_id:
        if mode == "adk":
            try:
                from src.agents.adk_workflow import run_adk_triage
                report, _, usage = await run_adk_triage(alert)
            except Exception:  # noqa: BLE001 - fall back to the deterministic local triage path.
                report, _ = await run_in_threadpool(run_triage, alert)
                report.limitations.append("ADK execution was unavailable; deterministic local triage was used.")
                actual_mode = "adk_fallback"
        else:
            report, _ = await run_in_threadpool(run_triage, alert)
            actual_mode = "local_fallback"
    duration_ms = (time.perf_counter() - started) * 1000
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    input_rate = os.getenv("INPUT_COST_PER_MILLION_USD")
    output_rate = os.getenv("OUTPUT_COST_PER_MILLION_USD")
    try:
        cost = (input_tokens * float(input_rate) + output_tokens * float(output_rate)) / 1_000_000 \
            if actual_mode == "adk" and input_rate is not None and output_rate is not None else (None if actual_mode == "adk" else 0.0)
    except (TypeError, ValueError):
        cost = None
    model = (f"{os.getenv('TRIAGE_MODEL', 'gemini-3.5-flash-lite')}+{os.getenv('SYNTHESIS_MODEL', 'gemini-3.5-flash')}"
             if actual_mode == "adk" else "local-deterministic")
    return TriageResponse(report=report, trace=TraceSummary(
        trace_id=trace_id, duration_ms=duration_ms, model=model,
        input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost_usd=cost,
    ), metadata={"mode": actual_mode,
                 "model_calls": usage.get("calls", 0),
                 "cost_is_estimate": cost is not None,
                 "generated_at": datetime.now(UTC).isoformat()})
