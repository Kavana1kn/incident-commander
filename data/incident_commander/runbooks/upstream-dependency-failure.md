# Runbook: Upstream Dependency Failure / Circuit Breaker Open

**Applies to:** Any service with a downstream dependency (search-service -> catalog-api).
**Symptoms:** Upstream returns 503, `Circuit breaker transitioned CLOSED -> OPEN`, high `upstream_error_rate`, degraded/stale results, but the service's OWN error_rate stays modest because of graceful degradation.

## Likely causes
1. The downstream/upstream dependency is itself unhealthy (not this service).
2. Network partition or DNS issue between the service and the dependency.
3. Downstream capacity exhaustion or its own deploy.

## Diagnosis steps
1. Confirm there was **no** deploy/config change to this service (see `deploys.json`); if none, the fault is upstream.
2. Check the dependency's own health dashboard and page the owning team.
3. Verify the circuit breaker is doing its job (serving from cache / degraded mode) so blast radius is limited.

## Remediation
- **Immediate (mitigate):** Keep the circuit breaker OPEN and continue serving degraded/cached results; do NOT roll back this service (it is not the cause).
- **Escalate:** Page the team that owns the failing dependency (catalog-api). This is the primary action.
- **Fix forward:** Add/verify fallback data freshness limits and customer-facing degraded-mode messaging.

## Severity guidance
If graceful degradation keeps customer impact low, this is typically **SEV-3** for this service but may be **SEV-1/2** for the dependency owner. Escalate rather than self-remediate.
