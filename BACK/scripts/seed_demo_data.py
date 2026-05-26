#!/usr/bin/env python3
"""
IQ PLUS — Demo Data Seeder
==========================
Generates a fully populated academic demo environment for end-to-end exploration.

Usage:
    python scripts/seed_demo_data.py             # seed (abort if demo data exists)
    python scripts/seed_demo_data.py --reseed    # wipe and regenerate
    python scripts/seed_demo_data.py --clear     # wipe only

All demo accounts use the @demo.iqplus.dev domain.
Every created document is tracked in the _demo_registry MongoDB collection so
clear_demo_data.py can remove them precisely without touching real records.

Login (development mode — Bearer token = email):
    e.g.  Authorization: Bearer david.cohen@demo.iqplus.dev
"""

import asyncio
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
BACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACK_DIR / ".env")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from passlib.context import CryptContext

from app.models import (
    ALL_DOCUMENTS,
    User, Course, Enrollment, Grade, Attendance, Feedback,
    LessonRecord, ProgressMetrics, AIAlert, WeeklySummary,
    Notification, CourseMaterial, LearningInsight, AuditLog,
    RoleEnum, EnrollmentStatusEnum, AttendanceStatusEnum,
    AlertLevelEnum, NotificationTypeEnum, CourseStatusEnum,
    DifficultyEnum, SentimentEnum, InsightTypeEnum,
)

# ── Configuration ─────────────────────────────────────────────────────────────

MONGODB_URL        = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME            = os.getenv("DB_NAME",     "iqplus_db")
REGISTRY_COLLECTION = "_demo_registry"
DEMO_DOMAIN        = "@demo.iqplus.dev"
WEEKS_BACK         = 10
LESSONS_PER_WEEK   = 2
RNG                = random.Random(99)   # fixed for reproducibility

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ROLE_PASSWORDS = {
    RoleEnum.ADMIN:   "Admin123!",
    RoleEnum.TEACHER: "Teacher123!",
    RoleEnum.STUDENT: "Student123!",
    RoleEnum.PARENT:  "Parent123!",
}

# ── Feedback content pools ────────────────────────────────────────────────────

_FB: dict[str, list[str]] = {
    "at_risk": [
        "Attendance remains a serious concern. Missed core topics this week.",
        "Struggling to follow the material due to repeated absences.",
        "Several assignments incomplete. Urgent parent meeting recommended.",
        "Has not submitted the last two assignments. Please follow up.",
        "Very low participation. Gaps in understanding are widening.",
        "Needs immediate academic support. Falling behind peers significantly.",
    ],
    "declining": [
        "Performance this week was below what we have come to expect.",
        "Shows less focus compared to earlier in the semester.",
        "Quality of written work has dropped noticeably.",
        "Good potential but recent results do not reflect it.",
        "Encouraged to revise last month's material before the upcoming test.",
        "Participation in discussions has decreased. Check-in suggested.",
    ],
    "stable_average": [
        "Completing work on time. Accuracy on assessments could improve.",
        "Solid attendance and effort. Conceptual depth needs work.",
        "Understands basics well. Encourage further reading.",
        "Steady performance. Review the exercises from chapter three.",
        "On track but capable of achieving more with focused revision.",
        "Reasonable results this week. Keep building on the foundations.",
    ],
    "stable_good": [
        "Strong grasp of this week's content. Minor revision of the last quiz.",
        "Reliable contributor to classroom discussions. Well done.",
        "Consistently solid work. Aim for stretch goals next term.",
        "Good independent thinking demonstrated in today's assignment.",
        "On track and progressing well. Encourage peer tutoring opportunities.",
        "Excellent homework submission rate. Keep up the momentum.",
    ],
    "improving": [
        "Noticeable improvement in accuracy this week. Great effort.",
        "Attendance and focus have both improved. Keep it up.",
        "Starting to show real confidence in problem-solving.",
        "Recent quiz results show a positive upward trend. Well done.",
        "Clearly putting in extra study time — it shows in the results.",
        "Fantastic progress this month. Ready for the next challenge.",
    ],
    "excellent": [
        "Outstanding performance. Consistently top of the class.",
        "Excellent analytical work on this week's assignment.",
        "A model of dedication and intellectual curiosity.",
        "Demonstrated exceptional depth of understanding. Impressive.",
        "Helped peers with a difficult concept. Great leadership.",
        "Near-perfect assessment. Recommended for advanced enrichment.",
    ],
}

# ── Data definitions ──────────────────────────────────────────────────────────

_ADMIN = dict(email="admin@demo.iqplus.dev", first_name="Demo", last_name="Admin")

_TEACHERS = [
    dict(email="david.cohen@demo.iqplus.dev",  first_name="David",  last_name="Cohen"),
    dict(email="sarah.levy@demo.iqplus.dev",   first_name="Sarah",  last_name="Levy"),
    dict(email="rachel.ben@demo.iqplus.dev",   first_name="Rachel", last_name="Ben-David"),
    dict(email="moshe.gold@demo.iqplus.dev",   first_name="Moshe",  last_name="Goldberg"),
    dict(email="yoav.amit@demo.iqplus.dev",    first_name="Yoav",   last_name="Amit"),
]

_STUDENTS = [
    dict(email="j.rosner@demo.iqplus.dev",    first_name="Jonathan", last_name="Rosner",    profile="at_risk"),
    dict(email="s.weiss@demo.iqplus.dev",      first_name="Sarah",    last_name="Weiss",     profile="excellent"),
    dict(email="mam.lahav@demo.iqplus.dev",    first_name="Mam",      last_name="Lahav",     profile="stable_good"),
    dict(email="tom.levi@demo.iqplus.dev",     first_name="Tom",      last_name="Levi",      profile="stable_average"),
    dict(email="dana.cohen@demo.iqplus.dev",   first_name="Dana",     last_name="Cohen",     profile="stable_average"),
    dict(email="yael.mizrahi@demo.iqplus.dev", first_name="Yael",     last_name="Mizrahi",   profile="declining"),
    dict(email="avi.shapiro@demo.iqplus.dev",  first_name="Avi",      last_name="Shapiro",   profile="stable_good"),
    dict(email="noa.katz@demo.iqplus.dev",     first_name="Noa",      last_name="Katz",      profile="excellent"),
    dict(email="eli.baron@demo.iqplus.dev",    first_name="Eli",      last_name="Bar-On",    profile="improving"),
    dict(email="michal.stern@demo.iqplus.dev", first_name="Michal",   last_name="Stern",     profile="at_risk"),
    dict(email="ronen.peretz@demo.iqplus.dev", first_name="Ronen",    last_name="Peretz",    profile="declining"),
    dict(email="hila.dagan@demo.iqplus.dev",   first_name="Hila",     last_name="Dagan",     profile="stable_good"),
    dict(email="yossi.haim@demo.iqplus.dev",   first_name="Yossi",    last_name="Haim",      profile="improving"),
    dict(email="tamar.benami@demo.iqplus.dev", first_name="Tamar",    last_name="Ben-Ami",   profile="stable_average"),
    dict(email="amir.gold2@demo.iqplus.dev",   first_name="Amir",     last_name="Goldstein", profile="at_risk"),
]

# One parent per student (by matching index).
_PARENTS = [
    dict(email="p.rosner@demo.iqplus.dev",    first_name="Michael",  last_name="Rosner",    child=0),
    dict(email="p.weiss@demo.iqplus.dev",      first_name="Hanna",    last_name="Weiss",     child=1),
    dict(email="p.lahav@demo.iqplus.dev",      first_name="Orna",     last_name="Lahav",     child=2),
    dict(email="p.levi@demo.iqplus.dev",       first_name="Uri",      last_name="Levi",      child=3),
    dict(email="p.dcohen@demo.iqplus.dev",     first_name="Rivka",    last_name="Cohen",     child=4),
    dict(email="p.mizrahi@demo.iqplus.dev",    first_name="Oren",     last_name="Mizrahi",   child=5),
    dict(email="p.shapiro@demo.iqplus.dev",    first_name="Leah",     last_name="Shapiro",   child=6),
    dict(email="p.katz@demo.iqplus.dev",       first_name="Moshe",    last_name="Katz",      child=7),
    dict(email="p.baron@demo.iqplus.dev",      first_name="Nitza",    last_name="Bar-On",    child=8),
    dict(email="p.stern@demo.iqplus.dev",      first_name="Eli",      last_name="Stern",     child=9),
    dict(email="p.peretz@demo.iqplus.dev",     first_name="Dina",     last_name="Peretz",    child=10),
    dict(email="p.dagan@demo.iqplus.dev",      first_name="Yigal",    last_name="Dagan",     child=11),
    dict(email="p.haim@demo.iqplus.dev",       first_name="Nurit",    last_name="Haim",      child=12),
    dict(email="p.benami@demo.iqplus.dev",     first_name="Shlomo",   last_name="Ben-Ami",   child=13),
    dict(email="p.goldstein@demo.iqplus.dev",  first_name="Tova",     last_name="Goldstein", child=14),
]

# code → (name, subject, teacher_email, schedule, capacity)
_COURSES = [
    dict(code="MATH101", name="Algebra Fundamentals",    subject="Mathematics",
         teacher_email="david.cohen@demo.iqplus.dev",
         schedule={"monday": "09:00-10:30", "wednesday": "09:00-10:30"}, capacity=30),
    dict(code="MATH201", name="Advanced Calculus",       subject="Mathematics",
         teacher_email="david.cohen@demo.iqplus.dev",
         schedule={"tuesday": "09:00-10:30", "thursday": "09:00-10:30"}, capacity=20),
    dict(code="ENG101",  name="English Composition",     subject="English",
         teacher_email="sarah.levy@demo.iqplus.dev",
         schedule={"monday": "11:00-12:30", "wednesday": "11:00-12:30"}, capacity=28),
    dict(code="ENG201",  name="Literature & Analysis",   subject="Literature",
         teacher_email="sarah.levy@demo.iqplus.dev",
         schedule={"tuesday": "11:00-12:30", "friday": "11:00-12:30"}, capacity=20),
    dict(code="SCI101",  name="General Science",         subject="Science",
         teacher_email="rachel.ben@demo.iqplus.dev",
         schedule={"tuesday": "13:00-14:30", "thursday": "13:00-14:30"}, capacity=25),
    dict(code="PHY201",  name="Physics Principles",      subject="Physics",
         teacher_email="rachel.ben@demo.iqplus.dev",
         schedule={"monday": "13:00-14:30", "thursday": "13:00-14:30"}, capacity=22),
    dict(code="CS101",   name="Programming Fundamentals",subject="Programming",
         teacher_email="yoav.amit@demo.iqplus.dev",
         schedule={"wednesday": "13:00-14:30", "friday": "13:00-14:30"}, capacity=20),
    dict(code="CHEM101", name="Chemistry Basics",        subject="Chemistry",
         teacher_email="moshe.gold@demo.iqplus.dev",
         schedule={"tuesday": "15:00-16:30", "friday": "15:00-16:30"}, capacity=24),
]

# (student_email, course_code)
_ENROLLMENTS = [
    # MATH101 — 10 students (broad intake)
    ("j.rosner@demo.iqplus.dev",    "MATH101"),
    ("s.weiss@demo.iqplus.dev",     "MATH101"),
    ("mam.lahav@demo.iqplus.dev",   "MATH101"),
    ("tom.levi@demo.iqplus.dev",    "MATH101"),
    ("yael.mizrahi@demo.iqplus.dev","MATH101"),
    ("avi.shapiro@demo.iqplus.dev", "MATH101"),
    ("eli.baron@demo.iqplus.dev",   "MATH101"),
    ("hila.dagan@demo.iqplus.dev",  "MATH101"),
    ("tamar.benami@demo.iqplus.dev","MATH101"),
    ("amir.gold2@demo.iqplus.dev",  "MATH101"),
    # MATH201 — 4 advanced students
    ("s.weiss@demo.iqplus.dev",     "MATH201"),
    ("noa.katz@demo.iqplus.dev",    "MATH201"),
    ("hila.dagan@demo.iqplus.dev",  "MATH201"),
    ("eli.baron@demo.iqplus.dev",   "MATH201"),
    # ENG101 — 8 students
    ("j.rosner@demo.iqplus.dev",    "ENG101"),
    ("mam.lahav@demo.iqplus.dev",   "ENG101"),
    ("dana.cohen@demo.iqplus.dev",  "ENG101"),
    ("michal.stern@demo.iqplus.dev","ENG101"),
    ("ronen.peretz@demo.iqplus.dev","ENG101"),
    ("yossi.haim@demo.iqplus.dev",  "ENG101"),
    ("tamar.benami@demo.iqplus.dev","ENG101"),
    ("amir.gold2@demo.iqplus.dev",  "ENG101"),
    # ENG201 — 3 advanced students
    ("s.weiss@demo.iqplus.dev",     "ENG201"),
    ("noa.katz@demo.iqplus.dev",    "ENG201"),
    ("mam.lahav@demo.iqplus.dev",   "ENG201"),
    # SCI101 — 6 students
    ("mam.lahav@demo.iqplus.dev",   "SCI101"),
    ("tom.levi@demo.iqplus.dev",    "SCI101"),
    ("dana.cohen@demo.iqplus.dev",  "SCI101"),
    ("avi.shapiro@demo.iqplus.dev", "SCI101"),
    ("eli.baron@demo.iqplus.dev",   "SCI101"),
    ("yossi.haim@demo.iqplus.dev",  "SCI101"),
    # PHY201 — 4 students
    ("avi.shapiro@demo.iqplus.dev", "PHY201"),
    ("noa.katz@demo.iqplus.dev",    "PHY201"),
    ("tom.levi@demo.iqplus.dev",    "PHY201"),
    ("hila.dagan@demo.iqplus.dev",  "PHY201"),
    # CS101 — 5 students
    ("j.rosner@demo.iqplus.dev",    "CS101"),
    ("dana.cohen@demo.iqplus.dev",  "CS101"),
    ("yossi.haim@demo.iqplus.dev",  "CS101"),
    ("amir.gold2@demo.iqplus.dev",  "CS101"),
    ("michal.stern@demo.iqplus.dev","CS101"),
    # CHEM101 — 4 students
    ("ronen.peretz@demo.iqplus.dev","CHEM101"),
    ("yael.mizrahi@demo.iqplus.dev","CHEM101"),
    ("tamar.benami@demo.iqplus.dev","CHEM101"),
    ("michal.stern@demo.iqplus.dev","CHEM101"),
]

# course_code → 3 material titles
_MATERIALS: dict[str, list[str]] = {
    "MATH101": ["Week 1–4 Exercise Pack", "Equations Reference Sheet", "Mid-Term Practice Paper"],
    "MATH201": ["Calculus Formula Booklet", "Integration Techniques Worksheet", "Final Exam Prep Guide"],
    "ENG101":  ["Essay Structure Guide", "Grammar & Style Checklist", "Reading Comprehension Drills"],
    "ENG201":  ["Literary Analysis Framework", "Annotated Poem Collection", "Critical Essay Rubric"],
    "SCI101":  ["Lab Safety Guidelines", "Unit 1 Revision Notes", "Science Fair Project Brief"],
    "PHY201":  ["Newton's Laws Summary", "Wave & Optics Problems Set", "Physics Formula Sheet"],
    "CS101":   ["Python Quick Reference", "Algorithm Design Workbook", "Debugging Checklist"],
    "CHEM101": ["Periodic Table Poster", "Reaction Types Cheat Sheet", "Lab Report Template"],
}


# ── Lesson parameter generator ────────────────────────────────────────────────

_PRESENT = AttendanceStatusEnum.PRESENT
_ABSENT  = AttendanceStatusEnum.ABSENT
_LATE    = AttendanceStatusEnum.LATE
_EXCUSED = AttendanceStatusEnum.EXCUSED


def _lesson_params(profile: str, week_index: int, total_weeks: int, cseed: int) -> tuple:
    """
    Return (att, grade_or_None, difficulty, engagement, feedback_or_None, sentiment)
    based on student profile and position in timeline.
    """
    progress = week_index / max(total_weeks - 1, 1)
    rng = random.Random(99 + week_index * 19 + cseed)

    if profile == "at_risk":
        att   = rng.choices([_PRESENT, _ABSENT, _EXCUSED, _LATE], weights=[26, 44, 18, 12])[0]
        grade = round(rng.uniform(33, 57), 1) if att in (_PRESENT, _LATE) else None
        diff  = rng.choice([DifficultyEnum.HARD, DifficultyEnum.HARD, DifficultyEnum.MEDIUM])
        eng   = rng.randint(1, 2) if att != _ABSENT else None
        senti = SentimentEnum.NEGATIVE

    elif profile == "excellent":
        att   = rng.choices([_PRESENT, _LATE], weights=[96, 4])[0]
        grade = round(rng.uniform(87, 99), 1)
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.EASY, DifficultyEnum.MEDIUM])
        eng   = rng.randint(4, 5)
        senti = SentimentEnum.POSITIVE

    elif profile == "stable_good":
        att   = rng.choices([_PRESENT, _LATE, _ABSENT], weights=[82, 10, 8])[0]
        grade = round(rng.uniform(72, 87), 1) if att != _ABSENT else None
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.MEDIUM, DifficultyEnum.MEDIUM])
        eng   = rng.randint(3, 5)
        senti = SentimentEnum.POSITIVE

    elif profile == "stable_average":
        att   = rng.choices([_PRESENT, _LATE, _ABSENT, _EXCUSED], weights=[60, 12, 18, 10])[0]
        grade = round(rng.uniform(56, 74), 1) if att in (_PRESENT, _LATE) else None
        diff  = DifficultyEnum.MEDIUM
        eng   = rng.randint(2, 4)
        senti = SentimentEnum.NEUTRAL

    elif profile == "declining":
        if progress < 0.40:
            att   = _PRESENT
            grade = round(rng.uniform(74, 87), 1)
            eng   = rng.randint(3, 5)
            senti = SentimentEnum.POSITIVE
        else:
            att   = rng.choices([_PRESENT, _ABSENT, _LATE], weights=[52, 30, 18])[0]
            grade = round(rng.uniform(42, 62), 1) if att != _ABSENT else None
            eng   = rng.randint(1, 3)
            senti = SentimentEnum.NEGATIVE
        diff = rng.choice([DifficultyEnum.MEDIUM, DifficultyEnum.HARD])

    elif profile == "improving":
        if progress < 0.30:
            att   = rng.choices([_PRESENT, _ABSENT, _LATE], weights=[60, 25, 15])[0]
            grade = round(rng.uniform(45, 63), 1) if att != _ABSENT else None
            eng   = rng.randint(2, 3)
            senti = SentimentEnum.NEUTRAL
        elif progress < 0.65:
            att   = rng.choices([_PRESENT, _LATE, _ABSENT], weights=[72, 16, 12])[0]
            grade = round(rng.uniform(62, 76), 1) if att != _ABSENT else None
            eng   = rng.randint(3, 4)
            senti = SentimentEnum.NEUTRAL
        else:
            att   = rng.choices([_PRESENT, _LATE], weights=[86, 14])[0]
            grade = round(rng.uniform(73, 88), 1)
            eng   = rng.randint(4, 5)
            senti = SentimentEnum.POSITIVE
        diff = DifficultyEnum.MEDIUM

    else:
        att   = _PRESENT
        grade = round(rng.uniform(65, 80), 1)
        diff  = DifficultyEnum.MEDIUM
        eng   = 3
        senti = SentimentEnum.NEUTRAL

    # Feedback only for attended lessons.
    feedback = None
    if att in (_PRESENT, _LATE):
        feedback = rng.choice(_FB.get(profile, _FB["stable_average"]))

    return att, grade, diff, eng, feedback, senti


# ── Metrics calculator ────────────────────────────────────────────────────────

def _compute_metrics(records: list) -> tuple[float, float, str]:
    grades   = [r.grade_value for r in records if r.grade_value is not None]
    avg      = round(sum(grades) / len(grades), 2) if grades else 0.0
    present  = sum(1 for r in records
                   if r.attendance_status in (_PRESENT, _LATE))
    att_rate = round(present / len(records) * 100, 2) if records else 0.0

    if len(grades) >= 4:
        mid        = len(grades) // 2
        first_avg  = sum(grades[:mid]) / mid
        second_avg = sum(grades[mid:]) / (len(grades) - mid)
        delta      = second_avg - first_avg
        trend      = "improving" if delta > 4 else "declining" if delta < -4 else "stable"
    else:
        trend = "stable"

    return avg, att_rate, trend


# ── Registry helpers ──────────────────────────────────────────────────────────

async def _save_registry(db, ids: dict) -> None:
    await db[REGISTRY_COLLECTION].insert_one({
        "seeded_at": datetime.utcnow(),
        "version":   "2.0",
        "collections": {k: list(v) for k, v in ids.items()},
    })


async def _clear(db) -> None:
    entries = await db[REGISTRY_COLLECTION].find({}).to_list(length=None)
    if not entries:
        print("  No demo data found in registry.")
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

    await db[REGISTRY_COLLECTION].delete_many({})
    print(f"\n  Total removed: {total} documents. Registry cleared.")


# ── Main seeder ───────────────────────────────────────────────────────────────

async def seed() -> None:
    do_reseed   = "--reseed" in sys.argv or "--force" in sys.argv
    do_clear    = "--clear" in sys.argv

    print(f"\n  Connecting to {DB_NAME}...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db     = client[DB_NAME]
    await init_beanie(database=db, document_models=ALL_DOCUMENTS)
    print("  Connected.\n")

    if do_clear:
        await _clear(db)
        return

    existing = await db[REGISTRY_COLLECTION].find_one({})
    if existing:
        if not do_reseed:
            print("  Demo data already exists. Use --reseed to regenerate.\n")
            return
        print("  Wiping existing demo data...")
        await _clear(db)
        print()

    ids: dict[str, list] = defaultdict(list)   # tracks every created document ID
    now = datetime.utcnow()
    total_lessons = WEEKS_BACK * LESSONS_PER_WEEK

    # ── 1. Users ──────────────────────────────────────────────────────────────

    admin = User(firebase_uid=_ADMIN["email"], email=_ADMIN["email"],
                 first_name=_ADMIN["first_name"], last_name=_ADMIN["last_name"],
                 role=RoleEnum.ADMIN,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.ADMIN]),
                 is_active=True)
    await admin.insert()
    ids["users"].append(str(admin.id))

    teacher_map: dict[str, User] = {}
    for td in _TEACHERS:
        t = User(firebase_uid=td["email"], email=td["email"],
                 first_name=td["first_name"], last_name=td["last_name"],
                 role=RoleEnum.TEACHER,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.TEACHER]),
                 is_active=True)
        await t.insert()
        teacher_map[td["email"]] = t
        ids["users"].append(str(t.id))

    student_map:  dict[str, User] = {}
    profile_map:  dict[str, str]  = {}
    for sd in _STUDENTS:
        s = User(firebase_uid=sd["email"], email=sd["email"],
                 first_name=sd["first_name"], last_name=sd["last_name"],
                 role=RoleEnum.STUDENT,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.STUDENT]),
                 is_active=True)
        await s.insert()
        student_map[sd["email"]]  = s
        profile_map[sd["email"]]  = sd["profile"]
        ids["users"].append(str(s.id))

    parent_map: dict[str, User] = {}
    for pd in _PARENTS:
        child_email  = _STUDENTS[pd["child"]]["email"]
        child_user   = student_map[child_email]
        p = User(firebase_uid=pd["email"], email=pd["email"],
                 first_name=pd["first_name"], last_name=pd["last_name"],
                 role=RoleEnum.PARENT, linked_student_ids=[str(child_user.id)],
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.PARENT]),
                 is_active=True)
        await p.insert()
        parent_map[pd["email"]] = p
        ids["users"].append(str(p.id))

    print(f"  Users: 1 admin, {len(teacher_map)} teachers, "
          f"{len(student_map)} students, {len(parent_map)} parents.")

    # ── 2. Courses ────────────────────────────────────────────────────────────

    course_map:     dict[str, Course] = {}
    course_subject: dict[str, str]    = {}   # code → subject name
    course_teacher: dict[str, User]   = {}   # code → teacher User

    for cd in _COURSES:
        teacher = teacher_map[cd["teacher_email"]]
        c = Course(code=cd["code"], name=cd["name"],
                   description=cd["name"] + " — demo course.",
                   teacher_id=str(teacher.id), created_by_role="teacher",
                   schedule=cd["schedule"], capacity=cd["capacity"],
                   status=CourseStatusEnum.PUBLISHED)
        await c.insert()
        course_map[cd["code"]]     = c
        course_subject[cd["code"]] = cd["subject"]
        course_teacher[cd["code"]] = teacher
        ids["courses"].append(str(c.id))

    print(f"  Courses: {len(course_map)} created (PUBLISHED).")

    # ── 3. Enrollments ────────────────────────────────────────────────────────

    for s_email, c_code in _ENROLLMENTS:
        e = Enrollment(student_id=str(student_map[s_email].id),
                       course_id=str(course_map[c_code].id),
                       status=EnrollmentStatusEnum.ACTIVE)
        await e.insert()
        ids["enrollments"].append(str(e.id))

    print(f"  Enrollments: {len(_ENROLLMENTS)} created.")

    # ── 4. Academic data: LessonRecord + Grade + Attendance + Feedback ────────

    lesson_count = att_count = grade_count = feedback_count = 0
    all_records: dict[tuple, list] = {}   # (s_email, c_code) → [LessonRecord]

    for s_email, c_code in _ENROLLMENTS:
        student = student_map[s_email]
        course  = course_map[c_code]
        teacher = course_teacher[c_code]
        profile = profile_map[s_email]
        subject = course_subject[c_code]
        cseed   = hash(c_code) % 1000

        # Generate evenly-spaced lesson dates (oldest → newest).
        lesson_dates: list[datetime] = []
        for week in range(WEEKS_BACK - 1, -1, -1):
            base = now - timedelta(weeks=week)
            for ln in range(LESSONS_PER_WEEK):
                lesson_dates.append(
                    base.replace(hour=9 + ln * 4, minute=0, second=0, microsecond=0)
                    - timedelta(days=ln * 3)
                )
        lesson_dates.sort()

        records: list[LessonRecord] = []
        for idx, ldate in enumerate(lesson_dates):
            att, grade, diff, eng, feedback, senti = _lesson_params(
                profile, idx, total_lessons, cseed
            )

            # LessonRecord
            lr = LessonRecord(
                student_id=str(student.id), course_id=str(course.id),
                lesson_date=ldate, attendance_status=att,
                grade_value=grade, teacher_feedback=feedback,
                difficulty_level=diff, engagement_rating=eng,
                created_by_teacher_id=str(teacher.id), created_at=ldate,
            )
            await lr.insert()
            records.append(lr)
            ids["lesson_records"].append(str(lr.id))
            lesson_count += 1

            # Separate Attendance document (used by progress API)
            a = Attendance(
                student_id=str(student.id), course_id=str(course.id),
                date=ldate, status=att,
                remarks=feedback[:60] if feedback and att == _LATE else None,
                created_at=ldate, updated_at=ldate,
            )
            await a.insert()
            ids["attendance"].append(str(a.id))
            att_count += 1

            # Separate Grade document
            if grade is not None:
                g = Grade(
                    student_id=str(student.id), course_id=str(course.id),
                    score=grade, subject=subject,
                    recorded_at=ldate, created_at=ldate, updated_at=ldate,
                )
                await g.insert()
                ids["grades"].append(str(g.id))
                grade_count += 1

            # Separate Feedback document (every other lesson when feedback exists)
            if feedback and idx % 2 == 0:
                fb = Feedback(
                    student_id=str(student.id), course_id=str(course.id),
                    sentiment=senti, content=feedback,
                    submitted_at=ldate, created_at=ldate, updated_at=ldate,
                )
                await fb.insert()
                ids["feedback"].append(str(fb.id))
                feedback_count += 1

        all_records[(s_email, c_code)] = records

    print(f"  Academic data: {lesson_count} lesson records, {att_count} attendance, "
          f"{grade_count} grades, {feedback_count} feedback.")

    # ── 5. Progress Metrics ───────────────────────────────────────────────────

    metrics_map: dict[tuple, ProgressMetrics] = {}
    for (s_email, c_code), records in all_records.items():
        avg, att_rate, trend = _compute_metrics(records)
        m = ProgressMetrics(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            average_grade=avg, attendance_rate=att_rate,
            trend_direction=trend, last_updated=now,
        )
        await m.insert()
        metrics_map[(s_email, c_code)] = m
        ids["progress_metrics"].append(str(m.id))

    print(f"  Progress metrics: {len(metrics_map)} created.")

    # ── 6. Learning Insights ──────────────────────────────────────────────────

    insight_defs = [
        # (student_email, course_code, insight_type, change_pct, summary, prev, curr)
        ("j.rosner@demo.iqplus.dev",    "MATH101", InsightTypeEnum.PERFORMANCE_DECLINE,
         -24.0, "Grade average dropped 24% over the past four weeks.", 71.0, 47.0),
        ("j.rosner@demo.iqplus.dev",    "MATH101", InsightTypeEnum.ATTENDANCE_CONCERN,
         -38.0, "Attendance rate fell from 88% to 50% this month.",    88.0, 50.0),
        ("michal.stern@demo.iqplus.dev","ENG101",  InsightTypeEnum.ATTENDANCE_CONCERN,
         -32.0, "Attendance rate is critically low at 46%.",           78.0, 46.0),
        ("yael.mizrahi@demo.iqplus.dev","MATH101", InsightTypeEnum.PERFORMANCE_DECLINE,
         -19.0, "Declining trend detected — average fell from 82% to 63%.", 82.0, 63.0),
        ("ronen.peretz@demo.iqplus.dev","ENG101",  InsightTypeEnum.PERFORMANCE_DECLINE,
         -16.0, "Performance has dropped steadily over the last 5 weeks.", 77.0, 61.0),
        ("eli.baron@demo.iqplus.dev",   "MATH101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT,
         +21.0, "Grade average improved 21% over the last month.",      54.0, 75.0),
        ("yossi.haim@demo.iqplus.dev",  "ENG101",  InsightTypeEnum.PERFORMANCE_IMPROVEMENT,
         +18.0, "Consistently improving — up from 57% to 75% average.", 57.0, 75.0),
        ("s.weiss@demo.iqplus.dev",     "MATH101", InsightTypeEnum.ATTENDANCE_IMPROVEMENT,
         +12.0, "Perfect attendance maintained for the third month running.", 88.0, 100.0),
    ]

    for s_email, c_code, itype, pct, summary, prev, curr in insight_defs:
        if s_email not in student_map or c_code not in course_map:
            continue
        li = LearningInsight(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            change_percentage=pct, insight_type=itype,
            summary=summary, metric_name="grade_average",
            prev_value=prev, curr_value=curr,
            email_sent=True, created_at=now - timedelta(days=3),
        )
        await li.insert()
        ids["learning_insights"].append(str(li.id))

    print(f"  Learning insights: {len(ids['learning_insights'])} created.")

    # ── 7. AI Alerts ──────────────────────────────────────────────────────────

    alert_defs = [
        # (student_email, course_code, level, message, recommendation)
        ("j.rosner@demo.iqplus.dev", "MATH101", AlertLevelEnum.CRITICAL,
         "Critical: attendance 44%, average grade 46%. Immediate intervention required.",
         "Schedule an urgent parent meeting and arrange supplementary sessions."),
        ("j.rosner@demo.iqplus.dev", "CS101", AlertLevelEnum.WARNING,
         "Below-threshold performance in Programming Fundamentals. Average: 49%.",
         "Provide targeted feedback and recommend peer-study groups."),
        ("michal.stern@demo.iqplus.dev", "ENG101", AlertLevelEnum.CRITICAL,
         "Critical: attendance 46% in English Composition. Core content is being missed.",
         "Contact parent immediately. Review attendance records and explore support options."),
        ("amir.gold2@demo.iqplus.dev", "MATH101", AlertLevelEnum.WARNING,
         "Repeated low scores detected. Three of the last four assessments below 55%.",
         "Assign remedial exercises and schedule a check-in with the student."),
        ("yael.mizrahi@demo.iqplus.dev", "MATH101", AlertLevelEnum.WARNING,
         "Declining trend in Algebra Fundamentals. Average dropped from 82% to 63%.",
         "One-on-one session recommended to identify root cause of decline."),
        ("ronen.peretz@demo.iqplus.dev", "ENG101", AlertLevelEnum.WARNING,
         "Performance declining in English Composition over the past five weeks.",
         "Review written assignments together. Encourage additional reading practice."),
    ]

    alert_objects: list[tuple] = []   # (AIAlert, student_email, course_code)
    for s_email, c_code, level, msg, rec in alert_defs:
        if s_email not in student_map or c_code not in course_map:
            continue
        recs = all_records.get((s_email, c_code), [])
        latest_lr_id = str(recs[-1].id) if recs else None
        al = AIAlert(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            alert_level=level, message=msg, recommendation=rec,
            lesson_record_id=latest_lr_id,
            notification_sent=True,
            parent_seen=False, parent_acknowledged=False,
            created_at=now - timedelta(hours=RNG.randint(1, 48)),
        )
        await al.insert()
        ids["ai_alerts"].append(str(al.id))
        alert_objects.append((al, s_email, c_code))

    print(f"  AI alerts: {len(alert_objects)} created "
          f"({sum(1 for a,_,_ in alert_objects if a.alert_level == AlertLevelEnum.CRITICAL)} critical, "
          f"{sum(1 for a,_,_ in alert_objects if a.alert_level == AlertLevelEnum.WARNING)} warning).")

    # ── 8. Notifications ──────────────────────────────────────────────────────

    notif_count = 0

    # Build a reverse map: student_id → parent User
    student_id_to_parent: dict[str, User] = {}
    for pd in _PARENTS:
        child_email = _STUDENTS[pd["child"]]["email"]
        if child_email in student_map:
            student_id_to_parent[str(student_map[child_email].id)] = parent_map[pd["email"]]

    for alert, s_email, c_code in alert_objects:
        student = student_map[s_email]
        teacher = course_teacher[c_code]
        cname   = course_map[c_code].name
        lvl_str = alert.alert_level.value.upper()

        # Notify the student
        n = Notification(user_id=str(student.id), type=NotificationTypeEnum.AI_ALERT,
                         message=f"[{lvl_str}] {alert.message[:120]}",
                         read_status=False, created_at=alert.created_at)
        await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

        # Notify the teacher
        n = Notification(user_id=str(teacher.id), type=NotificationTypeEnum.AI_ALERT,
                         message=(f"AI Alert for {student.first_name} {student.last_name} "
                                  f"in {cname}: {alert.message[:90]}"),
                         read_status=False, created_at=alert.created_at)
        await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

        # Notify the linked parent
        parent = student_id_to_parent.get(str(student.id))
        if parent:
            n = Notification(user_id=str(parent.id), type=NotificationTypeEnum.AI_ALERT,
                             message=(f"[{lvl_str}] Alert for your child "
                                      f"{student.first_name} in {cname}. "
                                      f"Please review and acknowledge."),
                             read_status=False, created_at=alert.created_at)
            await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

    print(f"  Notifications: {notif_count} created.")

    # ── 9. Weekly Summaries ───────────────────────────────────────────────────

    week_start = now - timedelta(days=now.weekday() + 7)
    for (s_email, c_code), records in all_records.items():
        profile   = profile_map[s_email]
        week_recs = [r for r in records if r.lesson_date >= week_start] or records[-2:]
        present   = sum(1 for r in week_recs if r.attendance_status in (_PRESENT, _LATE))
        absent    = len(week_recs) - present
        wgrades   = [r.grade_value for r in week_recs if r.grade_value is not None]
        wavg      = round(sum(wgrades) / len(wgrades), 2) if wgrades else 0.0
        _, _, trend = _compute_metrics(records)
        highlights  = [r.teacher_feedback for r in week_recs if r.teacher_feedback][:3]
        obs_map = {
            "at_risk":       "Persistent issues require immediate intervention.",
            "declining":     "Notable performance drop; intervention recommended.",
            "stable_average":"Meeting baseline expectations; focused revision advised.",
            "stable_good":   "Strong, consistent performance this week.",
            "improving":     "Positive upward trend continues. Encourage the student.",
            "excellent":     "Exceptional results and engagement this week.",
        }
        ws = WeeklySummary(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            week_start=week_start, attendance_present=present,
            attendance_absent=absent, average_grade=wavg,
            trend_vs_previous=trend, teacher_feedback_highlights=highlights,
            ai_observations=obs_map.get(profile), email_sent=True, created_at=now,
        )
        await ws.insert()
        ids["weekly_summaries"].append(str(ws.id))

    print(f"  Weekly summaries: {len(ids['weekly_summaries'])} created.")

    # ── 10. Course Materials ──────────────────────────────────────────────────

    for c_code, titles in _MATERIALS.items():
        if c_code not in course_map:
            continue
        teacher = course_teacher[c_code]
        for title in titles:
            mat = CourseMaterial(
                course_id=str(course_map[c_code].id),
                title=title, uploaded_by=str(teacher.id),
                file_url=None, link_url=None,
                created_at=now - timedelta(days=RNG.randint(3, 30)),
            )
            await mat.insert()
            ids["course_materials"].append(str(mat.id))

    print(f"  Course materials: {len(ids['course_materials'])} created.")

    # ── 11. Audit Logs ────────────────────────────────────────────────────────

    audit_entries = []
    for cd in _COURSES:
        teacher = teacher_map[cd["teacher_email"]]
        audit_entries.append(AuditLog(
            user_id=str(teacher.id), action="create", resource_type="course",
            resource_id=str(course_map[cd["code"]].id),
            details={"code": cd["code"], "name": cd["name"]},
            timestamp=now - timedelta(days=RNG.randint(14, 60)),
        ))
    for td in _TEACHERS:
        audit_entries.append(AuditLog(
            user_id=str(admin.id), action="register_user",
            resource_type="user", resource_id=str(teacher_map[td["email"]].id),
            details={"role": "teacher", "email": td["email"]},
            timestamp=now - timedelta(days=RNG.randint(60, 90)),
        ))
    for s_email, c_code in _ENROLLMENTS[:12]:
        teacher = course_teacher[c_code]
        audit_entries.append(AuditLog(
            user_id=str(teacher.id), action="approve_enrollment",
            resource_type="enrollment",
            resource_id=str(course_map[c_code].id),
            details={"student": s_email, "course": c_code},
            timestamp=now - timedelta(days=RNG.randint(7, 45)),
        ))

    for entry in audit_entries:
        await entry.insert()
        ids["audit_logs"].append(str(entry.id))

    print(f"  Audit logs: {len(ids['audit_logs'])} created.")

    # ── 12. Save registry ─────────────────────────────────────────────────────

    await _save_registry(db, ids)

    # ── Summary ───────────────────────────────────────────────────────────────

    grand_total = sum(len(v) for v in ids.values())
    _banner()
    print(f"  Database  : {DB_NAME}")
    print(f"  Documents : {grand_total} total across {len(ids)} collections")
    print()
    print(f"  {'Collection':<22} Count")
    print(f"  {'-'*22} -----")
    for coll, doc_ids in sorted(ids.items()):
        print(f"  {coll:<22} {len(doc_ids)}")
    print()
    print("  LOGIN CREDENTIALS  (development — Bearer token = email)")
    print()
    print(f"  {'ROLE':<20}  EMAIL")
    print(f"  {'-'*20}  {'-'*42}")
    _cred("Admin",           _ADMIN["email"])
    for td in _TEACHERS:
        _cred("Teacher",     td["email"])
    for sd in _STUDENTS[:5]:
        _cred(f"Student ({sd['profile']})", sd["email"])
    print(f"  {'...':<20}  (and {len(_STUDENTS)-5} more students — all @demo.iqplus.dev)")
    for pd in _PARENTS[:3]:
        child = _STUDENTS[pd["child"]]
        _cred(f"Parent of {child['first_name']}", pd["email"])
    print(f"  {'...':<20}  (and {len(_PARENTS)-3} more parents)")
    _banner()
    print()
    print("  Critical alerts seeded:")
    for al, s_email, c_code in alert_objects:
        lvl = al.alert_level.value.upper()
        sname = next(s["first_name"] + " " + s["last_name"]
                     for s in _STUDENTS if s["email"] == s_email)
        print(f"    [{lvl:<8}] {sname:<22} → {c_code}")
    print()


def _banner():
    print("\n  " + "=" * 68)


def _cred(role: str, email: str):
    print(f"  {role:<20}  {email}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(seed())
