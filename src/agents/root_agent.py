"""Bounded, evidence-first local triage workflow.

Cloud model integrations are intentionally opt-in; without configured model credentials this
workflow returns an honest evidence summary instead of inventing a root cause.
"""
from __future__ import annotations

import json
import os
import re
from uuid import uuid4

from src.api.schemas import AlertInput, Citation, IncidentReport
from src.tools.hybrid_rag import HybridRetriever
from src.tools.safety_policy import apply_safety_policy


def run_triage(alert: AlertInput) -> tuple[IncidentReport, str]:
    root = os.getenv("RUNBOOK_DIR", "evals/dataset/runbooks")
    retriever = HybridRetriever.from_directory(root)
    candidates = retriever.search(f"{alert.service} {alert.summary}", limit=20)
    evidence = [chunk for chunk in candidates if _matches_service(chunk.text, alert.service)][:5]
    citations = [Citation(source_type="runbook", evidence_id=c.chunk_id,
                          excerpt=c.text[:500], uri=c.source) for c in evidence]
    telemetry_available = False
    errors, deployments, metrics = [], [], []
    try:
        from src.tools.bigquery_tools import recent_deployments, recent_errors, recent_metrics
        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            errors = recent_errors(alert.service, since_minutes=60, limit=30)
            deployments = recent_deployments(alert.service, limit=10)
            metrics = recent_metrics(alert.service, limit=30)
            telemetry_available = True
            for source_type, rows in (("error_logs", errors), ("recent_deployments", deployments),
                                      ("service_metrics", metrics)):
                for row in rows[:5]:
                    stamp = row.get("timestamp")
                    if stamp is not None:
                        citations.append(Citation(
                            source_type="bigquery", evidence_id=f"bq:{source_type}:{stamp}",
                            excerpt=json.dumps(row, default=str, ensure_ascii=False)[:1000],
                            uri=f"bigquery:{os.getenv('BIGQUERY_DATASET', 'sentinelops')}.{source_type}",
                        ))
    except Exception:  # noqa: BLE001 - BigQuery enrichment is optional; local evidence remains usable.
        errors, deployments, metrics = [], [], []
    # Only assert causes that appear in retrieved evidence. Generic output is explicit when absent.
    matched = [c for c in evidence if any(t in c.text.lower() for t in ("root cause", "cause:"))]
    latest_error = errors[0] if errors else None
    latest_deployment = deployments[0] if deployments else None
    if latest_error and latest_error.get("error_code"):
        cause = (f"BigQuery reports {latest_error['error_code']} for {alert.service} at "
                 f"{latest_error.get('timestamp')}; correlate this with the cited runbook before remediation.")
    elif matched:
        cause = matched[0].text[:500]
    elif latest_deployment and latest_deployment.get("status") == "FAILED":
        cause = (f"The latest recorded deployment for {alert.service} failed at "
                 f"{latest_deployment.get('timestamp')}; further correlation is required.")
    else:
        cause = "Root cause is undetermined from the available runbook and telemetry evidence."
    commands = apply_safety_policy([
        {"command": f"kubectl get pods -n {alert.environment} -l app={alert.service}", "rationale": "Inspect service pod health."},
        {"command": f"kubectl logs -n {alert.environment} deploy/{alert.service} --since=30m", "rationale": "Review recent application errors."},
    ])
    limitations = [] if evidence else ["No matching runbook chunks were found."]
    if not telemetry_available:
        limitations.append("BigQuery telemetry was unavailable; configure project access and seed the required tables.")
    limitations.append("Gemini synthesis is enabled only when AGENT_BACKEND=adk and Google credentials are configured.")
    from src.agents.triage_supervisor import classify
    severity = classify(alert)
    report = IncidentReport(
        incident_id=alert.alert_id, service=alert.service, severity=severity,
        root_cause=cause, confidence=0.7 if latest_error or latest_deployment else (0.45 if matched else 0.1), citations=citations,
        proposed_commands=commands, rollback_steps=["Confirm the target release and impact with the incident commander.",
          "Use the approved deployment rollback procedure after human approval."],
        status="investigated" if (matched or latest_error or latest_deployment) else "needs_evidence", limitations=limitations,
    )
    return report, uuid4().hex


def _matches_service(text: str, service: str) -> bool:
    """Keep service-specific runbooks from being cited for a different service."""
    service_mentions = set(re.findall(
        r"\b[A-Za-z][A-Za-z0-9._-]*(?:-api|-service)\b", text, flags=re.IGNORECASE
    ))
    return not service_mentions or service.casefold() in {name.casefold() for name in service_mentions}
