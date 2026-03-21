# IQ PLUS - Learning Center Management System

## Repository Structure

```
iqplus/
├── FRONT/                  # React + TypeScript frontend
│   ├── src/
│   │   ├── pages/         # Page components
│   │   ├── components/    # Reusable components
│   │   ├── services/      # API and Firebase services
│   │   ├── hooks/         # Custom React hooks
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── BACK/                   # Python FastAPI backend
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py
│   │   │   │   ├── courses.py
│   │   │   │   ├── enrollments.py
│   │   │   │   ├── academic.py
│   │   │   │   └── progress.py
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   ├── __init__.py      # Business logic
│   │   │   ├── ai_service.py    # Learning insights AI
│   │   │   └── email_service.py # Notifications
│   │   ├── repositories/        # Data access layer
│   │   │   └── __init__.py
│   │   ├── models/
│   │   │   └── __init__.py      # SQLAlchemy models
│   │   ├── database.py          # DB connection
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── security.py          # Auth & RBAC
│   │   ├── main.py              # FastAPI app
│   │   └── __init__.py
│   ├── DATA/migrations/        # MongoDB index setup
│   │   └── versions/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── DATA/                   # Database schema and migrations
│   ├── SCHEMA.md          # ER diagram and documentation
│   └── migrations/
│       ├── initial_schema.sql
│       └── 001_initial_schema.py
│
└── INFRA/                  # Infrastructure and deployment
    ├── docker-compose.yml
    ├── .env.example
    ├── setup.sh
    ├── scripts/
    │   └── seed_database.py
    └── README.md
```

## Key Architecture Features

### 1. **Token Verification Strategy**
The backend uses email + password login with opaque session tokens stored in MongoDB:

```
Client Browser (FRONT)
    ↓
POST /api/auth/login  { email, password }
    ↓
Backend verifies password hash (bcrypt/passlib)
    ↓
Issues opaque session token  (secrets.token_urlsafe(32))
Stores hashed token on User document in MongoDB
    ↓
Client stores token, sends as:
    Authorization: Bearer {session_token}
    ↓
FastAPI dependency: get_current_user()
    ├─ Hashes incoming token
    ├─ Looks up User by session_token_hash
    └─→ Returns authenticated User object
    ↓
Route handler receives authenticated User object
```

**Why this approach:**
- **Self-contained**: No external auth provider required to run locally
- **Simple to demo**: `email + password` — no Firebase project setup needed
- **Revocable**: Logout clears the token from DB immediately
- Firebase Admin SDK is still wired in for optional UID syncing

### 2. **RBAC (Role-Based Access Control)**

**Frontend Level** (Client-side protection):
- Protected routes check user role before rendering
- UI elements conditionally shown based on role
- Prevents unauthorized navigation

**Backend Level** (Server-side enforcement - CRITICAL):
- Every endpoint has role-dependent `Depends()` middleware
- Route handlers receive authenticated User object with role
- Raises `HTTP_403_FORBIDDEN` if role not authorized
- Cannot be bypassed even with token manipulation

**Rationale for dual enforcement:**
- **Frontend**: User experience - hide features users can't access
- **Backend**: Security - enforce permission at API layer
- Frontend can be inspected/modified by users - never trust client validation
- Backend is authoritative source of truth for permissions

Roles:
- **ADMIN**: Full system access, user management, report access
- **TEACHER**: Create courses, grade students, view class progress
- **STUDENT**: View own courses, submit feedback, see own progress, view insights
- **PARENT**: View assigned student's progress (future enhancement)

### 3. **AI-Powered Learning Insights**

Implemented as supporting backend service (not external microservice for simplicity):

```python
InsightService
├── check_and_generate_insights()
│   ├─ Query recent grades (last 30 days)
│   ├─ Calculate percentage change
│   ├─ Compare against THRESHOLD (15%)
│   ├─ Create LearningInsight record if triggered
│   └─ Trigger email notification
├── check_attendance_insights()
│   └─ Similar flow for attendance changes
└── Insight Types:
    ├─ PERFORMANCE_IMPROVEMENT
    ├─ PERFORMANCE_DECLINE  
    ├─ ATTENDANCE_IMPROVEMENT
    └─ ATTENDANCE_CONCERN
```

**Why integrated (not external service):**
- Simpler deployment - single Python process
- Lower latency - no network calls between services
- Shared database access - transactional integrity
- Can be refactored to external microservice later if needed

**Threshold Logic:**
- Compares recent average (last 5 grades) vs older average
- Only creates insight if ±15% change detected
- Prevents notification spam
- Explainable: shows before/after values

**Email Notifications:**
- Sent to student + teacher (configurable)
- Only if significance threshold met
- Tracked to prevent duplicates
- HTML templates with actionable recommendations

### 4. **Schedule Conflict Detection**

```python
EnrollmentService.check_schedule_conflict()
├─ Get student's active enrollments
├─ Extract schedule from existing courses
├─ Compare with new course schedule
├─ Check for overlapping time slots
└─ Return True if conflict, Block enrollment
```

Prevents double-booking of students in overlapping courses.

---

## Running the System

See **[RUNNING_GUIDE.md](RUNNING_GUIDE.md)** for the full step-by-step guide including prerequisites, seeding, credentials, and troubleshooting.

### Quick Start (Manual)

```powershell
# Terminal 1 — Backend
cd BACK
venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd FRONT
npm install && npm run dev
```

### Seed Demo Data

```powershell
cd BACK
# Large demo (60 students, 22 courses, 14 weeks of history)
venv\Scripts\python scripts/seed_large_demo.py

# Small demo (15 students, 8 courses)
venv\Scripts\python scripts/seed_demo_data.py

# Planner demo (conflict / balanced / heavy-workload scenarios)
venv\Scripts\python scripts/seed_planner_demo.py
```

### Demo Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin.demo@large.iqplus.dev` | `Admin123!` |
| Teacher | `teacher.math@large.iqplus.dev` | `Teacher123!` |
| Student | `student.star@large.iqplus.dev` | `Student123!` |
| Parent | `parent.one@large.iqplus.dev` | `Parent123!` |

See RUNNING_GUIDE.md §5 for full credential tables for all three demo datasets.

---

## API Endpoints

### Authentication
- `POST /api/auth/signup` — Register new user
- `POST /api/auth/login` — Login (email + password → session token)
- `GET /api/auth/me` — Get current user
- `POST /api/auth/logout` — Invalidate session token

### Courses & Enrollments
- `POST /api/courses/` — Create course (teacher/admin)
- `GET /api/courses/` — List courses
- `PATCH /api/courses/{id}` — Update course
- `DELETE /api/courses/{id}` — Soft-delete course
- `POST /api/enrollments/` — Enroll student (conflict check)
- `PATCH /api/enrollments/{id}` — Update enrollment status
- `DELETE /api/enrollments/{id}` — Withdraw

### Academic
- `POST /api/academic/grades` — Record grade
- `GET /api/academic/grades` — List grades (RBAC: own data only)
- `POST /api/academic/attendance` — Record attendance
- `GET /api/academic/attendance` — List attendance (RBAC)
- `POST /api/academic/feedback` — Submit feedback
- `GET /api/academic/feedback` — List feedback (RBAC)

### Scores & Progress
- `GET /api/scores/{student_id}/{course_id}` — Get performance score
- `GET /api/scores/{student_id}/{course_id}/history` — Score history
- `GET /api/scores/{student_id}/{course_id}/prediction` — Predicted trend
- `POST /api/progress/generate-insights` — Trigger insight generation

### Dashboard & Reports
- `GET /api/dashboard` — Role-specific dashboard data
- `GET /api/reports/student/{id}/pdf` — PDF progress report
- `GET /api/reports/class/{course_id}/csv` — Class CSV export
- `GET /api/admin/students` — Admin: all students with enrollment stats

### Notifications & Alerts
- `GET /api/notifications` — List notifications for current user
- `PATCH /api/notifications/{id}/read` — Mark as read
- `GET /api/ai-alerts` — List AI-generated alerts (parent/admin)
- `PATCH /api/ai-alerts/{id}/acknowledge` — Acknowledge alert

### Academic Planner
- `POST /api/planner/analyze` — Analyze selected courses for conflicts, workload, and AI recommendations
- `GET /api/planner/recommend` — Get personalized course recommendations

### Syllabus & Materials
- `POST /api/syllabus/{course_id}` — Create/update syllabus
- `GET /api/syllabus/{course_id}` — Get syllabus (draft/published RBAC)
- `POST /api/materials/{course_id}` — Upload course material
- `GET /api/materials/{course_id}` — List materials

### Admin & Audit
- `GET /api/audit` — Audit log (admin only)
- `GET /api/admin/demo/status` — Demo data status
- `POST /api/admin/demo/clear` — Clear demo data

Full interactive documentation: http://localhost:8000/docs

---

## Environment Configuration

See `INFRA/.env.example` for all required variables:

```env
# Firebase
FIREBASE_PROJECT_ID=your-project
FIREBASE_PRIVATE_KEY=your-key
FIREBASE_CLIENT_EMAIL=your-email

# SMTP (Email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Database
MONGODB_URL=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/
```

---

## Features Implemented

✅ **Authentication** — email + password with opaque session tokens (no external auth service required)
✅ **RBAC** — Admin / Teacher / Student / Parent, enforced on every endpoint
✅ **Course management** — CRUD, capacity, soft-delete, syllabus (draft/published), materials upload
✅ **Enrollment** — schedule conflict detection, status tracking, parent enrollment requests
✅ **Academic data** — grades, attendance, feedback with sentiment; duplicate-submission guards
✅ **Performance scoring** — weighted composite score (grades + attendance + feedback), history, trend prediction
✅ **AI insights** — grade/attendance decline detection → AIAlert + email; deduplication guard
✅ **AI planner** — course combination analysis, conflict detection, workload scoring, Claude-backed recommendations with rule-based fallback
✅ **Role dashboards** — admin KPIs, teacher per-student progress, parent child scores
✅ **Reports** — per-student PDF, per-class CSV (admin/teacher only)
✅ **Notifications** — in-app panel with sound toggle, mark-read, unread count badge
✅ **Email** — weekly summaries, feedback digest, performance warnings (APScheduler)
✅ **Audit log** — every write action recorded with actor and timestamp
✅ **Demo data** — large (60 students), small (15 students), and planner-specific seed scripts
✅ **206-test suite** — pytest-asyncio with MongoDB/Firebase mocked; all passing

---

## Technology Stack

**Frontend:**
- React 18 + TypeScript
- Vite
- TanStack Query (data fetching)
- React Router (navigation)
- TailwindCSS (styling)
- Firebase SDK (auth)

**Backend:**
- Python 3.11
- FastAPI (web framework)
- Beanie 1.x (MongoDB ODM)
- Pydantic v2 (validation)
- Firebase Admin SDK (auth)
- MongoDB Atlas (database)

**Deployment:**
- Docker & Docker Compose
- MongoDB Atlas (cloud)
- Production-ready configurations

---

**Status**: Production-ready system with all components integrated and tested.
