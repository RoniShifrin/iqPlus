# IQ PLUS - Production-Ready Learning Center Management System

**Complete, fully functional system with all components integrated and ready to deploy.**

---

## 📁 Project File Tree (current)

```
iqplus/
├── README.md / PROJECT_OVERVIEW.md / RUNNING_GUIDE.md
│
├── FRONT/src/
│   ├── contexts/AppContext.tsx               # Auth + notification state
│   ├── services/apiService.ts               # Axios API client
│   ├── utils/safeStorage.ts                 # localStorage with Safari fallback
│   ├── components/
│   │   ├── NotificationPanel.tsx            # In-app notification drawer + sound
│   │   ├── QuickFeedbackModal.tsx
│   │   ├── QuickAttendanceModal.tsx
│   │   └── SearchBar.tsx
│   └── pages/
│       ├── LoginPage.tsx / SignupPage.tsx
│       ├── AdminDashboard.tsx               # KPIs + user/course management
│       ├── TeacherDashboard.tsx             # Class performance + alerts
│       ├── StudentDashboard.tsx             # Personal progress + insights
│       ├── ParentDashboard.tsx              # Child scores + alerts
│       ├── CoursesPage.tsx                  # Browse + enroll
│       ├── ProgressPage.tsx                 # Score history + prediction
│       ├── NotificationsPage.tsx
│       ├── AcademicPlannerPage.tsx          # AI Analyze + Recommend
│       └── SettingsPage.tsx
│
├── BACK/
│   ├── app/api/routes/
│   │   ├── auth.py                          # Login / signup / logout / /me
│   │   ├── courses.py                       # Course CRUD
│   │   ├── enrollments.py                   # Enroll + conflict check
│   │   ├── academic.py                      # Grades, attendance, feedback
│   │   ├── scores.py                        # PerformanceScore + prediction
│   │   ├── progress.py                      # Insights + AI alerts
│   │   ├── dashboard.py                     # Role dashboards
│   │   ├── reports.py                       # PDF/CSV export
│   │   ├── notifications.py                 # In-app notifications
│   │   ├── academic_planning.py             # Planner (analyze + recommend)
│   │   ├── profile.py / materials.py / syllabus.py
│   │   ├── audit.py                         # Audit log
│   │   ├── admin_health.py / admin_demo.py
│   │   └── __init__.py
│   ├── app/services/
│   │   ├── __init__.py                      # InsightService, EnrollmentService
│   │   ├── score_service.py                 # Weighted score engine
│   │   ├── claude_service.py                # Anthropic API + rule-based fallback
│   │   └── email_service.py                 # SMTP + APScheduler jobs
│   ├── app/repositories/__init__.py         # All repository classes
│   ├── app/models/__init__.py               # All Beanie ODM models
│   ├── app/schemas.py / security.py / main.py / scheduler.py
│   ├── scripts/
│   │   ├── seed_large_demo.py               # 60 students, 14 weeks
│   │   ├── seed_demo_data.py                # 15 students, 8 courses
│   │   ├── seed_planner_demo.py             # Conflict/balanced/heavy scenarios
│   │   ├── clear_*.py / reseed_demo.py
│   └── tests/                               # 206 tests, all passing
│
└── INFRA/
    ├── docker-compose.yml
    └── .env.example
```

---

## 🏗️ System Architecture

### Three-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                       │
│  React + TypeScript (Vite)                                   │
│  - Login/Signup pages                                        │
│  - Role-based dashboards (Admin, Teacher, Student)           │
│  - Course management UI                                      │
│  - Progress tracking interface                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       │ Bearer Token Auth
┌──────────────────────▼──────────────────────────────────────┐
│                     API LAYER                                │
│  FastAPI + Python                                            │
│  - /api/auth (Login, Signup, Token refresh)                  │
│  - /api/courses (CRUD, list)                                 │
│  - /api/enrollments (Enroll, withdraw, list)                 │
│  - /api/academic (Grades, attendance, feedback)              │
│  - /api/progress (Analytics, insights)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQL
                       │ Transactions
┌──────────────────────▼──────────────────────────────────────┐
│                   DATA LAYER                                 │
│  MongoDB Atlas + Beanie ODM                                 │
│  - 7 core tables (Users, Courses, Enrollments, etc.)         │
│  - Indices for performance                                   │
│  - Foreign key constraints                                   │
│  - Soft delete support                                       │
└─────────────────────────────────────────────────────────────┘
```

### Service Architecture

```
FastAPI Request
      ↓
[Security Layer] ← Firebase Token Verification
      ↓
[API Route Handler]
      ↓
[Repository Layer] ← Queries database
      ↓
[Service Layer] ← Business logic, conflict validation
      ↓
[AI Service] ← Insight generation if threshold met
      ↓
[Email Service] ← Send notification if generated
      ↓
Beanie ODM → MongoDB Atlas
```

---

## 🔐 Authentication & Authorization Flow

### Token Verification Pipeline

```
1. User submits email + password to POST /api/auth/login

2. Backend:
   ├─ Looks up User by email
   ├─ Verifies password with bcrypt (passlib)
   ├─ Issues opaque token: secrets.token_urlsafe(32)
   ├─ Stores hashed token on User document in MongoDB
   └─ Returns token to client

3. Client stores token, sends on every request:
   Authorization: Bearer {session_token}

4. FastAPI Dependency Injection:
   ├─ get_current_user() hashes incoming token
   ├─ Looks up User by session_token_hash
   └─ Returns authenticated User or 401

5. Role-Based Access Control:
   ├─ require_role() / get_teacher_user() dependencies
   ├─ Return 403 Forbidden if role not authorized
   └─ Execute handler if authorized
```

### Why This Approach

✅ **Self-contained** — no external auth service required to run locally
✅ **Simple to demo** — email + password, no Firebase project setup
✅ **Revocable** — logout clears token from DB immediately
✅ **RBAC enforced server-side** — every endpoint has a role dependency

---

## 🤖 AI-Powered Learning Insights

### Insight Generation Pipeline

```
1. Grade Recorded or Attendance Updated
   └─ Trigger: InsightService.check_and_generate_insights()
   
2. Data Analysis:
   ├─ Query last 30 days of grades/attendance
   ├─ Calculate percentage change from previous period
   ├─ Compare against THRESHOLD (±15%)
   
3. Threshold Decision:
   ├─ If |change| < 15% → No insight (suppress spam)
   ├─ If change > 15% → PERFORMANCE_IMPROVEMENT insight
   └─ If change < -15% → PERFORMANCE_DECLINE insight
   
4. Insight Generation:
   ├─ Build learning profile (strengths, concerns, trends)
   ├─ Generate explainable summary with before/after values
   ├─ Create actionable recommendation
   ├─ Store in database (LearningInsight table)
   └─ Set email_sent = false (for batch processing)
   
5. Email Notification:
   ├─ EmailNotificationService detects unsent insights
   ├─ Generates HTML mail with insight details
   ├─ Sends to: student + teacher
   ├─ Marks email_sent = true
   └─ Logs transmission for audit trail
```

### Example Insight

```
Scenario: Student's grade improved from 65 to 80 (23% improvement)

Insight Generated:
├─ Type: PERFORMANCE_IMPROVEMENT
├─ Summary: "Great work! Your grade improved from 65.0 to 80.0 (23.0% increase)"
├─ Recommendation: "Keep up the excellent work. Consider helping peers..."
├─ Metric: grade
├─ Change_Percent: 23.0
└─ EmailSent: false (waiting for batch notification task)

Email Sent To:
├─ student@example.com
└─ teacher@example.com

HTML Mail Contains:
├─ Personalized greeting
├─ Insight summary in highlighted box
├─ Recommendation section
├─ Link to full analytics portal
└─ Engagement call-to-action
```

### Why Integrated AI Service

✅ **Lower latency** - No network calls between services
✅ **Simpler deployment** - Single Python process, no orchestration
✅ **Transactional integrity** - Database changes atomic
✅ **Scalability path** - Can extract to external service later
✅ **Maintenance** - Centralized business logic

---

## 🛡️ RBAC Implementation (Dual-Layer)

### Frontend (User Experience Protection)

```typescript
// Protected routes hide unauthorized content
<PrivateRoute requiredRoles={['admin', 'teacher']}>
  <GradingInterface />
</PrivateRoute>

// Conditional UI rendering
{user.role === 'admin' && <AdminPanel />}
{user.role === 'teacher' && <ClassManagement />}
{user.role === 'student' && <CourseEnrollment />}
```

**Frontend cannot be trusted** - Users can inspect HTML/JS and bypass checks

### Backend (Security Enforcement) ⚠️ CRITICAL

```python
# Every endpoint has authorization check
@router.post("/api/academic/grades")
async def record_grade(
    grade: GradeCreate,
    current_user: User = Depends(get_teacher_user),  # ← ENFORCED
    db: Session = Depends(get_db)
):
    """Record grade (teachers only) - CANNOT BE BYPASSED"""
    # current_user is guaranteed to have TEACHER or ADMIN role
    # If not, request fails with 403 before reaching handler
    ...
```

**Backend is the source of truth** - Cannot be manipulated by client

### Role Permissions Matrix

| Endpoint | Admin | Teacher | Student | Parent |
|----------|-------|---------|---------|--------|
| Create Course | ✓ | ✓ | ✗ | ✗ |
| Record Grade | ✓ | ✓ | ✗ | ✗ |
| Enroll Course | ✓ | ✗ | ✓ | ✗ |
| View Progress | ✓ | ✓ (own class) | ✓ (own) | ✓ (child) |
| Manage Users | ✓ | ✗ | ✗ | ✗ |
| View Insights | ✓ | ✓ (own class) | ✓ (own) | ✓ (child) |

---

## 🚀 Running the System

### Quick Start (Docker) - Recommended
```bash
cd INFRA
docker compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs


### Manual Setup
**Backend:**
```bash
cd BACK
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd FRONT
npm install
npm run dev
```

---

## 📊 Database Schema

### Core Tables (7)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| **users** | Auth & profile | firebase_uid, email, role, is_active |
| **courses** | Course catalog | code, name, teacher_id, schedule, capacity |
| **enrollments** | Student-course link | student_id, course_id, status, enrolled_at |
| **grades** | Student performance | student_id, course_id, score, subject |
| **attendance** | Class attendance | student_id, course_id, date, status |
| **feedback** | Course feedback | student_id, course_id, sentiment, content |
| **learning_insights** | AI-generated | student_id, course_id, insight_type, summary |

### Relationships

```
User
├─ courses_taught (1:N with Course)
├─ enrollments (1:N with Enrollment)
├─ grades (1:N with Grade)
├─ attendance (1:N with Attendance)
├─ feedback (1:N with Feedback)
└─ learning_insights (1:N with LearningInsight)

Course
├─ teacher (N:1 with User)
├─ enrollments (1:N with Enrollment)
├─ grades (1:N with Grade)
├─ attendance (1:N with Attendance)
├─ feedback (1:N with Feedback)
└─ learning_insights (1:N with LearningInsight)
```

---

## 📝 API Endpoints

### Authentication
- `POST /api/auth/signup` — Register
- `POST /api/auth/login` — Login → session token
- `GET /api/auth/me` — Current user
- `POST /api/auth/logout` — Invalidate token

### Courses & Enrollments
- `POST/GET/PATCH/DELETE /api/courses/` — CRUD
- `POST/GET/DELETE /api/enrollments/` — Enroll / withdraw
- `GET/POST /api/syllabus/{course_id}` — Syllabus (draft/publish)
- `GET/POST /api/materials/{course_id}` — File upload/download

### Academic
- `POST/GET /api/academic/grades`
- `POST/GET /api/academic/attendance`
- `POST/GET /api/academic/feedback`

### Scores & Progress
- `GET /api/scores/{student_id}/{course_id}` — Performance score
- `GET /api/scores/{student_id}/{course_id}/history`
- `GET /api/scores/{student_id}/{course_id}/prediction`
- `POST /api/progress/generate-insights`

### Dashboard & Reports
- `GET /api/dashboard` — Role-specific data
- `GET /api/reports/student/{id}/pdf`
- `GET /api/reports/class/{course_id}/csv`

### Notifications & Alerts
- `GET /api/notifications` — In-app notifications
- `PATCH /api/notifications/{id}/read`
- `GET /api/ai-alerts` — AI-generated alerts
- `PATCH /api/ai-alerts/{id}/acknowledge`

### Academic Planner
- `POST /api/planner/analyze` — Conflict + workload + AI recommendations
- `GET /api/planner/recommend` — Personalized course suggestions

### Admin
- `GET /api/admin/students` — All students
- `GET /api/audit` — Audit log
- `GET/POST /api/admin/demo/...` — Demo data management

Full docs: http://localhost:8000/docs

---

## 📦 Technology Stack Summary

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tooling
- **TailwindCSS** - Styling
- **Axios** - HTTP client
- **React Router** - Navigation
- **React Context** - State management

### Backend
- **FastAPI 0.104.1** - Web framework
- **Python 3.11** - Runtime
- **Beanie 1.x** - MongoDB ODM
- **Pydantic 2.5** - Validation
- **MongoDB Atlas** - Database
- **Firebase Admin SDK** - Auth verification
- **Motor** - Async MongoDB driver

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Nginx** (optional) - Reverse proxy
- **GitHub Actions** (optional) - CI/CD

---

## 🎯 Key Features Implemented

✅ **Authentication** — email + password, opaque session tokens, bcrypt hashing, logout revocation

✅ **RBAC (4 roles)** — Admin, Teacher, Student, Parent; enforced on every API endpoint + frontend routes

✅ **Course Management** — CRUD, capacity, soft-delete, schedule metadata, syllabus (draft/published), file materials upload

✅ **Enrollment** — schedule conflict detection, duplicate prevention, status lifecycle, parent-initiated requests

✅ **Academic Data** — grades, attendance (with duplicate-submission guard), feedback with sentiment analysis

✅ **Performance Scoring** — weighted composite score (grades 50% + attendance 30% + feedback 20%), history, trend prediction

✅ **AI Insights** — grade/attendance decline detection → AIAlert + email; deduplication prevents repeat alerts

✅ **Academic Planner** — course combination conflict analysis, workload scoring, Claude-backed AI recommendations with rule-based fallback; 3 demo scenarios (conflict / balanced / heavy)

✅ **Role Dashboards** — admin KPIs, teacher per-student progress, student personal view, parent child scores

✅ **Reports** — per-student PDF export, per-class CSV (RBAC: teacher/admin only)

✅ **Notifications** — in-app panel, sound toggle, unread count, mark-read, APScheduler weekly digest emails

✅ **Audit Log** — all write actions recorded with actor, timestamp, details

✅ **Demo Data** — 3 seed scripts: large (60 students), small (15 students), planner-specific; CLI + API clear/reseed

✅ **Test Suite** — 206 pytest-asyncio tests, MongoDB/Firebase fully mocked, all passing

---

## 🔄 Deployment Workflow

### Development
```bash
# Terminal 1: Backend
cd BACK
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port=8000

# Terminal 2: Frontend
cd FRONT
npm install && npm run dev
# Visit http://localhost:5173
```

### Production (Docker)
```bash
cd INFRA
cp .env.example .env
# Edit .env with production credentials

docker compose up --build -d

# Database setup (one-time)
docker compose exec backend python -m app.database
```

### Scaling Considerations
- Frontend: Deploy to CDN (Cloudflare, AWS CloudFront)
- Backend: Scale horizontally with load balancer (Nginx, AWS ALB)
- Database: MongoDB Atlas (already managed)
- Storage: S3 for file uploads
- Cache: Redis for sessions
- Queue: Celery for async tasks (email, insights)

---

## 📖 Documentation Files

| File | Purpose |
|------|---------|
| README.md | Main project overview |
| BACK/README.md | Backend setup & structure |
| BACK/SETUP.md | Backend detailed setup |
| FRONT/README.md | Frontend setup & structure |
| FRONT/SETUP.md | Frontend detailed setup |
| DATA/SCHEMA.md | Database ER diagram & design |
| INFRA/setup.sh | Automated setup script |

---

## ✅ Verification Checklist

After deployment:

- [ ] Frontend loads at http://localhost:5173
- [ ] Backend API responds at http://localhost:8000/health
- [ ] API documentation available at http://localhost:8000/docs
- [ ] User can sign up and create account
- [ ] User can log in and see dashboard
- [ ] Teacher can create course
- [ ] Student can enroll in course
- [ ] Teacher can record grades
- [ ] Student can view progress
- [ ] Insights generated after grade changes
- [ ] Email notifications sent (check SMTP config)
- [ ] UI is responsive on mobile

---

## 🐛 Troubleshooting

### Port conflicts
```bash
docker compose down
lsof -i :8000  # Check what's using port
```

### Database connection errors
```bash
# Check backend MongoDB connection
docker compose ps
docker compose logs backend  # MongoDB connection issues
```

### Firebase auth not working
```bash
# Enable development mode (remove auth requirement)
# Edit BACK/app/security.py and disable auth checks
```

### Frontend not connecting to API
```bash
# Check VITE_API_URL in FRONT/.env
# Verify backend is running on expected port
# Check CORS in BACK/app/main.py
```

---

**Status:** ✅ **PRODUCTION READY**

All components integrated, tested, and documented. Ready for deployment.

**Last Updated:** March 21, 2026
