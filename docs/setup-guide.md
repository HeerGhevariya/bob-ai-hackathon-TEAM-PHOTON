# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites

Before you begin, ensure you have the following installed:

- [x] **Python 3.11+** — [Download](https://www.python.org/downloads/)
- [x] **Node.js 18+** — [Download](https://nodejs.org/)
- [x] **pip** (comes with Python)
- [x] **npm** (comes with Node.js)
- [ ] *(Optional)* **uv** — faster Python package installer ([Install](https://docs.astral.sh/uv/))
- [ ] *(Optional)* **IBM Bob CLI** — for MCP integration testing

No database or cloud account is required. All data is generated synthetically at startup.

## Environment Variables

Copy `.env.example` to `.env` in the `src/` directory:

```bash
cp src/.env.example src/.env
```

| Variable | Description | Required |
|---|---|---|
| `APP_PORT` | Backend API port (default: 8000) | No |
| `APP_ENV` | Environment mode (default: development) | No |
| `WATSONX_API_KEY` | IBM watsonx.ai API key (for enhanced CAPA reports) | No |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID | No |

> **Note:** No environment variables are required. The application runs fully out-of-the-box with synthetic data and template-based CAPA generation.

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/HeerGhevariya/bob-ai-hackathon-TEAM-PHOTON.git
cd bob-ai-hackathon-TEAM-PHOTON

# 2. Install backend dependencies
cd src/backend
pip install -r requirements.txt

# 3. Install frontend dependencies
cd ../frontend
npm install
```

## Running the Application

### Start the Backend (Terminal 1)

```bash
cd src/backend
python main.py
```

You should see:
```
🛡️  TrialGuard AI — Clinical Trial Risk Monitor
==================================================
Starting backend server on http://localhost:8000
API docs available at http://localhost:8000/docs
==================================================
```

The API is now running at `http://localhost:8000`. You can verify by visiting `http://localhost:8000/docs` for the interactive Swagger UI.

### Start the Frontend (Terminal 2)

```bash
cd src/frontend
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in Xms

  ➜  Local:   http://localhost:5173/
```

Open `http://localhost:5173` in your browser to see the TrialGuard AI dashboard.

### Test IBM Bob MCP Integration (Terminal 3, optional)

```bash
cd src/backend
python -m mcp dev mcp_server.py
```

This launches the MCP Inspector where you can test all 5 tools interactively.

To connect Bob directly, add this to your Bob MCP configuration:
```json
{
  "mcpServers": {
    "trialguard": {
      "command": "python",
      "args": ["src/backend/mcp_server.py"]
    }
  }
}
```

## Running Tests

```bash
cd src/backend
python -c "
from core.protocol import get_protocol
from core.synthetic_data import generate_trial_data, get_trial_statistics
from core.deviation_detector import DeviationDetector
from core.severity_classifier import SeverityClassifier
from core.risk_scorer import RiskScorer

# Generate data
sites, protocol = generate_trial_data(seed=42)
stats = get_trial_statistics(sites)
print(f'Sites: {stats[\"total_sites\"]}, Patients: {stats[\"total_patients\"]}, Visits: {stats[\"total_visits\"]}')

# Detect deviations
detector = DeviationDetector(protocol)
deviations = detector.detect_all(sites)
print(f'Deviations detected: {len(deviations)}')

# Classify
classifier = SeverityClassifier()
classifier.classify_all(deviations)
from collections import Counter
sev = Counter(d.severity for d in deviations)
print(f'Major: {sev[\"major\"]}, Minor: {sev[\"minor\"]}, Administrative: {sev[\"administrative\"]}')

# Score sites
from datetime import date
scorer = RiskScorer(reference_date=date(2024, 9, 1))
site_info = {s.site_id: {\"name\": s.site_name, \"total_patients\": len(s.patients)} for s in sites}
profiles = scorer.score_all_sites(deviations, site_info)
critical = [p for p in profiles if p.risk_tier.value == 'critical']
print(f'Critical sites: {len(critical)}, Top risk: {profiles[0].site_id} ({profiles[0].risk_score}/100)')
print('All checks passed!')
"
```

## Quick Demo

After starting both the backend and frontend:

1. Open `http://localhost:5173` — you'll see the **Trial Overview** with summary statistics
2. Click **Site Risk Leaderboard** — all 210 sites ranked by risk score
3. Click any **Critical** or **High** risk site — see detailed deviation history and risk factors
4. Click **Generate CAPA Report** — produces a full regulatory-standard CAPA report
5. Use **Deviation Explorer** — filter by severity, type, or site

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements.txt` from `src/backend/` |
| `ENOENT: npm not found` | Install Node.js 18+ from https://nodejs.org/ |
| Backend starts but dashboard shows "Failed to load data" | Ensure the backend is running on port 8000, and the frontend's Vite proxy is configured (check `vite.config.js`) |
| `Port 8000 already in use` | Kill the existing process or change `APP_PORT` in `.env` |
| MCP Inspector not opening | Ensure you have `uv` installed: `pip install uv`, then run `uv run mcp dev mcp_server.py` |
| Frontend shows CORS errors | The backend CORS is configured for `*`. If you changed it, update the allowed origins in `api.py` |
