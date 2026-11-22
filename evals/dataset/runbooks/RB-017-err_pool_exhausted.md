# Runbook RB-017: ERR_POOL_EXHAUSTED response for checkout-api

## Symptoms
connection pool exhausted after a sudden checkout traffic increase. Alert codes may include `ERR_POOL_EXHAUSTED`.

## Root cause
Cause: Increase in checkout-api database connection waiters exhausted the configured pool.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `checkout-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
