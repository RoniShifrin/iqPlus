# IQ PLUS — Running Guide

---

## Prerequisites

Before first run, install all dependencies:

```powershell
cd BACK
venv\Scripts\python -m pip install -r requirements.txt
venv\Scripts\python -m pip install -r requirements-dev.txt

# bcrypt MUST be <4.0.0 — newer versions break passlib
venv\Scripts\python -m pip install "bcrypt<4.0.0"

# Verify
venv\Scripts\python -m pip show bcrypt   # should show Version: 3.x.x
```

---

## 1. Start the Backend

```powershell
cd BACK
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> Keep this terminal open. API runs at: http://localhost:8000
>
> Alternative (no activation needed):
> `venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

---

## 2. Start the Frontend

Open a **new terminal**:

```powershell
cd FRONT
npm install
npm run dev
```

> App runs at: http://localhost:5173

**Important:** `FRONT\.env.local` must contain:
```
VITE_API_URL=http://127.0.0.1:8000
```
If the file is missing or has the wrong port, login will show "Failed to fetch".
After editing `.env.local`, restart Vite (Ctrl+C → `npm run dev`).

---

## 3. Seed Demo Data

Open a **new terminal** (backend must already be running):

**Large demo** — 3 admins · 10 teachers · 60 students · 40 parents · 22 courses · 14 weeks:
```powershell
cd BACK
venv\Scripts\python scripts/seed_large_demo.py
```

**Small demo** — 1 admin · 5 teachers · 15 students · 8 courses · 10 weeks:
```powershell
venv\Scripts\python scripts/seed_demo_data.py
```

**Planner demo** — 1 teacher · 1 student · 1 parent · 6 courses designed to showcase the Academic Planner AI Analyze feature (conflict, balanced, and heavy-workload scenarios):
```powershell
venv\Scripts\python scripts/seed_planner_demo.py
```

All three demos can coexist — they use separate email domains and share the `_demo_registry` collection for cleanup.

---

## 4. Open the App

| What               | URL                                         |
|--------------------|---------------------------------------------|
| App                | http://localhost:5173 (or 5174 if 5173 is in use) |
| API docs (Swagger) | http://localhost:8000/docs                  |
| Demo status (API)  | http://localhost:8000/api/admin/demo/status |

> Vite automatically picks the next available port if 5173 is taken. Check the terminal output for the actual URL.

---

## 5. Login Credentials

Login uses **email + password**.

### Large demo (`@large.iqplus.dev`)

| Role                | Email                               | Password    |
|---------------------|-------------------------------------|-------------|
| Admin               | `admin.demo@large.iqplus.dev`       | `Admin123!` |
| Coordinator         | `coord.academic@large.iqplus.dev`   | `Admin123!` |
| Teacher (Math)      | `teacher.math@large.iqplus.dev`     | `Teacher123!` |
| Teacher (CS)        | `yoav.ben@large.iqplus.dev`         | `Teacher123!` |
| Student (excellent) | `student.star@large.iqplus.dev`     | `Student123!` |
| Student (at-risk)   | `jay.ross@large.iqplus.dev`         | `Student123!` |
| Student (improving) | `carlos.diaz@large.iqplus.dev`      | `Student123!` |
| Parent              | `parent.one@large.iqplus.dev`       | `Parent123!` |

### Small demo (`@demo.iqplus.dev`)

| Role    | Email                          | Password      |
|---------|--------------------------------|---------------|
| Admin   | `admin@demo.iqplus.dev`        | `Admin123!`   |
| Teacher | `david.cohen@demo.iqplus.dev`  | `Teacher123!` |
| Student | `s.weiss@demo.iqplus.dev`      | `Student123!` |
| Parent  | `p.weiss@demo.iqplus.dev`      | `Parent123!`  |

### Planner demo (`@planner.iqplus.dev`)

Designed to showcase the Academic Planner. All accounts use password `Planner123!`.

| Role    | Email                                     |
|---------|-------------------------------------------|
| Teacher | `planner.teacher@planner.iqplus.dev`      |
| Student | `planner.student@planner.iqplus.dev`      |
| Parent  | `planner.parent@planner.iqplus.dev`       |

**Planner scenario quick-reference** (log in as Student, go to Academic Planner):

| Scenario | Courses to select | Expected result |
|----------|-------------------|-----------------|
| Conflict | PLAN101 + PLAN102 | Overlap detected Mon & Wed 10:00–11:00 |
| Balanced | PLAN103 + PLAN104 | Light workload, zero conflicts |
| Heavy load | PLAN101 + PLAN103 + PLAN104 + PLAN105 + PLAN106 | 17.5 h/week, density warnings |

---

## 6. Clear Demo Data

```powershell
# Clear large demo only
venv\Scripts\python scripts/clear_large_demo.py

# Clear small demo only
venv\Scripts\python scripts/clear_demo_data.py

# Clear planner demo only
venv\Scripts\python scripts/seed_planner_demo.py --clear
```

> Only demo-tagged documents are deleted. Real data is never touched.

---

## 7. Reseed Demo Data

```powershell
# Wipe and regenerate large demo
venv\Scripts\python scripts/reseed_demo.py large

# Wipe and regenerate small demo
venv\Scripts\python scripts/reseed_demo.py small

# Wipe and regenerate both
venv\Scripts\python scripts/reseed_demo.py all

# Wipe and regenerate planner demo
venv\Scripts\python scripts/seed_planner_demo.py --reseed
```

---

## 8. Admin Demo Controls (API)

When logged in as admin, you can also manage demo data via the API:

```
GET  /api/admin/demo/status               — see what is seeded
POST /api/admin/demo/clear?dataset=large  — clear large demo
POST /api/admin/demo/clear?dataset=small  — clear small demo
POST /api/admin/demo/clear?dataset=all    — clear both
```

> Seeding must be done via CLI — it is too slow for an HTTP request.

---

## Demo Data — Safety Model

All seeded documents are tracked by ID in MongoDB registry collections:
- `_demo_registry` — small demo
- `_large_demo_registry` — large demo

Clearing reads the registry and deletes only those exact IDs. No filters on real data.

---

## Troubleshooting

### bcrypt error on seed ("password cannot be longer than 72 bytes")
bcrypt 4.x/5.x is incompatible with passlib 1.7.4. Downgrade:
```powershell
venv\Scripts\python -m pip install "bcrypt<4.0.0"
```

### "Failed to fetch" on login
The frontend API URL is wrong. Fix `FRONT\.env.local`:
```
VITE_API_URL=http://127.0.0.1:8000
```
Then restart Vite.

### Seed fails with DuplicateKeyError
A previous seed run failed partway and left orphaned data. The clear script won't find it (registry was never written). Fix:
```powershell
# 1. Clear via clear script first
venv\Scripts\python scripts/clear_large_demo.py

# 2. If it reports "No demo data found", manually wipe orphaned data:
venv\Scripts\python -c "
import asyncio, os, certifi
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('..') / '.env')
from motor.motor_asyncio import AsyncIOMotorClient
async def main():
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'), tlsCAFile=certifi.where())
    db = client[os.getenv('DB_NAME', 'iqplus_db')]
    for col in await db.list_collection_names():
        r = await db[col].delete_many({})
        if r.deleted_count: print(f'  {col}: {r.deleted_count} deleted')
    client.close()
asyncio.run(main())
"

# 3. Then seed again
venv\Scripts\python scripts/seed_large_demo.py
```

### AI alerts show "rule-based" instead of Claude-generated text
`ANTHROPIC_API_KEY` is not set. The system works fully without it — AI alerts fall back to
rule-based analysis. To enable Claude AI analysis, add to `BACK/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### Planner returns 404 / routes missing
The backend process is a stale instance from a previous session that predates the planner routes.
Kill it and restart:
```powershell
# Find the PID on port 8000 and kill it
python -c "
import subprocess
r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
pids = {l.split()[-1] for l in r.stdout.splitlines() if ':8000 ' in l and 'LISTENING' in l}
for pid in pids:
    subprocess.run(['taskkill', '/PID', pid, '/F', '/T'])
    print('Killed', pid)
"

# Then restart the backend normally
venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### MongoDB SSL error (TLSV1_ALERT_INTERNAL_ERROR)
Something on your network is intercepting TLS traffic on port 27017.
- Try switching to a **mobile hotspot** to confirm it is network-related
- Disable **antivirus SSL/HTTPS scanning** (Windows Defender, Avast, etc.)
- Disconnect **VPN** if active
- Check router **Intrusion Prevention / DPI** settings

Note: TCP connects fine — the issue is TLS interception, not a firewall block.
