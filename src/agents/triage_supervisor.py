"""Severity routing helpers; deterministic and bounded."""
from src.api.schemas import AlertInput, Severity


def classify(alert: AlertInput) -> Severity:
    if alert.severity != Severity.UNKNOWN:
        return alert.severity
    text = alert.summary.lower()
    if any(k in text for k in ("all users", "complete outage", "data loss")):
        return Severity.SEV1
    if any(k in text for k in ("elevated errors", "5xx", "unavailable", "latency")):
        return Severity.SEV2
    return Severity.SEV3
