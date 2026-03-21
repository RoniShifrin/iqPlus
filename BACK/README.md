# IQ PLUS - Backend

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env — set MONGODB_URL with your Atlas password

# Seed database (creates admin@iqplus.com account)
python ../INFRA/scripts/seed_database.py

# Start development server (venv must be active)
venv\Scripts\activate          # Windows — activates the venv
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Alternative without activating (Windows):
# venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Default Admin Account

After running the seed script:

```
Email:    admin@iqplus.com
Password: Admin123!
Role:     Admin (Full System Access)
```

**IMPORTANT:** Change this password immediately after first login!

## API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database

- **MongoDB Atlas** — cloud-hosted NoSQL database
- Cluster: your MongoDB Atlas cluster (set via `MONGODB_URL` in `.env`)
- ODM: Beanie (async, built on Motor)
- Collections created automatically on app startup

## Environment Variables

See `.env.example` for all required configuration.

Key variables:
- `MONGODB_URL`: MongoDB Atlas connection string
- `DB_NAME`: Database name (default: `iqplus_db`)
- `FIREBASE_PROJECT_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL`: Firebase credentials
- `SMTP_*`: SMTP server configuration for email notifications

## Demo Data

Two independent demo datasets are available, each using a separate domain and registry collection so they can coexist safely.

### Small demo (`@demo.iqplus.dev`)
1 admin · 5 teachers · 15 students · 15 parents · 8 courses · 10 weeks of history

```bash
python scripts/seed_demo_data.py           # seed
python scripts/seed_demo_data.py --reseed  # wipe and regenerate
python scripts/seed_demo_data.py --clear   # wipe only
```

Fixed accounts:

| Role    | Email (= Bearer token in dev mode)      |
|---------|-----------------------------------------|
| Admin   | `admin@demo.iqplus.dev`                 |
| Teacher | `david.cohen@demo.iqplus.dev`           |
| Student | `s.weiss@demo.iqplus.dev` (excellent)   |
| Parent  | `p.weiss@demo.iqplus.dev`               |

### Large demo (`@large.iqplus.dev`)
3 admins · 10 teachers · 60 students · 40 parents · 22 courses · 14 weeks · 3 lessons/week
Includes: performance scores, score history, syllabi, messages, usability feedback, 12 AI alerts

```bash
python scripts/seed_large_demo.py           # seed
python scripts/seed_large_demo.py --reseed  # wipe and regenerate
python scripts/seed_large_demo.py --clear   # wipe only
```

Fixed test accounts:

| Role              | Email (= Bearer token in dev mode)          |
|-------------------|---------------------------------------------|
| Admin             | `admin.demo@large.iqplus.dev`               |
| Coordinator       | `coord.academic@large.iqplus.dev`           |
| Teacher (Math)    | `teacher.math@large.iqplus.dev`             |
| Teacher (CS)      | `yoav.ben@large.iqplus.dev`                 |
| Student (excellent) | `student.star@large.iqplus.dev`           |
| Student (at-risk) | `jay.ross@large.iqplus.dev`                 |
| Student (improving) | `carlos.diaz@large.iqplus.dev`            |
| Parent            | `parent.one@large.iqplus.dev`               |

Student profile distribution: 12 excellent · 12 stable_good · 10 stable_average · 8 improving · 8 declining · 10 at_risk

> **Development auth:** set `ENVIRONMENT=development` in `.env`. The Bearer token is the user's email string — no Firebase token required.

## Project Structure

```
app/
├── api/routes/           # API endpoint handlers
├── services/             # Business logic & AI
├── repositories/         # Data access layer
├── models/               # Beanie ODM documents
├── database.py           # MongoDB/Motor connection
├── schemas.py            # Pydantic validation
├── security.py           # Firebase auth & RBAC
├── config.py             # Configuration
└── main.py               # FastAPI app entry
```
