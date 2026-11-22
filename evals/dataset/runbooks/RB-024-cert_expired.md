# Runbook RB-024: CERT_EXPIRED response for identity-api

## Symptoms
TLS certificate expired handshake failures. Alert codes may include `CERT_EXPIRED`.

## Root cause
Cause: The certificate renewal job failed and the active certificate expired.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `identity-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
