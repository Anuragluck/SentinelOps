# Runbook RB-023: HIGH_P95 response for catalog-api

## Symptoms
high p95 latency elevated service metrics. Alert codes may include `HIGH_P95`.

Synthetic incident fingerprint: `INC_CATALOG_API_HIGH_P95_023`.

## Root cause
Cause: A saturated connection pool increased request queueing and p95 latency.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `catalog-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
