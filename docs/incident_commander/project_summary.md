# Incident Commander — Project Summary

**Agentic AI Hackathon (Track 2) · Built on Cognizant Neuro SAN Studio**
**Theme:** Human-in-the-loop AI that increases productivity while maintaining trust · Replace a manual business process with an agentic workflow.

---

## Problem

Production incidents are expensive and stressful. When an alert fires, a single on-call
engineer must simultaneously read logs, scan dashboards, recall the right runbook,
determine *what changed*, decide whether to roll back, and write a safe status update —
under time pressure, with revenue on the line. This manual scramble dominates
**mean-time-to-resolution (MTTR)**, and haste causes secondary mistakes (rolling back
the wrong service, leaking internal details in comms). Existing "AIOps" tools either
stop at alerting or act autonomously in ways teams don't trust.

## Solution

**Incident Commander** is a multi-agent system that performs the entire triage workflow
in seconds and hands the engineer a single, evidence-backed decision to approve. It
automates everything that is safe to automate while keeping a hard, code-enforced human
gate at the point of any real action.

Given an alert, a front-man **IncidentCommander** agent orchestrates a specialist team:

1. **EvidenceCollector** parses logs and analyzes metric time-series (via Python tools).
2. **RunbookExpert** retrieves the matching procedure from a runbook knowledge base (RAG).
3. **RootCauseAnalyst** proposes a ranked root-cause hypothesis and severity.
4. **HypothesisVerifier** adversarially checks it — an **evaluation loop** that sends weak
   or contradicted hypotheses back for revision (up to two rounds).
5. **RemediationPlanner** produces mitigation, fix-forward, rollback + verification, and risk.
6. **CommsDrafter** drafts a severity-appropriate status message.
7. The commander presents one consolidated report and **pauses for human approval**;
   only on approval does it dispatch communications.

## Why it's novel

- **Self-checking diagnosis.** The `HypothesisVerifier` is prompted to *disprove* the
  root cause, catching the common failure of confidently blaming the wrong thing (e.g.
  "just roll it back" when the fault is actually upstream).
- **Trust by construction.** The human-in-the-loop gate is enforced in two layers —
  the prompt *and* the `CommsDispatcher` code, which refuses to act without
  `approved=true`. Autonomy stops exactly where risk begins.
- **Grounded, not hallucinated.** Deterministic Python tools compute the evidence
  (log signatures, anomaly onset, deploy correlation); the LLMs only reason over facts.

## Neuro SAN usage

- Idiomatic declarative **HOCON agent network** (7 LLM agents + 4 coded tools) with
  multi-agent delegation and a shared instruction prefix.
- Four **`CodedTool`** implementations (log parsing, anomaly detection, offline TF-IDF
  RAG, approval-gated dispatch).
- **`sly_data`** for out-of-band incident state between tools.
- Provider-portable via the `config/llm_config.hocon` fallback chain (runs on Gemini's
  free tier); validated with neuro-san's own `hocon_validator_cli`.

## Demonstrated capabilities (per the rubric)

| Required capability | Where it shows up |
|---------------------|-------------------|
| Multi-agent coordination | 7 agents orchestrated by the front-man |
| Tool usage | 4 Python coded tools + offline RAG |
| Task planning | The 9-step incident playbook |
| Evaluation loops | RootCauseAnalyst ↔ HypothesisVerifier revision loop |
| (Theme) Human-in-the-loop | Two-layer, code-enforced approval gate |

## Impact & scalability

The system drops into any team that has logs, metrics, and runbooks. Every external
dependency is isolated behind a coded tool, so moving from the synthetic demo to
production is a matter of swapping tool backends — local files → Splunk/Datadog,
markdown RAG → Confluence + embeddings, outbox → Slack/PagerDuty/status-page APIs — with
**no change to the agent network**. Faster, more consistent triage lowers MTTR and
reduces on-call cognitive load, while the approval gate preserves the human accountability
that regulated enterprises require.

## Demo

Three synthetic scenarios ship with the project: a deploy-induced DB connection-pool
exhaustion (→ rollback), a memory-leak OOM loop (→ restart + cache fix), and an upstream
dependency outage (→ escalate, *not* rollback — the case where the evaluation loop
overturns the obvious-but-wrong answer). One command (`python -m neuro_san_studio run`)
launches the network in the nsflow UI.

## Compliance

All data is synthetic; no PII, financial, medical, or proprietary datasets are used.
Built solely on the Apache-2.0 Neuro SAN framework.

---

*Team contact: darshan.v@cognizant.com*
