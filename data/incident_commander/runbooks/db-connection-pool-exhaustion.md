# Runbook: Database Connection Pool Exhaustion

**Applies to:** Any service using a HikariCP / JDBC connection pool (checkout-service, orders-service).
**Symptoms:** `Connection is not available, request timed out`, `SQLTransientConnectionException`, `DB pool EXHAUSTED`, rising `db_pool_active` pinned at max, error_rate spike, p99 latency at the pool timeout ceiling (e.g. 5000ms).

## Likely causes
1. Pool size set too low for current traffic (recent config/deploy change).
2. A query regression (e.g. N+1 pattern) holding connections far longer than before.
3. A downstream DB slowdown or lock causing connections to be held.
4. Connection leak (connections not returned to the pool).

## Diagnosis steps
1. Check for a recent deploy or config change immediately before the incident start time. Correlate with `deploys.json`.
2. Inspect logs for "Slow query detected" and repeated identical queries per request (N+1).
3. Confirm `db_pool_active` is pinned at max and `waiting` is growing.
4. Verify the database itself is healthy (CPU, locks, slow log) to rule out a DB-side cause.

## Remediation
- **Immediate (mitigate):** Roll back the most recent deploy if the incident started right after it. This is the fastest safe action when a change is the correlated trigger.
- **Short term:** Increase pool size back to the known-good value (e.g. 50) and redeploy, if rollback is not possible.
- **Fix forward:** Eliminate the N+1 query (batch/join the `cart_items` fetch), then restore pool size deliberately.
- Add a connection-acquisition timeout alert and a pool-utilization dashboard.

## Rollback procedure
`kubectl rollout undo deployment/<service>` then verify `db_pool_active` drops and error_rate returns to baseline within 5 minutes.

## Severity guidance
Sustained error_rate > 0.5 on a checkout/payment path is **SEV-1** (revenue-impacting).
