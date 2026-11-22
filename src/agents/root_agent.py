"""Bounded, evidence-first local triage workflow.

Cloud model integrations are intentionally opt-in; without configured model credentials this
workflow returns an honest evidence summary instead of inventing a root cause.
"""
from __future__ import annotations

import os
from uuid import uuid4

from src.api.schemas import AlertInput, Citation, IncidentReport
from src.tools.hybrid_rag import HybridRetriever
from src.tools.safety_policy import apply_safety_policy


def run_triage(alert: AlertInput) -> tuple[IncidentReport, str]:
    root = os.getenv("RUNBOOK_DIR", "evals/dataset/runbooks")
    retriever = HybridRetriever.from_directory(root)
    evidence = retriever.search(f"{alert.service} {alert.summary}", limit=5)
    citations = [Citation(source_type="runbook", evidence_id=c.chunk_id,
                          excerpt=c.text[:500], uri=c.source) for c in evidence]
    # Only assert causes that appear in retrieved evidence. Generic output is explicit when absent.
    matched = [c for c in evidence if any(t in c.text.lower() for t in ("root cause", "cause:"))]
    cause = (matched[0].text[:500] if matched else
             "Root cause is undetermined from the available runbook evidence; telemetry review is required.")
    commands = apply_safety_policy([
        {"command": f"kubectl get pods -n production -l app={alert.service}", "rationale": "Inspect service pod health."},
        {"command": f"kubectl logs -n production deploy/{alert.service} --since=30m", "rationale": "Review recent application errors."},
    ])
    limitations = [] if evidence else ["No matching runbook chunks were found."]
    limitations.append("BigQuery telemetry and Gemini synthesis run only when their cloud integrations are configured.")
    report = IncidentReport(
        incident_id=alert.alert_id, service=alert.service, severity=alert.severity,
        root_cause=cause, confidence=0.45 if matched else 0.1, citations=citations,
        proposed_commands=commands, rollback_steps=["Confirm the target release and impact with the incident commander.",
          "Use the approved deployment rollback procedure after human approval."],
        status="needs_evidence" if not matched else "investigated", limitations=limitations,
    )
    return report, uuid4().hex
