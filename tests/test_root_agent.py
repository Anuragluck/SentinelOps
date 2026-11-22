from pathlib import Path

from src.agents.root_agent import run_triage
from src.api.schemas import AlertInput


def test_triage_works_without_cloud_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("RUNBOOK_DIR", str(Path(__file__).parents[1] / "evals" / "dataset" / "runbooks"))

    report, _ = run_triage(AlertInput(
        service="checkout-api",
        summary="Elevated 5xx errors after recent deployment",
        severity="SEV2",
    ))

    assert report.service == "checkout-api"
    assert report.citations
    assert all("checkout-api" in citation.excerpt for citation in report.citations)
