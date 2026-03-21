#!/usr/bin/env python3
"""
IQ PLUS — Academic Planner Demo Seeder
=======================================
Creates 6 courses and 3 demo users specifically designed to showcase the
Academic Planner AI Analyze feature: conflict detection, balanced schedule
recommendation, and heavy-workload warnings.

Usage:
    python scripts/seed_planner_demo.py              # seed (skip if already exists)
    python scripts/seed_planner_demo.py --reseed     # wipe and regenerate
    python scripts/seed_planner_demo.py --clear      # wipe only

All accounts use the @planner.iqplus.dev domain.
Documents are tracked in _demo_registry so /api/admin/demo/clear?dataset=small
removes them safely alongside the main demo dataset.

Login (development mode — Bearer token = email):
    Teacher : planner.teacher@planner.iqplus.dev
    Student : planner.student@planner.iqplus.dev
    Parent  : planner.parent@planner.iqplus.dev
    Password: Planner123!  (all three)

-----------------------------------------------------------------------------
Planner Scenario Guide
-----------------------------------------------------------------------------

  SCENARIO 1 — CONFLICT
  ─────────────────────
  Submit course IDs: [PLAN101, PLAN102]
  Both run Monday + Wednesday 09:00–11:00 vs 10:00–12:00.
  The planner detects a 1-hour overlap (10:00–11:00) on both days.

  SCENARIO 2 — BALANCED
  ──────────────────────
  Submit course IDs: [PLAN103, PLAN104]
  Spread across Tue/Thu and Friday. Zero conflicts. Light weekly hours (4.5h).
  Planner should recommend this as an ideal pairing.

  SCENARIO 3 — HEAVY WORKLOAD
  ────────────────────────────
  Submit course IDs: [PLAN101, PLAN103, PLAN104, PLAN105, PLAN106]
  17.5 contact hours/week. Monday alone carries 4h. Planner will flag
  high daily density and recommend reducing to 3–4 courses.

-----------------------------------------------------------------------------
"""

import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
BACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACK_DIR.parent / ".env")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from passlib.context import CryptContext

from app.models import (
    ALL_DOCUMENTS,
    User, Course, Enrollment,
    RoleEnum, CourseStatusEnum, EnrollmentStatusEnum,
)

# ── Configuration ─────────────────────────────────────────────────────────────
MONGODB_URL        = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME            = os.getenv("DB_NAME",     "iqplus_db")
REGISTRY_COLLECTION = "_demo_registry"          # shared with main demo — cleared together
DEMO_DOMAIN         = "@planner.iqplus.dev"
DATASET_TAG         = "planner"

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEMO_PASSWORD = "Planner123!"

# ── Users ─────────────────────────────────────────────────────────────────────

_TEACHER = dict(
    email      = "planner.teacher@planner.iqplus.dev",
    first_name = "Dana",
    last_name  = "Planner",
)

_STUDENT = dict(
    email      = "planner.student@planner.iqplus.dev",
    first_name = "Avi",
    last_name  = "Demo",
)

_PARENT = dict(
    email      = "planner.parent@planner.iqplus.dev",
    first_name = "Ruth",
    last_name  = "Demo",
)

# ── Courses ───────────────────────────────────────────────────────────────────
#
# Schedule format used by the Academic Planner:
#   {
#     "days":       ["monday", "wednesday"],   # list of lowercase day names
#     "start_time": "09:00",                   # "HH:MM"
#     "end_time":   "11:00",                   # "HH:MM"
#   }
#
# Course codes are prefixed with PLAN to avoid collisions with existing seed data.

_COURSES = [
    # ── Scenario 1 participant A ──────────────────────────────────────────────
    dict(
        code        = "PLAN101",
        name        = "Advanced Mathematics",
        description = (
            "In-depth exploration of calculus, linear algebra, and mathematical "
            "proof techniques. Heavy problem-set workload. 2 contact hours per session."
        ),
        schedule    = {
            "days":       ["monday", "wednesday"],
            "start_time": "09:00",
            "end_time":   "11:00",
        },
        capacity    = 25,
        # weekly contact: 2 sessions × 2h = 4h
    ),
    # ── Scenario 1 participant B (conflicts with PLAN101) ────────────────────
    dict(
        code        = "PLAN102",
        name        = "Physics Lab",
        description = (
            "Experimental physics laboratory covering mechanics, electromagnetism, "
            "and optics. Lab reports due weekly. "
            "WARNING: Overlaps with Advanced Mathematics (Mon & Wed 10:00–11:00)."
        ),
        schedule    = {
            "days":       ["monday", "wednesday"],
            "start_time": "10:00",
            "end_time":   "12:00",
        },
        capacity    = 20,
        # weekly contact: 2 sessions × 2h = 4h
        # CONFLICT with PLAN101: shared days Mon+Wed, overlap window 10:00–11:00
    ),
    # ── Scenario 2 & 3 participant: balanced course A ─────────────────────────
    dict(
        code        = "PLAN103",
        name        = "Literature Studies",
        description = (
            "Close reading of modern and classic literary works, weekly discussion "
            "seminars, and essay assignments. Tue/Thu morning — no schedule conflicts."
        ),
        schedule    = {
            "days":       ["tuesday", "thursday"],
            "start_time": "09:00",
            "end_time":   "10:30",
        },
        capacity    = 28,
        # weekly contact: 2 sessions × 1.5h = 3h
    ),
    # ── Scenario 2 & 3 participant: balanced course B ─────────────────────────
    dict(
        code        = "PLAN104",
        name        = "History & Society",
        description = (
            "Sociopolitical history from the Industrial Revolution to the present. "
            "Friday-only schedule; pairs cleanly with any Mon–Thu course."
        ),
        schedule    = {
            "days":       ["friday"],
            "start_time": "10:00",
            "end_time":   "11:30",
        },
        capacity    = 30,
        # weekly contact: 1 session × 1.5h = 1.5h
    ),
    # ── Scenario 3 participant: high-density course ───────────────────────────
    dict(
        code        = "PLAN105",
        name        = "Data Science",
        description = (
            "Practical machine learning, statistics, and data visualisation. "
            "Three sessions per week (Mon, Tue, Thu) for intensive lab practice. "
            "6 contact hours/week — major contributor to heavy-load scenario."
        ),
        schedule    = {
            "days":       ["monday", "tuesday", "thursday"],
            "start_time": "14:00",
            "end_time":   "16:00",
        },
        capacity    = 22,
        # weekly contact: 3 sessions × 2h = 6h
    ),
    # ── Scenario 3 participant: secondary density course ─────────────────────
    dict(
        code        = "PLAN106",
        name        = "Digital Arts",
        description = (
            "Graphic design, UX fundamentals, and creative software tooling. "
            "Wed and Fri afternoons; adds 3h/week to heavy-load scenario."
        ),
        schedule    = {
            "days":       ["wednesday", "friday"],
            "start_time": "13:00",
            "end_time":   "14:30",
        },
        capacity    = 18,
        # weekly contact: 2 sessions × 1.5h = 3h
    ),
]

# ── Default enrollment ─────────────────────────────────────────────────────────
# Pre-enroll the demo student in the BALANCED scenario courses so the planner
# can show personalised context (existing score / workload level).
# All three demo scenarios work regardless of enrollment state — the planner
# accepts any valid course_ids array.
_DEFAULT_ENROLLMENT_CODES = ["PLAN103", "PLAN104"]


# ── Registry helpers ───────────────────────────────────────────────────────────

async def _save_registry(db, ids: dict) -> None:
    """Append a tagged entry to the shared _demo_registry."""
    await db[REGISTRY_COLLECTION].insert_one({
        "seeded_at":  datetime.utcnow(),
        "dataset":    DATASET_TAG,
        "version":    "1.0",
        "collections": {k: list(v) for k, v in ids.items()},
    })


async def _clear(db) -> None:
    """Remove all planner demo documents tracked in the registry."""
    entries = await db[REGISTRY_COLLECTION].find(
        {"dataset": DATASET_TAG}
    ).to_list(length=None)

    if not entries:
        print("  No planner demo data found in registry.")
        return

    merged: dict[str, set] = {}
    for e in entries:
        for coll, str_ids in e.get("collections", {}).items():
            merged.setdefault(coll, set()).update(str_ids)

    total = 0
    for coll_name, str_ids in sorted(merged.items()):
        if not str_ids:
            continue
        oids   = [ObjectId(s) for s in str_ids]
        result = await db[coll_name].delete_many({"_id": {"$in": oids}})
        n      = result.deleted_count
        total += n
        if n:
            print(f"  Deleted {n:>4}  from  {coll_name}")

    await db[REGISTRY_COLLECTION].delete_many({"dataset": DATASET_TAG})
    print(f"\n  Total removed: {total} documents. Planner demo registry cleared.")


# ── Main seeder ────────────────────────────────────────────────────────────────

async def seed() -> None:
    do_reseed = "--reseed" in sys.argv or "--force" in sys.argv
    do_clear  = "--clear"  in sys.argv

    print(f"\n  IQ PLUS — Planner Demo Seeder")
    print(f"  Connecting to {DB_NAME} ...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db     = client[DB_NAME]
    await init_beanie(database=db, document_models=ALL_DOCUMENTS)
    print("  Connected.\n")

    if do_clear:
        await _clear(db)
        return

    existing = await db[REGISTRY_COLLECTION].find_one({"dataset": DATASET_TAG})
    if existing:
        if not do_reseed:
            print("  Planner demo data already exists. Use --reseed to regenerate.\n")
            return
        print("  Wiping existing planner demo data ...")
        await _clear(db)
        print()

    ids: dict[str, list] = defaultdict(list)

    # ── 1. Teacher ─────────────────────────────────────────────────────────────
    teacher = User(
        firebase_uid    = _TEACHER["email"],
        email           = _TEACHER["email"],
        first_name      = _TEACHER["first_name"],
        last_name       = _TEACHER["last_name"],
        role            = RoleEnum.TEACHER,
        hashed_password = _pwd.hash(DEMO_PASSWORD),
        is_active       = True,
        is_approved     = True,
    )
    await teacher.insert()
    ids["users"].append(str(teacher.id))
    print(f"  Teacher  : {teacher.email}  (id={teacher.id})")

    # ── 2. Student ─────────────────────────────────────────────────────────────
    student = User(
        firebase_uid    = _STUDENT["email"],
        email           = _STUDENT["email"],
        first_name      = _STUDENT["first_name"],
        last_name       = _STUDENT["last_name"],
        role            = RoleEnum.STUDENT,
        hashed_password = _pwd.hash(DEMO_PASSWORD),
        is_active       = True,
        is_approved     = True,
    )
    await student.insert()
    ids["users"].append(str(student.id))
    print(f"  Student  : {student.email}  (id={student.id})")

    # ── 3. Parent (linked to student) ──────────────────────────────────────────
    parent = User(
        firebase_uid        = _PARENT["email"],
        email               = _PARENT["email"],
        first_name          = _PARENT["first_name"],
        last_name           = _PARENT["last_name"],
        role                = RoleEnum.PARENT,
        linked_student_ids  = [str(student.id)],
        hashed_password     = _pwd.hash(DEMO_PASSWORD),
        is_active           = True,
        is_approved         = True,
    )
    await parent.insert()
    ids["users"].append(str(parent.id))
    print(f"  Parent   : {parent.email}  (id={parent.id})")

    # ── 4. Courses ─────────────────────────────────────────────────────────────
    course_map: dict[str, Course] = {}
    print()
    for cd in _COURSES:
        c = Course(
            code            = cd["code"],
            name            = cd["name"],
            description     = cd["description"],
            teacher_id      = str(teacher.id),
            created_by_role = "teacher",
            schedule        = cd["schedule"],
            capacity        = cd["capacity"],
            status          = CourseStatusEnum.PUBLISHED,
        )
        await c.insert()
        course_map[cd["code"]] = c
        ids["courses"].append(str(c.id))
        days_str  = ", ".join(cd["schedule"]["days"]).title()
        time_str  = f"{cd['schedule']['start_time']}–{cd['schedule']['end_time']}"
        print(f"  Course {cd['code']} : {cd['name']}")
        print(f"             {days_str}  {time_str}  (id={c.id})")

    # ── 5. Default enrollments (balanced scenario) ────────────────────────────
    print()
    for code in _DEFAULT_ENROLLMENT_CODES:
        course = course_map[code]
        e = Enrollment(
            student_id  = str(student.id),
            course_id   = str(course.id),
            status      = EnrollmentStatusEnum.ACTIVE,
        )
        await e.insert()
        ids["enrollments"].append(str(e.id))
        print(f"  Enrolled {student.first_name} in {code} ({course.name})")

    # ── 6. Save registry ───────────────────────────────────────────────────────
    await _save_registry(db, ids)
    print()

    # ── 7. Print scenario guide ────────────────────────────────────────────────
    plan101_id = course_map["PLAN101"].id
    plan102_id = course_map["PLAN102"].id
    plan103_id = course_map["PLAN103"].id
    plan104_id = course_map["PLAN104"].id
    plan105_id = course_map["PLAN105"].id
    plan106_id = course_map["PLAN106"].id

    print("  ------------------------------------------------------------------")
    print("  PLANNER DEMO SCENARIO REFERENCE")
    print("  ------------------------------------------------------------------")
    print(f"\n  Student ID  : {student.id}")
    print(f"  Parent ID   : {parent.id}")
    print()
    print("  SCENARIO 1 — CONFLICT DETECTION")
    print("  Submit these two courses to the planner:")
    print(f"    PLAN101 (Advanced Mathematics)  id={plan101_id}")
    print(f"    PLAN102 (Physics Lab)            id={plan102_id}")
    print("  -> Both run Mon + Wed; overlap window 10:00–11:00.")
    print("  -> Planner flags 2 conflicts and recommends removing one.\n")
    print("  SCENARIO 2 — BALANCED SCHEDULE")
    print("  Submit these two courses to the planner:")
    print(f"    PLAN103 (Literature Studies)  id={plan103_id}")
    print(f"    PLAN104 (History & Society)   id={plan104_id}")
    print("  -> Tue/Thu + Friday. Zero conflicts. 4.5 contact hours/week.")
    print("  -> Planner classifies as light/moderate and marks both green.\n")
    print("  SCENARIO 3 — HEAVY WORKLOAD")
    print("  Submit these five courses to the planner:")
    print(f"    PLAN101 (Advanced Mathematics)  id={plan101_id}")
    print(f"    PLAN103 (Literature Studies)    id={plan103_id}")
    print(f"    PLAN104 (History & Society)     id={plan104_id}")
    print(f"    PLAN105 (Data Science)          id={plan105_id}")
    print(f"    PLAN106 (Digital Arts)          id={plan106_id}")
    print("  -> 17.5 contact hours/week. Monday carries 4h (09:00–11:00 + 14:00–16:00).")
    print("  -> Planner warns about daily density and overall heavy load.\n")
    print("  ------------------------------------------------------------------")
    print(f"  Total documents inserted: "
          f"{len(ids['users'])} users, "
          f"{len(ids['courses'])} courses, "
          f"{len(ids['enrollments'])} enrollments")
    print("  Use --reseed to regenerate or --clear to remove.\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
