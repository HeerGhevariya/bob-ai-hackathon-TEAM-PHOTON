# Solution Overview

## What We Built

TrialGuard AI is a clinical trial compliance monitoring system that **continuously watches every patient record against the protocol specification** and turns raw deviations into a prioritized, audit-ready risk picture — before the FDA ever sees it. It exposes its full analysis capability as an MCP server that IBM Bob can call conversationally.

## How It Works

The system operates in four connected stages, each building on the previous one:

1. **Stage 1 — Deviation Detection:** The engine compares every patient's actual visit record against the protocol specification. It checks visit timing (was the patient within the allowed window?), dosing accuracy (did they receive the correct amount?), co-medications (are they taking anything prohibited?), and assessment completeness (were all required tests performed?). Every mismatch is flagged immediately.

2. **Stage 2 — Severity Classification:** Every detected deviation is automatically classified using ICH E6(R2) — the international regulatory standard for Good Clinical Practice — into **Major**, **Minor**, or **Administrative**. This means findings speak the language regulators and auditors already use.

3. **Stage 3 — Site-Level Risk Scoring:** Rather than just counting deviations, the system scores each site (0–100) using composite leading indicators: severity weighting (a major counts 10× an administrative), trend direction (a site getting worse is flagged), repetition of the same deviation type (suggests systemic issues), and recency bias (recent problems are more actionable).

4. **Stage 4 — CAPA Report Generation:** For any flagged site, the system generates a complete Corrective and Preventive Action (CAPA) report: the finding, its severity, root cause analysis, corrective actions (immediate), preventive actions (long-term), timeline, and responsible parties.

## Architecture Diagram

> See [`architecture.md`](architecture.md) for the detailed diagram.

```
User (Risk Manager)
    │
    ├── IBM Bob CLI ──► MCP Server ──► Core Analysis Engine
    │                   (5 tools)      ├── Deviation Detector
    │                                  ├── Severity Classifier
    │                                  ├── Risk Scorer
    │                                  └── CAPA Generator
    │
    └── Browser ──► React Dashboard ──► FastAPI REST API
                                          └── Same Core Engine
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Deterministic rule-based engine (no AI for detection/classification)** | In regulated environments, "the AI said so" is not an acceptable audit answer. Every finding must trace to an exact rule and exact patient record. The AI (via Bob) only presents findings — it never decides what counts as a deviation. |
| **Composite risk scoring with leading indicators** | Simple deviation counts penalize large sites unfairly. Our scoring normalizes by patient count, weights by severity, detects trends, and penalizes repetition — predicting future problems, not just tallying past ones. |
| **ICH E6(R2) severity classification** | Using the actual international regulatory standard ensures findings speak the language auditors already use, rather than ad-hoc internal labels. |
| **MCP Server architecture for Bob integration** | MCP is the standard protocol for LLM tool integration. Exposing the engine as MCP tools means Bob can call deviation detection, risk scoring, and CAPA generation as naturally as calling any other tool. |
| **Synthetic data with seeded randomness** | Reproducible demo without any privacy concerns. Problem sites are deliberately injected to create realistic risk differentiation. |
| **Template-based CAPA generation** | Reliable, predictable output format that matches regulatory expectations. No hallucination risk. |

## IBM Technologies Used

- **IBM Bob (MCP Server):** Bob is the primary user interface for risk managers. The TrialGuard MCP server exposes 5 tools (`detect_deviations`, `classify_deviation`, `score_site_risk`, `generate_capa_report`, `get_trial_summary`), 2 resources (`trial://protocol`, `trial://sites/{site_id}`), and 2 prompts (`risk_briefing`, `site_investigation`). Bob can conduct full site investigations, generate CAPA reports, and provide daily risk briefings — all through natural conversation.
