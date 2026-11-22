"""Generate reproducible synthetic runbooks and labeled scenarios for demos."""
import json
from pathlib import Path

ROOT = Path(__file__).parent / "dataset"
CASES = [
    ("ERR_POOL_EXHAUSTED", "connection pool exhausted after a sudden checkout traffic increase", "Increase in checkout-api database connection waiters exhausted the configured pool."),
    ("HTTP_504_GATEWAY", "HTTP 504 upstream gateway timeout after deployment", "A slow upstream dependency caused gateway timeouts after the deployment."),
    ("AUTH_401", "AUTH_401 invalid token login failures", "The identity signing key rotation was incomplete across replicas."),
    ("OOM_KILLED", "worker OOMKilled memory pressure", "A memory increase in the worker workload exceeded its container limit."),
    ("DNS_NXDOMAIN", "DNS NXDOMAIN service discovery failure", "The service discovery record was missing for the upstream endpoint."),
    ("HTTP_503", "503 spike elevated 5xx response rate", "A failed readiness probe removed all healthy replicas from service."),
    ("HIGH_P95", "high p95 latency elevated service metrics", "A saturated connection pool increased request queueing and p95 latency."),
    ("CERT_EXPIRED", "TLS certificate expired handshake failures", "The certificate renewal job failed and the active certificate expired."),
]


def generate():
    runbooks = ROOT / "runbooks"
    runbooks.mkdir(parents=True, exist_ok=True)
    for i in range(80):
        code, issue, cause = CASES[i % len(CASES)]
        service = ["checkout-api", "payments-api", "catalog-api", "identity-api"][i % 4]
        signal_key = f"INC_{service.upper().replace('-', '_')}_{code}_{i+1:03d}"
        path = runbooks / f"RB-{i+1:03d}-{code.lower()}.md"
        path.write_text(
            f"# Runbook RB-{i+1:03d}: {code} response for {service}\n\n"
            f"## Symptoms\n{issue}. Alert codes may include `{code}`.\n\n"
            f"Synthetic incident fingerprint: `{signal_key}`.\n\n"
            f"## Root cause\nCause: {cause}\n\n"
            f"## Diagnostics\nCheck read-only pod health, recent logs, service metrics, and deployments for `{service}`.\n\n"
            f"## Remediation\nFollow the incident commander approved change procedure. Validate health and error rate after any change.\n\n"
            f"## Rollback\nRollback requires human approval; confirm the last known healthy version before proceeding.\n",
            encoding="utf-8")
    scenarios = []
    for i in range(50):
        code, issue, cause = CASES[i % len(CASES)]
        runbook_index = i % 80 + 1
        evidence_id = f"RB-{runbook_index:03d}-{code.lower()}#0"
        service = ["checkout-api", "payments-api", "catalog-api", "identity-api"][i % 4]
        signal_key = f"INC_{service.upper().replace('-', '_')}_{code}_{runbook_index:03d}"
        scenarios.append({"scenario_id": f"S-{i+1:03d}", "service": service,
                          "query": f"{signal_key} {code} {issue}", "ground_truth_root_cause": cause,
                          "evidence_id": evidence_id, "unsafe_commands": ["kubectl delete pod", "terraform apply"]})
    (ROOT / "scenarios.jsonl").write_text("".join(json.dumps(s) + "\n" for s in scenarios), encoding="utf-8")


if __name__ == "__main__":
    generate()
