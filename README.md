# 🛡️ TrialGuard AI — Clinical Trial Risk Monitor & Protocol Deviation Detector

> Real-time compliance monitoring for clinical trials with 200+ sites and 5,000+ patient visits.

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | TEAM PHOTON |
| **Track** | AI |
| **Team Lead** | Team Lead — lead@team.com |
| **Members** | Member 1, Member 2, Member 3, Member 4 |

---

## 🎯 Problem Statement

> Clinical trials run across 200+ hospitals simultaneously, enrolling thousands of patients governed by a master protocol. Protocol deviations — missed visits, wrong dosing, banned co-medications — go undetected until the FDA audit, when it's too late to fix. A single rejected submission delays drug approval by 6–12 months and costs $50–100M.

Risk managers today rely on periodic manual sampling with no real-time, cross-site view of deviation patterns. They have no standardized way to tell whether a deviation is a minor paperwork slip or a genuine safety issue, and no way to distinguish a site that made one mistake from one that's systemically failing.

---

## 💡 Solution

> TrialGuard AI is a Bob-integrated MCP server that continuously compares patient records against the trial protocol, classifies deviations by ICH E6 severity, scores site-level risk using leading indicators, and generates CAPA-ready regulatory reports — all through deterministic, auditable rules.

The system exposes 5 MCP tools that IBM Bob can call conversationally: deviation detection, severity classification, site risk scoring, CAPA report generation, and trial summary. Every finding traces back to an exact protocol rule and patient record — no black-box AI decisions.

---

## ✨ Key Features

- **Real-Time Deviation Detection:** Rule-based engine compares every patient visit against protocol specification (visit timing, dosing, co-medications, assessments)
- **ICH E6(R2) GCP Severity Classification:** Automatic Major/Minor/Administrative classification with codified regulatory thresholds
- **Composite Site Risk Scoring:** 0-100 risk score per site using severity weighting, trend detection, repetition analysis, and recency bias
- **CAPA Report Generation:** Regulatory-standard Corrective & Preventive Action reports with root cause analysis and recommended mitigations
- **IBM Bob MCP Integration:** 5 tools, 2 resources, 2 prompts — Bob can investigate sites, detect deviations, and generate reports conversationally

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, JavaScript |
| **Frameworks** | FastAPI, React 18, Vite 5 |
| **IBM Technologies** | IBM Bob (MCP Server integration) |
| **Databases** | In-memory (synthetic data generator) |
| **Other** | MCP Python SDK v2, Recharts, React Router, Uvicorn |

---

## 📁 Repository Structure

```
├── src/
│   ├── backend/
│   │   ├── core/                 # Deterministic analysis engine
│   │   │   ├── protocol.py       # Protocol specification model
│   │   │   ├── synthetic_data.py # 200+ sites, 5000+ visits generator
│   │   │   ├── deviation_detector.py  # Stage 1: Detection
│   │   │   ├── severity_classifier.py # Stage 2: ICH E6 Classification
│   │   │   ├── risk_scorer.py    # Stage 3: Site risk scoring
│   │   │   └── capa_generator.py # Stage 4: CAPA reports
│   │   ├── mcp_server.py         # MCP server for IBM Bob
│   │   ├── api.py                # FastAPI REST endpoints
│   │   └── main.py               # Backend entry point
│   ├── frontend/                 # React + Vite dashboard
│   │   └── src/components/       # UI components
│   └── bob_config.json           # Bob MCP configuration
├── docs/                         # Written documentation
├── demo/                         # Demo artifacts
├── presentation/                 # Slide deck
└── submission.yaml               # Structured submission metadata
```

---

## ⚡ How to Run

> **Full setup details: [`docs/setup-guide.md`](docs/setup-guide.md)**

```bash
# 1. Clone the repo
git clone https://github.com/HeerGhevariya/bob-ai-hackathon-TEAM-PHOTON.git
cd bob-ai-hackathon-TEAM-PHOTON

# 2. Install backend dependencies
cd src/backend
pip install -r requirements.txt

# 3. Start the backend API
python main.py
# → API running at http://localhost:8000

# 4. Install frontend dependencies (new terminal)
cd src/frontend
npm install

# 5. Start the frontend
npm run dev
# → Dashboard at http://localhost:5173

# 6. (Optional) Test Bob MCP integration
cd src/backend
python -m mcp dev mcp_server.py
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/](presentation/) |

---

## ⚠️ Known Limitations

- **Synthetic data only** — uses generated patient records (no real PHI for privacy/compliance)
- **No watsonx.ai integration** — CAPA narratives use deterministic templates (watsonx.ai was planned but not implemented due to API access constraints)
- **Not deployed** — dashboard runs locally only
- **Risk scoring thresholds are illustrative** — would need calibration with real trial data before production use
- **Single-protocol demo** — demonstrates with one trial (PHOENIX-301); production would support multiple protocols

---

## 🏅 What We're Most Proud Of

**The deterministic, auditable analysis engine.** In clinical trials, "the AI said so" is not an acceptable answer to an FDA auditor. Every deviation TrialGuard detects traces back to an exact protocol rule, an exact patient record, and an exact threshold. The AI (via Bob MCP) is used only to present findings conversationally and help risk managers investigate — it never decides what counts as a deviation, how severe it is, or what the risk score should be. This design choice makes the system trustworthy enough for actual regulated use, not just a demo.

---
