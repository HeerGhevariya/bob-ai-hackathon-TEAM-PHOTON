# Source Code — TrialGuard AI

All source code for the Clinical Trial Risk Monitor & Protocol Deviation Detector.

## Structure

```
src/
├── backend/                          # Python backend
│   ├── core/                         # Core analysis engine (deterministic, rule-based)
│   │   ├── protocol.py               # PHOENIX-301 protocol specification model
│   │   ├── synthetic_data.py         # Synthetic data generator (200+ sites, 5000+ visits)
│   │   ├── deviation_detector.py     # Stage 1: Protocol deviation detection
│   │   ├── severity_classifier.py    # Stage 2: ICH E6(R2) GCP severity classification
│   │   ├── risk_scorer.py            # Stage 3: Composite site-level risk scoring
│   │   └── capa_generator.py         # Stage 4: CAPA report generation
│   ├── mcp_server.py                 # MCP server — IBM Bob integration (5 tools, 2 resources, 2 prompts)
│   ├── api.py                        # FastAPI REST API for dashboard (7 endpoints)
│   ├── main.py                       # Backend entry point (uvicorn)
│   └── requirements.txt              # Python dependencies
├── frontend/                         # React + Vite dashboard
│   ├── index.html                    # HTML entry point
│   ├── package.json                  # Node.js dependencies
│   ├── vite.config.js                # Vite config with API proxy
│   └── src/
│       ├── main.jsx                  # React entry point
│       ├── App.jsx                   # Main app with routing
│       ├── index.css                 # Design system (dark clinical theme)
│       ├── components/               # React components
│       │   ├── Sidebar.jsx           # Navigation sidebar
│       │   ├── TrialOverview.jsx     # Dashboard home page
│       │   ├── SiteLeaderboard.jsx   # Risk-ranked site table
│       │   ├── SiteDetail.jsx        # Individual site drill-down
│       │   ├── DeviationExplorer.jsx # Filterable deviation table
│       │   ├── CapaReport.jsx        # CAPA report generator/viewer
│       │   ├── RiskBadge.jsx         # Risk tier badge component
│       │   ├── TrendArrow.jsx        # Trend direction indicator
│       │   └── SeverityChart.jsx     # Donut chart components
│       └── utils/
│           └── api.js                # API fetch utilities
├── bob_config.json                   # IBM Bob MCP server configuration
└── .env.example                      # Environment variable template
```

## Running

See the [setup guide](../docs/setup-guide.md) for full instructions.

```bash
# Backend
cd src/backend && pip install -r requirements.txt && python main.py

# Frontend (new terminal)
cd src/frontend && npm install && npm run dev
```
