# Incident Commander — Architecture Description

This document is the **architecture description** deliverable for the Agentic AI
Hackathon (Track 2). It explains the design of the Incident Commander agent network,
the responsibilities of each component, the control flow, and the key design
decisions.

---

## 1. Overview

Incident Commander is a **human-in-the-loop, multi-agent incident-response system**
built entirely on the Neuro SAN framework. It ingests a production alert and drives a
fixed SRE triage *playbook* across a team of specialist LLM agents, backed by
deterministic Python *coded tools* that supply trustworthy evidence. It produces a
consolidated incident report and then **stops** — no outward action (remediation or
communication) is taken until a human explicitly approves.

The design goal is **trustworthy autonomy**: automate everything that is safe to
automate (reading logs, crunching metrics, retrieving runbooks, reasoning about cause,
drafting comms) while keeping a hard, *code-enforced* boundary at the point of action.

---

## 2. Component model

The network is defined declaratively in
[`registries/industry/incident_commander.hocon`](../../registries/industry/incident_commander.hocon)
as **7 LLM agents** plus **4 coded tools** (11 nodes total, confirmed by
`neuro_san.client.hocon_validator_cli`).

### 2.1 Orchestrator (front-man)

**`IncidentCommander`** is the single point of contact for the human. It is the AAOSA
"front man": it owns the conversation, runs the playbook, delegates to specialists,
runs the evaluation loop, and enforces the approval gate. Its instructions encode the
9-step playbook (see §3) and the strict rule that *nothing is dispatched before human
approval arrives in a separate turn*.

### 2.2 Specialist agents

| Agent | Responsibility | Reasoning vs. tools |
|-------|----------------|---------------------|
| `EvidenceCollector` | Produces an objective evidence brief | Calls two coded tools; does not diagnose |
| `RunbookExpert` | Retrieves & summarizes the applicable runbook | Calls the RAG tool |
| `RootCauseAnalyst` | Ranked root-cause hypothesis + severity | Pure reasoning over supplied evidence |
| `HypothesisVerifier` | Adversarial evaluation of the hypothesis | Pure reasoning; returns a verdict + confidence |
| `RemediationPlanner` | Mitigation / fix-forward / rollback / risk | Pure reasoning grounded in the runbook |
| `CommsDrafter` | Drafts comms; dispatches only post-approval | Calls the dispatch tool only when approved |

### 2.3 Coded tools (deterministic Python)

All four implement `neuro_san.interfaces.coded_tool.CodedTool` (`async_invoke`). They
live in `coded_tools/industry/incident_commander/` and are resolved by neuro-san via
`module.Class` under `AGENT_TOOL_PATH=coded_tools/`.

| Tool | Class | What it does |
|------|-------|--------------|
| `IncidentLogReader` | `incident_log_reader.IncidentLogReader` | Parses a service log into level counts, **collapsed error signatures** (volatile tokens masked so identical error classes group), first-error time, versions seen, and **deploy correlation** (was there a deploy just before the first error?). |
| `MetricsAnalyzer` | `metrics_analyzer.MetricsAnalyzer` | Loads the metric time-series and flags **anomalies** per metric (baseline → peak, threshold breach, breach-onset timestamp) and computes the overall **incident onset**. |
| `RunbookRetriever` | `runbook_retriever.RunbookRetriever` | **Offline TF-IDF RAG** over the markdown runbook KB (no external vector store) — returns the best-matching runbook(s) with content and matched terms. |
| `CommsDispatcher` | `comms_dispatcher.CommsDispatcher` | The **action gate**: refuses to send unless `approved=true`; on approval writes to an auditable outbox (JSONL) and optionally posts to Slack (`SLACK_WEBHOOK_URL`). |

**Why coded tools for evidence?** LLMs are unreliable at counting log lines or reading
time-series precisely and may hallucinate. By computing evidence in Python and feeding
*facts* to the agents, root-cause reasoning is grounded and reproducible.

---

## 3. Control flow (the playbook)

```
                   ┌──────────────────────────────────────────────┐
   alert  ───────► │ IncidentCommander (front-man)                │
                   └──────────────────────────────────────────────┘
   (1) SCOPE service
   (2) EvidenceCollector ─► IncidentLogReader + MetricsAnalyzer ─► evidence brief
   (3) RunbookExpert     ─► RunbookRetriever (RAG)              ─► procedure
   (4) RootCauseAnalyst  ─► hypothesis + severity
   (5) HypothesisVerifier ─► VERIFIED | NEEDS_REVISION (+confidence)
         └── if NEEDS_REVISION ──► back to (4) with critique   (≤ 2 rounds)   ◄── EVALUATION LOOP
   (6) RemediationPlanner ─► mitigation / fix-forward / rollback+verify / risk
   (7) CommsDrafter (DRAFT) ─► proposed channel + message
   (8) PRESENT consolidated report to human ─► ASK for approval  ◄── HUMAN-IN-THE-LOOP GATE
        · · · · · · · · · · · (turn boundary — commander waits) · · · · · · · · · · ·
   (9) on "approve": CommsDrafter (DISPATCH) ─► CommsDispatcher(approved=true) ─► confirmation
```

### 3.1 The evaluation loop (steps 4–5)

`RootCauseAnalyst` proposes; `HypothesisVerifier` is prompted to **try to disprove**
it — checking timeline consistency (does the claimed cause precede the first symptom?),
attribution (is the fault actually in *this* service?), and mechanism (does the
evidence support causation, not just correlation?). A weak or contradicted hypothesis
returns `NEEDS_REVISION`, and the commander re-runs the analyst *with the critique
attached*, up to two revisions. This is the "evaluation loop" the rubric asks for, and
it is what stops the classic failure mode of confidently blaming the wrong thing.

### 3.2 The human-in-the-loop gate (steps 8–9)

The gate is enforced in **two independent layers** (defense in depth):

1. **Prompt layer** — the commander is instructed never to dispatch before approval and
   to pause the conversation asking a yes/no question.
2. **Code layer** — `CommsDispatcher` returns `BLOCKED_AWAITING_APPROVAL` and sends
   nothing unless it receives `approved=true`. Even if the LLM tried to jump the gun,
   the tool refuses.

---

## 4. State management (`sly_data`)

`sly_data` carries incident state between tools without polluting the chat/LLM context:
`incident_service` is set by the evidence tools and reused by later tools; dispatched
communications are appended to `comms_sent`. This mirrors the framework's intended use
of `sly_data` for out-of-band state.

---

## 5. LLM configuration

The network `include`s `config/llm_config.hocon`, which resolves to the developer
fallback chain **OpenAI → Anthropic → Gemini**. Providers without an available API key
are automatically culled, so setting only `GEMINI_API_KEY` runs the whole network on
Gemini's free tier. No model names are hard-coded in the network, so it is provider-
portable.

---

## 6. Design decisions & trade-offs

- **Directed orchestration over broadcast AAOSA.** The commander calls specialists in a
  deliberate playbook order rather than broadcasting an AAOSA `Determine` to all agents.
  This keeps latency and token cost low (important on a free tier) and makes the flow
  deterministic and demo-friendly, while still being a genuine multi-agent system
  (agents calling agents as tools).
- **Deterministic evidence, generative reasoning.** Facts come from code; judgment comes
  from LLMs. This is the core reliability decision.
- **Offline RAG.** TF-IDF over local markdown avoids an external vector DB dependency so
  the demo is reproducible and self-contained; the retriever is a drop-in seam for a
  real embeddings store.
- **Synthetic data only.** Three incident scenarios with logs, metrics, deploy history,
  and runbooks — no PII or proprietary data, per hackathon rules.

---

## 7. Extension points (production path)

| Seam | Demo implementation | Production swap |
|------|--------------------|-----------------|
| Log source | local `.log` files | Splunk / Elastic / Loki query |
| Metrics source | local JSON series | Datadog / Prometheus API |
| Runbook KB | markdown + TF-IDF | Confluence RAG (already in this repo) + embeddings |
| Action dispatch | outbox JSONL | Slack / PagerDuty / status-page APIs (toolbox) |
| Remediation | recommendation only | gated `kubectl rollout undo` via a coded tool |

Because each backend is isolated behind a coded tool, moving from demo to production is
a matter of swapping tool implementations — the agent network and playbook are unchanged.
