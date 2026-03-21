#!/usr/bin/env python3
"""
IQ PLUS — Development Data Seeding Script
==========================================
Generates a realistic academic dataset for development and testing.

Usage:
    python scripts/seed_dev_data.py           # abort if seed data exists
    python scripts/seed_dev_data.py --force   # wipe existing seed data, re-seed

Login pattern (development mode only — ENVIRONMENT=development):
    The Bearer token is the user's email address.
    Example:  Authorization: Bearer david.cohen@iqplus.dev

All seeded accounts use the @iqplus.dev domain so they are easy to
identify and safe to wipe with --force without touching real records.
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Bootstrap ─────────────────────────────────────────────────────────────────
# Make the BACK/ directory importable regardless of where the script is called from.
BACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACK_DIR.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.models import (
    ALL_DOCUMENTS,
    User, Course, Enrollment, LessonRecord, ProgressMetrics,
    AIAlert, WeeklySummary, Notification,
    RoleEnum, EnrollmentStatusEnum, AttendanceStatusEnum,
    AlertLevelEnum, NotificationTypeEnum, CourseStatusEnum,
    DifficultyEnum,
)

# ── Configuration ─────────────────────────────────────────────────────────────

MONGODB_URL  = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME      = os.getenv("DB_NAME",     "iqplus_db")
SEED_DOMAIN  = "@iqplus.dev"      # marker that identifies seeded accounts
LESSONS_PER_WEEK = 2              # lessons generated per enrollment per week
WEEKS_BACK       = 10             # how many weeks of lesson history to generate

# Fixed seed so the dataset is reproducible across re-runs without --force.
RNG = random.Random(42)

# ── Teacher feedback pools (per student profile) ──────────────────────────────

_FEEDBACK: dict[str, list[str]] = {
    "at_risk": [
        "Needs to attend more sessions to keep up with the material.",
        "Several key concepts are being missed due to frequent absences.",
        "Struggling with foundational topics — urgent additional support recommended.",
        "Incomplete submissions this week. Please follow up with the student.",
        "Significant comprehension gaps noted; one-on-one review strongly advised.",
        "Attendance is a serious concern; contacted family to discuss options.",
    ],
    "declining": [
        "Performance has dropped noticeably compared to the start of the semester.",
        "Seems less engaged recently; worth checking in about outside factors.",
        "Quality of written work has declined over the past three weeks.",
        "Showed strong results early on but is now clearly falling behind.",
        "Recommend a one-on-one session to identify the root cause of the decline.",
        "Participation in class discussions has dropped significantly.",
    ],
    "excellent": [
        "Outstanding work this week — consistently at the top of the class.",
        "Demonstrates strong conceptual understanding and genuine enthusiasm.",
        "Excellent independent thinking and classroom participation.",
        "Shows real depth of knowledge; a pleasure to teach.",
        "Helped peers understand a difficult concept — great leadership.",
        "Submitted an exceptional project; recommended for advanced enrichment.",
    ],
    "good": [
        "Good grasp of this week's material; minor revision of homework needed.",
        "Solid effort with noticeably improving comprehension. Well done.",
        "A reliable student who consistently delivers quality work.",
        "On track — encouraged to push a little further toward excellence.",
        "Asks thoughtful questions that benefit the whole class.",
        "Strong quiz result this week; keep up the momentum.",
    ],
    "average": [
        "Understands the basics but needs more practice on complex problems.",
        "Attendance is good but depth of understanding could improve.",
        "Steady progress — please revise the last two topics before the exam.",
        "Making a genuine effort; additional study sessions would help.",
        "Reasonable performance overall but clearly capable of more with focus.",
        "Completed all required work; aim for higher accuracy on written tasks.",
    ],
}


# ── Data definitions ──────────────────────────────────────────────────────────

_ADMIN = dict(email="admin@iqplus.dev", first_name="System", last_name="Admin")

_TEACHERS = [
    dict(email="david.cohen@iqplus.dev",   first_name="David",  last_name="Cohen"),
    dict(email="sarah.levy@iqplus.dev",    first_name="Sarah",  last_name="Levy"),
    dict(email="rachel.ben@iqplus.dev",    first_name="Rachel", last_name="Ben-David"),
    dict(email="moshe.gold@iqplus.dev",    first_name="Moshe",  last_name="Goldberg"),
]

_STUDENTS = [
    # profile drives grade ranges, attendance weights, and feedback tone
    dict(email="jonathan.rosner@iqplus.dev", first_name="Jonathan", last_name="Rosner",  profile="at_risk"),
    dict(email="sarah.weiss@iqplus.dev",     first_name="Sarah",    last_name="Weiss",   profile="excellent"),
    dict(email="mam.lahav@iqplus.dev",       first_name="Mam",      last_name="Lahav",   profile="good"),
    dict(email="tom.levi@iqplus.dev",        first_name="Tom",      last_name="Levi",    profile="average"),
    dict(email="dana.cohen@iqplus.dev",      first_name="Dana",     last_name="Cohen",   profile="average"),
    dict(email="yael.mizrahi@iqplus.dev",    first_name="Yael",     last_name="Mizrahi", profile="declining"),
    dict(email="avi.shapiro@iqplus.dev",     first_name="Avi",      last_name="Shapiro", profile="good"),
    dict(email="noa.katz@iqplus.dev",        first_name="Noa",      last_name="Katz",    profile="excellent"),
]

# Each parent entry lists the student emails they are linked to.
_PARENTS = [
    dict(email="parent.rosner@iqplus.dev",  first_name="Michael", last_name="Rosner",
         linked=["jonathan.rosner@iqplus.dev"]),
    dict(email="parent.weiss@iqplus.dev",   first_name="Hanna",   last_name="Weiss",
         linked=["sarah.weiss@iqplus.dev", "mam.lahav@iqplus.dev"]),
    dict(email="parent.mizrahi@iqplus.dev", first_name="Oren",    last_name="Mizrahi",
         linked=["yael.mizrahi@iqplus.dev"]),
]

# Courses: each needs a teacher_email to resolve the teacher ObjectId at runtime.
_COURSES = [
    dict(
        code="MATH101", name="Algebra Fundamentals",
        description="Core algebraic concepts: equations, functions, and graphing techniques.",
        teacher_email="david.cohen@iqplus.dev",
        schedule={"monday": "09:00-10:30", "wednesday": "09:00-10:30"},
        capacity=30,
    ),
    dict(
        code="SCI201", name="Physics Principles",
        description="Introduction to mechanics, energy, waves, and electromagnetism.",
        teacher_email="sarah.levy@iqplus.dev",
        schedule={"tuesday": "11:00-12:30", "thursday": "11:00-12:30"},
        capacity=25,
    ),
    dict(
        code="ENG101", name="English Literature",
        description="Survey of 20th-century prose, poetry, and critical essay writing.",
        teacher_email="rachel.ben@iqplus.dev",
        schedule={"monday": "13:00-14:30", "wednesday": "13:00-14:30"},
        capacity=28,
    ),
    dict(
        code="HIST201", name="World History",
        description="Major civilisations and geopolitical shifts from 1500 CE to the present.",
        teacher_email="moshe.gold@iqplus.dev",
        schedule={"tuesday": "09:00-10:30", "thursday": "09:00-10:30"},
        capacity=30,
    ),
    dict(
        code="MATH201", name="Advanced Mathematics",
        description="Calculus, linear algebra, and probability for advanced learners.",
        teacher_email="david.cohen@iqplus.dev",
        schedule={"monday": "11:00-12:30", "friday": "11:00-12:30"},
        capacity=20,
    ),
]

# (student_email, course_code)
_ENROLLMENTS = [
    # Jonathan — at-risk, two courses (will trigger CRITICAL alert)
    ("jonathan.rosner@iqplus.dev", "MATH101"),
    ("jonathan.rosner@iqplus.dev", "SCI201"),
    # Sarah Weiss — excellent, three courses
    ("sarah.weiss@iqplus.dev",     "MATH101"),
    ("sarah.weiss@iqplus.dev",     "ENG101"),
    ("sarah.weiss@iqplus.dev",     "HIST201"),
    # Mam Lahav — good, three courses
    ("mam.lahav@iqplus.dev",       "MATH101"),
    ("mam.lahav@iqplus.dev",       "SCI201"),
    ("mam.lahav@iqplus.dev",       "ENG101"),
    # Tom Levi — average, two courses
    ("tom.levi@iqplus.dev",        "SCI201"),
    ("tom.levi@iqplus.dev",        "HIST201"),
    # Dana Cohen — average, two courses
    ("dana.cohen@iqplus.dev",      "ENG101"),
    ("dana.cohen@iqplus.dev",      "HIST201"),
    # Yael Mizrahi — declining, two courses (will trigger WARNING alert)
    ("yael.mizrahi@iqplus.dev",    "MATH201"),
    ("yael.mizrahi@iqplus.dev",    "SCI201"),
    # Avi Shapiro — good, two courses
    ("avi.shapiro@iqplus.dev",     "MATH101"),
    ("avi.shapiro@iqplus.dev",     "HIST201"),
    # Noa Katz — excellent, two courses
    ("noa.katz@iqplus.dev",        "MATH201"),
    ("noa.katz@iqplus.dev",        "ENG101"),
]


# ── Lesson parameter generator ────────────────────────────────────────────────

def _lesson_params(
    profile: str,
    week_index: int,
    total_weeks: int,
    course_seed: int,
) -> tuple:
    """
    Return (attendance_status, grade_or_None, difficulty, engagement, feedback_or_None)
    for a single lesson, deterministically based on profile + temporal position.
    """
    progress = week_index / max(total_weeks - 1, 1)   # 0.0 (oldest) → 1.0 (newest)
    rng = random.Random(42 + week_index * 17 + course_seed)

    if profile == "at_risk":
        att = rng.choices(
            [AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.ABSENT,
             AttendanceStatusEnum.EXCUSED, AttendanceStatusEnum.LATE],
            weights=[28, 42, 18, 12],
        )[0]
        grade = round(rng.uniform(34, 57), 1) if att in (
            AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE) else None
        diff  = rng.choice([DifficultyEnum.HARD, DifficultyEnum.HARD, DifficultyEnum.MEDIUM])
        eng   = rng.randint(1, 2) if att != AttendanceStatusEnum.ABSENT else None

    elif profile == "excellent":
        att   = rng.choices([AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE],
                            weights=[96, 4])[0]
        grade = round(rng.uniform(88, 99), 1)
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.EASY, DifficultyEnum.MEDIUM])
        eng   = rng.randint(4, 5)

    elif profile == "good":
        att = rng.choices(
            [AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE,
             AttendanceStatusEnum.ABSENT],
            weights=[82, 10, 8],
        )[0]
        grade = round(rng.uniform(73, 88), 1) if att != AttendanceStatusEnum.ABSENT else None
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.MEDIUM, DifficultyEnum.MEDIUM])
        eng   = rng.randint(3, 5)

    elif profile == "average":
        att = rng.choices(
            [AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE,
             AttendanceStatusEnum.ABSENT, AttendanceStatusEnum.EXCUSED],
            weights=[62, 12, 16, 10],
        )[0]
        grade = round(rng.uniform(58, 76), 1) if att in (
            AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE) else None
        diff  = DifficultyEnum.MEDIUM
        eng   = rng.randint(2, 4)

    elif profile == "declining":
        # First 45 % of the timeline: performing well; remainder: slipping.
        if progress < 0.45:
            att   = AttendanceStatusEnum.PRESENT
            grade = round(rng.uniform(75, 87), 1)
            diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.MEDIUM])
            eng   = rng.randint(3, 5)
        else:
            att = rng.choices(
                [AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.ABSENT,
                 AttendanceStatusEnum.LATE],
                weights=[55, 28, 17],
            )[0]
            grade = round(rng.uniform(43, 62), 1) if att != AttendanceStatusEnum.ABSENT else None
            diff  = rng.choice([DifficultyEnum.MEDIUM, DifficultyEnum.HARD])
            eng   = rng.randint(1, 3)

    else:
        att   = AttendanceStatusEnum.PRESENT
        grade = round(rng.uniform(65, 80), 1)
        diff  = DifficultyEnum.MEDIUM
        eng   = 3

    # Only include teacher feedback when the student was present or late.
    feedback = None
    if att in (AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE):
        feedback = rng.choice(_FEEDBACK.get(profile, _FEEDBACK["average"]))

    return att, grade, diff, eng, feedback


# ── Progress metrics calculator ───────────────────────────────────────────────

def _compute_metrics(records: list[LessonRecord]) -> tuple[float, float, str]:
    """Return (average_grade, attendance_rate_pct, trend_direction) from a list of records."""
    grades = [r.grade_value for r in records if r.grade_value is not None]
    avg_grade = round(sum(grades) / len(grades), 2) if grades else 0.0

    present_statuses = {AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE}
    present = sum(
        1 for r in records
        if (r.attendance_status if isinstance(r.attendance_status, AttendanceStatusEnum)
            else AttendanceStatusEnum(r.attendance_status)) in present_statuses
    )
    att_rate = round(present / len(records) * 100, 2) if records else 0.0

    # Trend: compare first-half vs second-half average grades.
    if len(grades) >= 4:
        mid = len(grades) // 2
        first_avg  = sum(grades[:mid])  / mid
        second_avg = sum(grades[mid:])  / (len(grades) - mid)
        delta = second_avg - first_avg
        trend = "improving" if delta > 4 else "declining" if delta < -4 else "stable"
    else:
        trend = "stable"

    return avg_grade, att_rate, trend


# ── Wipe helper ───────────────────────────────────────────────────────────────

async def _wipe_seed_data() -> None:
    """Delete all documents that were created by this seed script."""
    print("  Wiping existing seed data...")

    # Collect seed user IDs before deletion.
    # Use a raw pymongo-style regex filter — Beanie 1.x doesn't expose .regex() on fields.
    seed_users  = await User.find({"email": {"$regex": SEED_DOMAIN}}).to_list()
    seed_ids    = [str(u.id) for u in seed_users]
    seed_emails = [u.email for u in seed_users]

    if not seed_ids:
        print("  Nothing to wipe.")
        return

    # Courses whose teacher is a seed account.
    seed_courses    = await Course.find({"teacher_id": {"$in": seed_ids}}).to_list()
    seed_course_pks = [c.id for c in seed_courses]   # PydanticObjectId list for $in

    counts: dict[str, int] = {}

    async def _del(model, filt: dict, key: str) -> None:
        result = await model.find(filt).delete()
        counts[key] = getattr(result, "deleted_count", 0)

    await _del(Notification,    {"user_id":    {"$in": seed_ids}},    "notifications")
    await _del(AIAlert,         {"student_id": {"$in": seed_ids}},    "ai_alerts")
    await _del(WeeklySummary,   {"student_id": {"$in": seed_ids}},    "weekly_summaries")
    await _del(ProgressMetrics, {"student_id": {"$in": seed_ids}},    "progress_metrics")
    await _del(LessonRecord,    {"student_id": {"$in": seed_ids}},    "lesson_records")
    await _del(Enrollment,      {"student_id": {"$in": seed_ids}},    "enrollments")

    # Courses — filter by Beanie PydanticObjectId list.
    if seed_course_pks:
        await _del(Course, {"_id": {"$in": seed_course_pks}}, "courses")

    # Users (last)
    result = await User.find({"email": {"$in": seed_emails}}).delete()
    counts["users"] = result.deleted_count if result else 0

    total = sum(counts.values())
    print(f"  Removed {total} documents: {counts}")


# ── Main seeding function ─────────────────────────────────────────────────────

async def seed() -> None:
    force = "--force" in sys.argv

    # Connect and initialise Beanie.
    print(f"\n  Connecting to MongoDB ({DB_NAME})...")
    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client[DB_NAME], document_models=ALL_DOCUMENTS)
    print("  Connected.")

    # Guard: abort if seed data already exists (unless --force).
    existing_admin = await User.find_one({"email": _ADMIN["email"]})
    if existing_admin:
        if not force:
            print(
                "\n  Seed data already exists. Run with --force to wipe and re-seed.\n"
                f"  Detected: {_ADMIN['email']}\n"
            )
            return
        await _wipe_seed_data()

    now = datetime.utcnow()

    # ── 1. Users ──────────────────────────────────────────────────────────────

    # Admin
    admin_user = User(
        firebase_uid=_ADMIN["email"],
        email=_ADMIN["email"],
        first_name=_ADMIN["first_name"],
        last_name=_ADMIN["last_name"],
        role=RoleEnum.ADMIN,
        is_active=True,
    )
    await admin_user.insert()

    # Teachers
    teacher_map: dict[str, User] = {}   # email → User
    for td in _TEACHERS:
        t = User(
            firebase_uid=td["email"],
            email=td["email"],
            first_name=td["first_name"],
            last_name=td["last_name"],
            role=RoleEnum.TEACHER,
            is_active=True,
        )
        await t.insert()
        teacher_map[td["email"]] = t

    # Students
    student_map: dict[str, User] = {}   # email → User
    profile_map: dict[str, str]  = {}   # email → profile name
    for sd in _STUDENTS:
        s = User(
            firebase_uid=sd["email"],
            email=sd["email"],
            first_name=sd["first_name"],
            last_name=sd["last_name"],
            role=RoleEnum.STUDENT,
            is_active=True,
        )
        await s.insert()
        student_map[sd["email"]] = s
        profile_map[sd["email"]] = sd["profile"]

    # Parents — link to their students by resolving IDs.
    parent_map: dict[str, User] = {}
    for pd in _PARENTS:
        linked_ids = [
            str(student_map[e].id)
            for e in pd["linked"]
            if e in student_map
        ]
        p = User(
            firebase_uid=pd["email"],
            email=pd["email"],
            first_name=pd["first_name"],
            last_name=pd["last_name"],
            role=RoleEnum.PARENT,
            linked_student_ids=linked_ids,
            is_active=True,
        )
        await p.insert()
        parent_map[pd["email"]] = p

    print(f"  Created 1 admin, {len(teacher_map)} teachers, "
          f"{len(student_map)} students, {len(parent_map)} parents.")

    # ── 2. Courses ────────────────────────────────────────────────────────────

    course_map: dict[str, Course] = {}   # code → Course
    for cd in _COURSES:
        teacher = teacher_map[cd["teacher_email"]]
        c = Course(
            code=cd["code"],
            name=cd["name"],
            description=cd["description"],
            teacher_id=str(teacher.id),
            created_by_role="teacher",
            schedule=cd["schedule"],
            capacity=cd["capacity"],
            status=CourseStatusEnum.PUBLISHED,
        )
        await c.insert()
        course_map[cd["code"]] = c

    print(f"  Created {len(course_map)} courses (PUBLISHED).")

    # ── 3. Enrollments ────────────────────────────────────────────────────────

    enrollment_map: dict[tuple[str, str], Enrollment] = {}   # (student_email, code) → Enrollment
    for student_email, course_code in _ENROLLMENTS:
        student = student_map[student_email]
        course  = course_map[course_code]
        e = Enrollment(
            student_id=str(student.id),
            course_id=str(course.id),
            status=EnrollmentStatusEnum.ACTIVE,
        )
        await e.insert()
        enrollment_map[(student_email, course_code)] = e

    print(f"  Created {len(enrollment_map)} enrollments.")

    # ── 4. Lesson Records ─────────────────────────────────────────────────────

    total_lessons   = LESSONS_PER_WEEK * WEEKS_BACK
    lesson_records_created = 0

    # Maps (student_email, course_code) → list[LessonRecord] for metrics later.
    all_records: dict[tuple[str, str], list[LessonRecord]] = {}

    for student_email, course_code in _ENROLLMENTS:
        student  = student_map[student_email]
        course   = course_map[course_code]
        profile  = profile_map[student_email]
        teacher  = teacher_map[
            next(cd["teacher_email"] for cd in _COURSES if cd["code"] == course_code)
        ]

        # Spread lesson dates evenly across WEEKS_BACK weeks, LESSONS_PER_WEEK per week.
        # Dates go from oldest → newest (oldest first in list, newest last).
        lesson_dates: list[datetime] = []
        for week in range(WEEKS_BACK - 1, -1, -1):
            base = now - timedelta(weeks=week)
            for lesson_num in range(LESSONS_PER_WEEK):
                offset_days = lesson_num * 3          # space lessons within the week
                offset_hour = RNG.randint(8, 16)      # somewhere during school hours
                lesson_dates.append(
                    base.replace(hour=offset_hour, minute=0, second=0, microsecond=0)
                    - timedelta(days=offset_days)
                )
        lesson_dates.sort()

        course_seed = hash(course_code) % 1000
        records: list[LessonRecord] = []

        for idx, lesson_date in enumerate(lesson_dates):
            att, grade, diff, eng, feedback = _lesson_params(
                profile, idx, total_lessons, course_seed
            )
            r = LessonRecord(
                student_id=str(student.id),
                course_id=str(course.id),
                lesson_date=lesson_date,
                attendance_status=att,
                grade_value=grade,
                teacher_feedback=feedback,
                difficulty_level=diff,
                engagement_rating=eng,
                created_by_teacher_id=str(teacher.id),
                created_at=lesson_date,
            )
            await r.insert()
            records.append(r)
            lesson_records_created += 1

        all_records[(student_email, course_code)] = records

    print(f"  Created {lesson_records_created} lesson records "
          f"({LESSONS_PER_WEEK}/week × {WEEKS_BACK} weeks per enrollment).")

    # ── 5. Progress Metrics ───────────────────────────────────────────────────

    metrics_map: dict[tuple[str, str], ProgressMetrics] = {}
    for (student_email, course_code), records in all_records.items():
        student = student_map[student_email]
        course  = course_map[course_code]
        avg_grade, att_rate, trend = _compute_metrics(records)
        m = ProgressMetrics(
            student_id=str(student.id),
            course_id=str(course.id),
            average_grade=avg_grade,
            attendance_rate=att_rate,
            trend_direction=trend,
            last_updated=now,
        )
        await m.insert()
        metrics_map[(student_email, course_code)] = m

    print(f"  Created {len(metrics_map)} progress metric snapshots.")

    # ── 6. AI Alerts ──────────────────────────────────────────────────────────

    ai_alerts: list[AIAlert] = []

    # Helper — find the course teacher User from a course code.
    def _teacher_for(code: str) -> User:
        email = next(cd["teacher_email"] for cd in _COURSES if cd["code"] == code)
        return teacher_map[email]

    # Helper — most recent lesson record for an enrollment.
    def _latest_record(student_email: str, course_code: str) -> LessonRecord | None:
        recs = all_records.get((student_email, course_code), [])
        return recs[-1] if recs else None

    # CRITICAL — Jonathan Rosner in MATH101 (low attendance + very low grades).
    jonathan = student_map["jonathan.rosner@iqplus.dev"]
    math101  = course_map["MATH101"]
    latest_j = _latest_record("jonathan.rosner@iqplus.dev", "MATH101")
    m_j      = metrics_map[("jonathan.rosner@iqplus.dev", "MATH101")]
    alert_critical = AIAlert(
        student_id=str(jonathan.id),
        course_id=str(math101.id),
        alert_level=AlertLevelEnum.CRITICAL,
        message=(
            f"Critical academic situation detected. Attendance rate is {m_j.attendance_rate:.1f}% "
            f"(threshold: 75%) and average grade is {m_j.average_grade:.1f}% "
            f"(threshold: 60%). Immediate intervention required."
        ),
        recommendation=(
            "Schedule an urgent meeting with the student and their parents. "
            "Arrange supplementary lessons and monitor attendance weekly."
        ),
        lesson_record_id=str(latest_j.id) if latest_j else None,
        notification_sent=True,
        parent_seen=False,
        parent_acknowledged=False,
        created_at=now - timedelta(hours=2),
    )
    await alert_critical.insert()
    ai_alerts.append(alert_critical)

    # WARNING — Jonathan Rosner in SCI201 (low grades alone warrant warning).
    sci201  = course_map["SCI201"]
    latest_j2 = _latest_record("jonathan.rosner@iqplus.dev", "SCI201")
    m_j2      = metrics_map[("jonathan.rosner@iqplus.dev", "SCI201")]
    alert_warning_j = AIAlert(
        student_id=str(jonathan.id),
        course_id=str(sci201.id),
        alert_level=AlertLevelEnum.WARNING,
        message=(
            f"Below-threshold performance in Physics Principles. "
            f"Average grade: {m_j2.average_grade:.1f}%. "
            f"Three of the last five assessments fell below 60%."
        ),
        recommendation=(
            "Recommend additional study sessions and peer tutoring. "
            "Teacher to provide targeted feedback on weak topics."
        ),
        lesson_record_id=str(latest_j2.id) if latest_j2 else None,
        notification_sent=True,
        parent_seen=False,
        parent_acknowledged=False,
        created_at=now - timedelta(hours=5),
    )
    await alert_warning_j.insert()
    ai_alerts.append(alert_warning_j)

    # WARNING — Yael Mizrahi in MATH201 (declining trend).
    yael   = student_map["yael.mizrahi@iqplus.dev"]
    math201 = course_map["MATH201"]
    latest_y = _latest_record("yael.mizrahi@iqplus.dev", "MATH201")
    m_y      = metrics_map[("yael.mizrahi@iqplus.dev", "MATH201")]
    alert_warning_y = AIAlert(
        student_id=str(yael.id),
        course_id=str(math201.id),
        alert_level=AlertLevelEnum.WARNING,
        message=(
            f"Declining performance trend detected in Advanced Mathematics. "
            f"Average grade dropped from ~81% in the first half of the term "
            f"to ~{m_y.average_grade:.1f}% recently. Engagement ratings have also fallen."
        ),
        recommendation=(
            "Arrange a one-on-one check-in session. Review recent lesson records "
            "for patterns in difficulty ratings and consider adjusting lesson pacing."
        ),
        lesson_record_id=str(latest_y.id) if latest_y else None,
        notification_sent=True,
        parent_seen=False,
        parent_acknowledged=False,
        created_at=now - timedelta(days=1),
    )
    await alert_warning_y.insert()
    ai_alerts.append(alert_warning_y)

    print(f"  Created {len(ai_alerts)} AI alerts "
          f"(1 CRITICAL, {len(ai_alerts) - 1} WARNING).")

    # ── 7. Notifications ──────────────────────────────────────────────────────

    notifications_created = 0

    # Notify students about their own alerts.
    student_alert_pairs = [
        (jonathan, alert_critical,  math101),
        (jonathan, alert_warning_j, sci201),
        (yael,     alert_warning_y, math201),
    ]
    for student, alert, course in student_alert_pairs:
        lvl = alert.alert_level.value.upper()
        n = Notification(
            user_id=str(student.id),
            message=(
                f"[{lvl}] {alert.message[:120]} — {alert.recommendation[:80]}"
            ),
            type=NotificationTypeEnum.AI_ALERT,
            read_status=False,
            created_at=alert.created_at,
        )
        await n.insert()
        notifications_created += 1

    # Notify the relevant teachers.
    teacher_alert_pairs = [
        (_teacher_for("MATH101"), alert_critical,  "Algebra Fundamentals",   jonathan),
        (_teacher_for("SCI201"),  alert_warning_j, "Physics Principles",     jonathan),
        (_teacher_for("MATH201"), alert_warning_y, "Advanced Mathematics",   yael),
    ]
    for teacher, alert, course_name, student in teacher_alert_pairs:
        n = Notification(
            user_id=str(teacher.id),
            message=(
                f"AI Alert for {student.first_name} {student.last_name} "
                f"in {course_name}: {alert.message[:100]}"
            ),
            type=NotificationTypeEnum.AI_ALERT,
            read_status=False,
            created_at=alert.created_at,
        )
        await n.insert()
        notifications_created += 1

    # Notify the parent linked to Jonathan (critical case).
    rosner_parent = parent_map.get("parent.rosner@iqplus.dev")
    if rosner_parent:
        n = Notification(
            user_id=str(rosner_parent.id),
            message=(
                f"[CRITICAL] Your child Jonathan Rosner has been flagged in "
                f"Algebra Fundamentals. Please review the AI alert and acknowledge."
            ),
            type=NotificationTypeEnum.AI_ALERT,
            read_status=False,
            created_at=alert_critical.created_at,
        )
        await n.insert()
        notifications_created += 1

    print(f"  Created {notifications_created} notifications.")

    # ── 8. Weekly Summaries ───────────────────────────────────────────────────

    week_start = now - timedelta(days=now.weekday() + 7)   # start of last Monday
    summaries_created = 0

    for (student_email, course_code), records in all_records.items():
        student = student_map[student_email]
        course  = course_map[course_code]
        profile = profile_map[student_email]

        # Select records from the past week only.
        week_records = [r for r in records if r.lesson_date >= week_start]
        if not week_records:
            # If the week slice is empty use the two most recent records as stand-ins
            # so the summary still has meaningful data.
            week_records = records[-2:] if len(records) >= 2 else records

        present_statuses = {AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE}
        present = sum(
            1 for r in week_records
            if (r.attendance_status if isinstance(r.attendance_status, AttendanceStatusEnum)
                else AttendanceStatusEnum(r.attendance_status)) in present_statuses
        )
        absent = len(week_records) - present

        week_grades = [r.grade_value for r in week_records if r.grade_value is not None]
        avg_grade = round(sum(week_grades) / len(week_grades), 2) if week_grades else 0.0

        highlights = [r.teacher_feedback for r in week_records if r.teacher_feedback][:3]
        _, _, trend = _compute_metrics(records)

        # AI observation text derived from the profile.
        ai_obs_map = {
            "at_risk":   "Persistent attendance and performance issues require immediate follow-up.",
            "declining": "Notable performance decline over recent weeks; intervention recommended.",
            "excellent": "Consistently high engagement and outstanding results this week.",
            "good":      "Strong and steady performance; encourage continued effort.",
            "average":   "Meeting baseline expectations; focused revision would raise outcomes.",
        }
        ai_obs = ai_obs_map.get(profile)

        ws = WeeklySummary(
            student_id=str(student.id),
            course_id=str(course.id),
            week_start=week_start,
            attendance_present=present,
            attendance_absent=absent,
            average_grade=avg_grade,
            trend_vs_previous=trend,
            teacher_feedback_highlights=highlights,
            ai_observations=ai_obs,
            email_sent=True,
            created_at=now,
        )
        await ws.insert()
        summaries_created += 1

    print(f"  Created {summaries_created} weekly summaries.")

    # ── Summary ───────────────────────────────────────────────────────────────

    _banner()
    print(f"  Database : {DB_NAME}")
    print(f"  Records  : {lesson_records_created} lesson records "
          f"across {len(_ENROLLMENTS)} enrollments")
    print()
    print("  LOGIN CREDENTIALS  (development mode — Bearer token = email)")
    print()
    print(f"  {'ROLE':<10}  {'EMAIL':<40}  TOKEN")
    print(f"  {'-'*10}  {'-'*40}  {'-'*40}")
    _cred("Admin",  _ADMIN["email"])
    for td in _TEACHERS:
        _cred("Teacher", td["email"])
    for sd in _STUDENTS:
        _cred(f"Student ({sd['profile']})", sd["email"])
    for pd in _PARENTS:
        linked = ", ".join(
            student_map[e].first_name
            for e in pd["linked"] if e in student_map
        )
        _cred(f"Parent ({linked})", pd["email"])
    _banner()
    print()
    print("  Alerts seeded:")
    print(f"    [CRITICAL] jonathan.rosner@iqplus.dev — MATH101 (low att + low grades)")
    print(f"    [WARNING]  jonathan.rosner@iqplus.dev — SCI201  (repeated low grades)")
    print(f"    [WARNING]  yael.mizrahi@iqplus.dev    — MATH201 (declining trend)")
    print()


def _banner() -> None:
    print()
    print("  " + "=" * 66)


def _cred(role: str, email: str) -> None:
    print(f"  {role:<26}  {email:<40}  {email}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(seed())
