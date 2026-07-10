# Runbook: Deploy Correlation, Rollback Policy & Severity Matrix

## Change-correlation rule
If an incident's start time is within ~5 minutes of a deploy or config change to the SAME service, treat that change as the prime suspect until proven otherwise. Always check `deploys.json`.

## Rollback policy
- Rolling back a recent, correlated deploy is the **preferred first mitigation** for a SEV-1/SEV-2 caused by a change: it is fast and reversible.
- Do NOT roll back a service when evidence shows the fault originates upstream/downstream (roll back solves nothing and adds churn).
- Every rollback must include a verification step: confirm the primary symptom metric returns to baseline within 5 minutes.

## Severity matrix
| Severity | Definition | Comms cadence |
|----------|------------|---------------|
| SEV-1 | Revenue-impacting or full outage on a critical path (checkout, payments) | Status page + exec update; updates every 15 min |
| SEV-2 | Partial degradation on a critical path or full outage on a non-critical path | Status page; updates every 30 min |
| SEV-3 | Minor/graceful degradation, limited customer impact | Internal channel only |

## Communications
- SEV-1/SEV-2 require a public status-page post AND an internal incident channel message.
- Comms must state: what is impacted, current status, the mitigation in progress, and the next-update time.
- Never include internal hostnames, credentials, or PII in customer-facing comms.

## Human-in-the-loop gate
No remediation action (rollback, restart, config change) and no customer-facing communication may be executed without an explicit human approver acknowledging the proposed action.
