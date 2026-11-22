# Runbook RB-058: HTTP_504_GATEWAY response for payments-api

## Symptoms
HTTP 504 upstream gateway timeout after deployment. Alert codes may include `HTTP_504_GATEWAY`.

## Root cause
Cause: A slow upstream dependency caused gateway timeouts after the deployment.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `payments-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
