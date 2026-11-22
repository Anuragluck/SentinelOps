# Runbook RB-036: OOM_KILLED response for identity-api

## Symptoms
worker OOMKilled memory pressure. Alert codes may include `OOM_KILLED`.

## Root cause
Cause: A memory increase in the worker workload exceeded its container limit.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `identity-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
