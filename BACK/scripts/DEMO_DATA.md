# IQ PLUS — Demo Data Guide

A fully populated academic demo environment for end-to-end exploration,
UI review, and identification of missing features.

---

## Commands

All commands must be run from the `BACK/` directory.

```bash
# Seed demo data (aborts safely if data already exists)
python scripts/seed_demo_data.py

# Wipe and regenerate in one step
python scripts/seed_demo_data.py --reseed

# Wipe demo data only (preserves real records)
python scripts/seed_demo_data.py --clear
# or, using the standalone cleaner:
python scripts/clear_demo_data.py
```

---

## What gets created

| Collection         | Count  | Notes                                      |
|--------------------|--------|--------------------------------------------|
| users              | 36     | 1 admin, 5 teachers, 15 students, 15 parents |
| courses            | 8      | All PUBLISHED with schedules               |
| enrollments        | 44     | Students across 2–4 courses each           |
| lesson_records     | ~880   | 2/week × 10 weeks per enrollment           |
| attendance         | ~880   | One per lesson record                      |
| grades             | ~616   | Created when a grade value exists          |
| feedback           | ~440   | Every other attended lesson                |
| progress_metrics   | 44     | One per enrollment (computed)              |
| learning_insights  | 8      | Notable performance changes                |
| ai_alerts          | 6      | 2 CRITICAL, 4 WARNING                      |
| notifications      | ~18    | Student + teacher + parent per alert       |
| weekly_summaries   | 44     | One per enrollment                         |
| course_materials   | 24     | 3 per course                               |
| audit_logs         | ~26    | Course creation, enrolments, user reg.     |

---

## Demo accounts

Login in **development mode**: the Bearer token is the user's email address.

### Admin
| Email                        |
|------------------------------|
| admin@demo.iqplus.dev        |

### Teachers
| Email                             | Courses           |
|-----------------------------------|-------------------|
| david.cohen@demo.iqplus.dev       | MATH101, MATH201  |
| sarah.levy@demo.iqplus.dev        | ENG101, ENG201    |
| rachel.ben@demo.iqplus.dev        | SCI101, PHY201    |
| moshe.gold@demo.iqplus.dev        | CHEM101           |
| yoav.amit@demo.iqplus.dev         | CS101             |

### Students — performance profiles
| Email                             | Profile         |
|-----------------------------------|-----------------|
| j.rosner@demo.iqplus.dev          | at_risk         |
| michal.stern@demo.iqplus.dev      | at_risk         |
| amir.gold2@demo.iqplus.dev        | at_risk         |
| yael.mizrahi@demo.iqplus.dev      | declining       |
| ronen.peretz@demo.iqplus.dev      | declining       |
| tom.levi@demo.iqplus.dev          | stable_average  |
| dana.cohen@demo.iqplus.dev        | stable_average  |
| tamar.benami@demo.iqplus.dev      | stable_average  |
| mam.lahav@demo.iqplus.dev         | stable_good     |
| avi.shapiro@demo.iqplus.dev       | stable_good     |
| hila.dagan@demo.iqplus.dev        | stable_good     |
| eli.baron@demo.iqplus.dev         | improving       |
| yossi.haim@demo.iqplus.dev        | improving       |
| s.weiss@demo.iqplus.dev           | excellent       |
| noa.katz@demo.iqplus.dev          | excellent       |

### Parents (selected)
| Email                             | Linked child        |
|-----------------------------------|---------------------|
| p.rosner@demo.iqplus.dev          | Jonathan Rosner     |
| p.weiss@demo.iqplus.dev           | Sarah Weiss         |
| p.mizrahi@demo.iqplus.dev         | Yael Mizrahi        |
| p.stern@demo.iqplus.dev           | Michal Stern        |
| *(+ 11 more, one per student)*    |                     |

---

## Pre-seeded alerts

| Level    | Student           | Course  | Reason                              |
|----------|-------------------|---------|-------------------------------------|
| CRITICAL | Jonathan Rosner   | MATH101 | Attendance 44%, average grade 46%   |
| CRITICAL | Michal Stern      | ENG101  | Attendance 46%, core content missed |
| WARNING  | Jonathan Rosner   | CS101   | Average below 50%                   |
| WARNING  | Amir Goldstein    | MATH101 | Three consecutive scores below 55%  |
| WARNING  | Yael Mizrahi      | MATH101 | Grade dropped from 82% to 63%       |
| WARNING  | Ronen Peretz      | ENG101  | Declining trend over 5 weeks        |

---

## Safety

- All demo documents are tracked in the `_demo_registry` MongoDB collection.
- The clear scripts delete **only** documents listed in that registry.
- Real manually created data is never touched.
- All demo user emails use the `@demo.iqplus.dev` domain for easy visual identification.

---

## Student profile reference

| Profile        | Attendance | Grade range     | Trend behaviour              |
|----------------|------------|-----------------|------------------------------|
| at_risk        | ~30%       | 33–57%          | Flat / declining              |
| declining      | 100% early, ~55% late | 74–87% → 42–62% | Downward    |
| stable_average | ~65%       | 56–74%          | Flat                         |
| stable_good    | ~85%       | 72–87%          | Flat                         |
| improving      | ~60% early, ~88% late | 45–63% → 73–88% | Upward  |
| excellent      | ~96%       | 87–99%          | Flat high                    |
