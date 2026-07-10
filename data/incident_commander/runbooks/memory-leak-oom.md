# Runbook: Memory Leak / OutOfMemoryError (OOMKilled)

**Applies to:** JVM services (payments-service, ledger-service).
**Symptoms:** `java.lang.OutOfMemoryError: Java heap space`, `OOMKilled`, climbing `heap_used_mb`, rising `gc_pct` (GC overhead), repeated pod restarts.

## Likely causes
1. Unbounded cache or collection with no eviction policy (common: rate/price caches).
2. Objects retained by a static reference or listener that is never removed.
3. Heap sized too small for working set after a feature that increased retained data.

## Diagnosis steps
1. Look for a cache/collection whose size grows without bound in logs (e.g. "holds N entries (no eviction policy)").
2. Correlate the leak's introduction with a recent deploy that added caching or buffering.
3. Confirm `gc_pct` rising toward 1.0 and Full GC reclaiming little memory before OOM.
4. Capture a heap dump on OOM (`-XX:+HeapDumpOnOutOfMemoryError`) for the fix-forward analysis.

## Remediation
- **Immediate (mitigate):** Restart affected pods to restore service, and/or roll back the deploy that introduced the unbounded cache.
- **Short term:** Add a bounded cache with an eviction policy (LRU + max size + TTL).
- **Fix forward:** Set an explicit max-entries/size on the cache; add a memory-usage alert at 80% heap.

## Severity guidance
Repeated OOMKilled restarts causing failed transactions on a payment path is **SEV-1**. A single restart with auto-recovery and no customer impact is **SEV-3**.
