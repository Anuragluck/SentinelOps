# Runbook RB-013: DNS_NXDOMAIN response for checkout-api

## Symptoms
DNS NXDOMAIN service discovery failure. Alert codes may include `DNS_NXDOMAIN`.

Synthetic incident fingerprint: `INC_CHECKOUT_API_DNS_NXDOMAIN_013`.

## Root cause
Cause: The service discovery record was missing for the upstream endpoint.

## Diagnostics
Check read-only pod health, recent logs, service metrics, and deployments for `checkout-api`.

## Remediation
Follow the incident commander approved change procedure. Validate health and error rate after any change.

## Rollback
Rollback requires human approval; confirm the last known healthy version before proceeding.
