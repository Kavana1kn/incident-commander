# Incident Commander — Demo Script & Video Plan

A tight, reproducible walkthrough for the live demo / recorded video (target: **3–4
minutes**). It showcases the four rubric capabilities (multi-agent coordination, tools,
planning, evaluation loop) plus the human-in-the-loop gate.

---

## 0. Setup (before recording)

```bash
# from repo root, with GEMINI_API_KEY set in .env
python -m neuro_san_studio run
```
Open <http://localhost:4173/>, select **IncidentCommander** in the agent list.
Have `data/incident_commander/outbox/sent_comms.jsonl` open in a second pane (it will
be created on the first approved dispatch) to show the auditable action.

> Tip: keep the nsflow graph view visible — as the run proceeds you can see the
> commander light up each specialist and coded tool, which makes the multi-agent
> orchestration tangible on camera.

---

## Scene 1 — The "happy path": deploy-induced outage (≈90s)

**Paste:**
> `PagerDuty SEV alert: checkout-service p99 latency 5s and error rate ~30% since 14:32. Investigate and recommend action.`

**Narrate while it runs** that the commander is delegating: EvidenceCollector →
(IncidentLogReader + MetricsAnalyzer), RunbookExpert → RunbookRetriever, then diagnosis
and verification.

**Point out in the output:**
- The **evidence** cites concrete facts: first error `14:33:10Z`, error_rate `0.002 → 0.71`,
  `db_pool_active` pinned at `10/10`, and the **deploy correlation**: `v2.3.1` at
  `14:30` (which lowered the pool size) *precedes* the first error.
- The **root cause**: connection-pool exhaustion caused by the `v2.3.1` deploy (N+1
  query + reduced pool), **SEV-1**.
- The **verifier** returns `VERIFIED` with high confidence (timeline is consistent).
- The **remediation**: immediate **rollback** of `v2.3.1`, fix-forward = remove the N+1
  query, verification = `db_pool_active` and `error_rate` return to baseline within 5 min.
- The commander **stops and asks for approval** — nothing has been sent yet.

---

## Scene 2 — The money shot: the evaluation loop overturns the obvious answer (≈90s)

**Paste (new session or continue):**
> `search-service is serving degraded results and the catalog-api circuit breaker is open. Roll it back.`

Note the user *suggests* a rollback — the tempting, wrong action.

**Point out:**
- Evidence shows **no deploy** to search-service in 24h and a **high upstream error
  rate** to `catalog-api`, with the circuit breaker doing its job (degraded results).
- If the analyst initially leans toward "roll back," the **HypothesisVerifier** returns
  `NEEDS_REVISION`: *you can't roll back your way out of an upstream fault; no local
  change preceded the symptoms.* The commander re-runs the analyst with that critique.
- Final recommendation: **escalate to the catalog-api owning team**, keep serving
  degraded results — explicitly **do not roll back**. Severity SEV-3 for this service.

This is the headline: **the system caught a plausible-but-wrong action** because of the
evaluation loop. Great soundbite for judges.

---

## Scene 3 — Human-in-the-loop approval & auditable action (≈45s)

Back in Scene 1's session, **type:**
> `approve`

**Point out:**
- Only now does `CommsDrafter` call `CommsDispatcher(approved=true)`.
- Show the new line appended to `data/incident_commander/outbox/sent_comms.jsonl` — the
  timestamped, approved communication.
- Mention the **code-level gate**: if you had replied "no", or if the LLM had tried to
  send earlier, `CommsDispatcher` returns `BLOCKED_AWAITING_APPROVAL` and sends nothing.

---

## Scene 4 — (optional, 20s) The third scenario

**Paste:**
> `payments-service pods keep getting OOMKilled and restarting today. What's going on and what do we do?`

Shows the system generalizing: unbounded `fx-rates` cache → memory leak → recommend
**restart + add cache eviction** (not rollback; the leak predates any single deploy).

---

## Closing line (15s)

> "Incident Commander turns a 3 a.m. scramble into one reviewed decision: it gathers the
> evidence, checks its own reasoning, and asks before it ever acts. Every backend —
> logs, metrics, runbooks, comms — is a swappable Neuro SAN coded tool, so this runs on
> your real stack tomorrow."

---

## What to capture for the video

1. The nsflow graph animating as agents/tools fire (multi-agent + tools).
2. The consolidated incident report with cited evidence (grounding).
3. The verifier flipping a wrong hypothesis in Scene 2 (evaluation loop).
4. The approval prompt → `approve` → outbox line (human-in-the-loop + auditable action).

## Fallback if live LLM latency is high

Record each scene separately and stitch, or use `python -m neuro_san_studio chat
industry/incident_commander` for a faster text-only capture. The coded-tool evidence is
deterministic, so the factual parts are identical every run.
