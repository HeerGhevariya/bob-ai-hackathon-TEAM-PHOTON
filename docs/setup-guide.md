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
- [ ] *(Optional)* **Supabase account** — for persistent database mode ([Sign up free](https://supabase.com/))

No database or cloud account is required for the default mode. All data is generated synthetically at startup.

## Environment Variables

Copy `.env.example` to `.env` in the `src/` directory:

```bash
cp src/.env.example src/.env
```

| Variable | Description | Required |
|---|---|---|
| `APP_PORT` | Backend API port (default: 8080) | No |
| `APP_ENV` | Environment mode (default: development) | No |
| `SUPABASE_URL` | Your Supabase project URL | No (enables persistent mode) |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | No (required if SUPABASE_URL is set) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | No (required for seed script only) |
| `WATSONX_API_KEY` | IBM watsonx.ai API key (for enhanced CAPA reports) | No |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID | No |

> **Note:** No environment variables are required for the default mode. The application runs fully out-of-the-box with in-memory synthetic data (MockDataSource).

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

### Option A: Default Mode (In-Memory, Zero Config)

No database or `.env` setup needed. Data is generated synthetically.

#### Start the Backend (Terminal 1)

```bash
cd src/backend
python main.py
```

You should see:
```
🛡️  TrialGuard AI — Clinical Trial Risk Monitor
==================================================
Starting backend server on http://localhost:8080
📊 Initializing MockDataSource (in-memory synthetic data)...
   ✅ Loaded 210 sites, 631 patients, 5241 visits, XXX deviations
==================================================
```

#### Start the Frontend (Terminal 2)

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

---

### Option B: Supabase Mode (Persistent Database)

#### Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com/) and create a free project
2. Copy your project URL and keys from **Settings → API**

#### Step 2: Configure Environment Variables

```bash
cp src/.env.example src/.env
```

Edit `src/.env` and fill in:
```
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

#### Step 3: Create Database Tables

Open the **Supabase SQL Editor** and run the contents of:
```
src/backend/db/schema.sql
```

This creates 6 tables: `sites`, `patients`, `patient_visits`, `deviations`, `site_risk_profiles`, `capa_reports` — with indexes and RLS policies.

#### Step 4: Seed the Database

```bash
cd src/backend
python db/seed.py
```

You should see:
```
🌱 TrialGuard AI — Supabase Seed Script
==================================================
✅ Connected to Supabase: https://your-project...
📊 Generating synthetic trial data...
🔍 Running deviation detection pipeline...
📈 Running risk scoring pipeline...
📥 Inserting sites... ✅ 210 sites
📥 Inserting patients... ✅ 631 patients
📥 Inserting patient visits... ✅ 5241 visits
📥 Inserting deviations... ✅ XXX deviations
📥 Inserting risk profiles... ✅ 210 risk profiles
🎉 Seed complete!
```

#### Step 5: Run the App

```bash
# Terminal 1
cd src/backend
python main.py
# → Should show: 🗄️  Initializing SupabaseDataSource (Supabase PostgreSQL)...

# Terminal 2
cd src/frontend
npm run dev
```

---

### Test IBM Bob MCP Integration (Optional, Terminal 3)

```bash
cd src/backend
python -m mcp dev mcp_server.py
```

This launches the MCP Inspector where you can test all 5 tools interactively.

To connect Bob directly, use the config in `src/bob_config.json`:
```json
{
  "mcpServers": {
    "trialguard": {
      "command": "python",
      "args": ["backend/mcp_server.py"]
    }
  }
}
```

> **Note:** The `bob_config.json` assumes Bob is started from the `src/` directory. If running from the repository root, change the path to `src/backend/mcp_server.py`.

## Running Tests

```bash
cd src/backend
python -c "
from core.data_source import get_data_source

# Initialize data source (Mock or Supabase depending on .env)
ds = get_data_source()
print(f'DataSource: {type(ds).__name__}')

# Check protocol
protocol = ds.get_protocol()
print(f'Protocol: {protocol.protocol_id} — {protocol.protocol_title}')

# Check data
sites = ds.get_sites()
devs = ds.get_all_deviations()
profiles = ds.get_risk_profiles()
from collections import Counter
sev = Counter(d.severity for d in devs)

print(f'Sites: {len(sites)}')
print(f'Deviations: {len(devs)} (Major: {sev[\"major\"]}, Minor: {sev[\"minor\"]}, Admin: {sev[\"administrative\"]})')
print(f'Critical sites: {sum(1 for p in profiles if p.risk_tier.value == \"critical\")}')
print(f'Top risk: {profiles[0].site_id} ({profiles[0].risk_score}/100)')

# Test FHIR export
from core.fhir_adapter import site_to_fhir_bundle
bundle = site_to_fhir_bundle(sites[0], ds.get_deviations_for_site(sites[0].site_id))
print(f'FHIR Bundle: {bundle[\"total\"]} entries for {sites[0].site_id}')

print('\\nAll checks passed! ✅')
"
```

## Quick Demo

After starting both the backend and frontend:

1. Open `http://localhost:5173` — you'll see the **Trial Overview** with summary statistics
2. Click **Site Risk Leaderboard** — all 210 sites ranked by risk score
3. Click any **Critical** or **High** risk site — see detailed deviation history and risk factors
4. Click **Generate CAPA Report** — produces a full regulatory-standard CAPA report
5. Use **Deviation Explorer** — filter by severity, type, or site
6. Visit `http://localhost:8080/api/export/fhir/SITE-001` — see FHIR R4 Bundle export
7. Visit `http://localhost:8080/api/data-source` — see which DataSource is active

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements.txt` from `src/backend/` |
| `ModuleNotFoundError: No module named 'supabase'` | Run `pip install supabase` — only needed for Supabase mode |
| `ENOENT: npm not found` | Install Node.js 18+ from https://nodejs.org/ |
| Backend starts but dashboard shows "Failed to load data" | Ensure the backend is running on port 8080, and the frontend's Vite proxy is configured (check `vite.config.js`) |
| `Port 8080 already in use` | Kill the existing process or change `APP_PORT` in `.env` |
| Supabase connection fails | Check `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `src/.env` |
| Seed script fails | Ensure you ran `schema.sql` in Supabase SQL Editor first |
| MCP Inspector not opening | Ensure you have `uv` installed: `pip install uv`, then run `uv run mcp dev mcp_server.py` |
| Frontend shows CORS errors | The backend CORS is configured for `*`. If you changed it, update the allowed origins in `api.py` |
| App shows `MockDataSource` instead of Supabase | Check that `src/.env` exists and has `SUPABASE_URL` set |
