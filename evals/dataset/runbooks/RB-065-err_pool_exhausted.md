# Runbook RB-065: ERR_POOL_EXHAUSTED response for checkout-api

## Symptoms
connection pool exhausted after a sudden checkout traffic increase. Alert codes may include `ERR_POOL_EXHAUSTED`.

Synthetic incident fingerprint: `INC_CHECKOUT_API_ERR_POOL_EXHAUSTED_065`.

## Root cause
Cause: Increase in checkout-api database connection waiters exhausted the configured pool.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `checkout-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
