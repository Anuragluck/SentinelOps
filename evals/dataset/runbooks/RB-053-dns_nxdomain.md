# Runbook RB-053: DNS_NXDOMAIN response for checkout-api

## Symptoms
DNS NXDOMAIN service discovery failure. Alert codes may include `DNS_NXDOMAIN`.

## Root cause
Cause: The service discovery record was missing for the upstream endpoint.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `checkout-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
