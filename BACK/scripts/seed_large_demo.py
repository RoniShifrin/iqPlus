#!/usr/bin/env python3
"""
IQ PLUS — Large-Scale Demo Data Seeder
=======================================
Generates a fully populated academic environment for comprehensive testing.

Usage:
    python scripts/seed_large_demo.py           # seed (abort if data exists)
    python scripts/seed_large_demo.py --reseed  # wipe and regenerate
    python scripts/seed_large_demo.py --clear   # wipe only

Fixed test accounts (dev mode — Bearer token = email):
    Admin    : admin.demo@large.iqplus.dev
    Teacher  : teacher.math@large.iqplus.dev
    Student  : student.star@large.iqplus.dev
    Parent   : parent.one@large.iqplus.dev

All demo accounts use @large.iqplus.dev — separate from @demo.iqplus.dev.
Every created document is tracked in _large_demo_registry for safe cleanup.
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
load_dotenv(dotenv_path=BACK_DIR.parent / ".env")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from passlib.context import CryptContext

from app.models import (
    ALL_DOCUMENTS,
    User, Course, Enrollment, Grade, Attendance, Feedback,
    LessonRecord, ProgressMetrics, AIAlert, WeeklySummary,
    Notification, CourseMaterial, LearningInsight, AuditLog,
    PerformanceScore, ScoreHistory, Message, Syllabus, UsabilityFeedback,
    WeeklyTopic, SyllabusStatusEnum,
    RoleEnum, EnrollmentStatusEnum, AttendanceStatusEnum,
    AlertLevelEnum, NotificationTypeEnum, CourseStatusEnum,
    DifficultyEnum, SentimentEnum, InsightTypeEnum,
    FeedbackVisibilityEnum, FeedbackDeliveryEnum,
    MessageTypeEnum, ScoreClassificationEnum, VisibilityScopeEnum,
)

# ── Configuration ─────────────────────────────────────────────────────────────
MONGODB_URL         = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME             = os.getenv("DB_NAME",     "iqplus_db")
REGISTRY_COLLECTION = "_large_demo_registry"
DEMO_DOMAIN         = "@large.iqplus.dev"
WEEKS_BACK          = 14
LESSONS_PER_WEEK    = 3
RNG                 = random.Random(42)

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ROLE_PASSWORDS = {
    RoleEnum.ADMIN:   "Admin123!",
    RoleEnum.TEACHER: "Teacher123!",
    RoleEnum.STUDENT: "Student123!",
    RoleEnum.PARENT:  "Parent123!",
}

_PRESENT = AttendanceStatusEnum.PRESENT
_ABSENT  = AttendanceStatusEnum.ABSENT
_LATE    = AttendanceStatusEnum.LATE
_EXCUSED = AttendanceStatusEnum.EXCUSED

# ── Feedback content pools ────────────────────────────────────────────────────
_FB: dict[str, list[str]] = {
    "at_risk": [
        "Attendance remains a serious concern. Missed core topics this week.",
        "Struggling to follow the material due to repeated absences.",
        "Several assignments incomplete. Urgent parent meeting recommended.",
        "Has not submitted the last two assignments. Please follow up.",
        "Very low participation. Gaps in understanding are widening.",
        "Needs immediate academic support. Falling behind peers significantly.",
        "Absent for the third consecutive lesson. Academic recovery plan needed.",
        "Minimal engagement when present. Intervention is overdue.",
    ],
    "declining": [
        "Performance this week was below what we have come to expect.",
        "Shows less focus compared to earlier in the semester.",
        "Quality of written work has dropped noticeably.",
        "Good potential but recent results do not reflect it.",
        "Encouraged to revise last month's material before the upcoming test.",
        "Participation in discussions has decreased. Check-in suggested.",
        "Homework submission rate has fallen. Follow-up needed.",
        "Recent assessment showed a clear downward trend. Recommend a review session.",
    ],
    "stable_average": [
        "Completing work on time. Accuracy on assessments could improve.",
        "Solid attendance and effort. Conceptual depth needs work.",
        "Understands basics well. Encourage further reading.",
        "Steady performance. Review the exercises from last week.",
        "On track but capable of achieving more with focused revision.",
        "Reasonable results this week. Keep building on the foundations.",
        "Meeting expectations consistently. Stretch goals would be beneficial.",
        "Good classroom behaviour. Written work needs more depth.",
    ],
    "stable_good": [
        "Strong grasp of this week's content. Minor revision on the quiz.",
        "Reliable contributor to classroom discussions. Well done.",
        "Consistently solid work. Aim for stretch goals next term.",
        "Good independent thinking demonstrated in today's assignment.",
        "On track and progressing well. Encourage peer tutoring opportunities.",
        "Excellent homework submission rate. Keep up the momentum.",
        "Above-average performance across all recent assessments.",
        "Demonstrates curiosity and initiative. Great to see.",
    ],
    "improving": [
        "Noticeable improvement in accuracy this week. Great effort.",
        "Attendance and focus have both improved. Keep it up.",
        "Starting to show real confidence in problem-solving.",
        "Recent quiz results show a positive upward trend. Well done.",
        "Clearly putting in extra study time — it shows in the results.",
        "Fantastic progress this month. Ready for the next challenge.",
        "Improvement in both written and verbal contributions. Encouraging.",
        "Consistency is building. Next step: stretch into advanced material.",
    ],
    "excellent": [
        "Outstanding performance. Consistently top of the class.",
        "Excellent analytical work on this week's assignment.",
        "A model of dedication and intellectual curiosity.",
        "Demonstrated exceptional depth of understanding. Impressive.",
        "Helped peers with a difficult concept. Great leadership.",
        "Near-perfect assessment. Recommended for advanced enrichment.",
        "Sets the benchmark for the class. Continue this excellent work.",
        "Insightful contributions to discussion. Exceptional critical thinking.",
    ],
}

# ── Users ─────────────────────────────────────────────────────────────────────
_ADMINS = [
    dict(email="admin.demo@large.iqplus.dev",    first_name="Admin",    last_name="Demo"),
    dict(email="coord.academic@large.iqplus.dev", first_name="Academic", last_name="Coordinator"),
    dict(email="coord.students@large.iqplus.dev", first_name="Student",  last_name="Affairs"),
]

_TEACHERS = [
    dict(email="teacher.math@large.iqplus.dev", first_name="Mark",     last_name="Thompson"),
    dict(email="sarah.morgan@large.iqplus.dev", first_name="Sarah",    last_name="Morgan"),
    dict(email="rachel.chen@large.iqplus.dev",  first_name="Rachel",   last_name="Chen"),
    dict(email="james.hoffman@large.iqplus.dev",first_name="James",    last_name="Hoffman"),
    dict(email="yoav.ben@large.iqplus.dev",     first_name="Yoav",     last_name="Ben-David"),
    dict(email="leah.nir@large.iqplus.dev",     first_name="Leah",     last_name="Nir"),
    dict(email="tal.green@large.iqplus.dev",    first_name="Tal",      last_name="Green"),
    dict(email="oren.malik@large.iqplus.dev",   first_name="Oren",     last_name="Malik"),
    dict(email="noa.barak@large.iqplus.dev",    first_name="Noa",      last_name="Barak"),
    dict(email="avi.silver@large.iqplus.dev",   first_name="Avi",      last_name="Silver"),
]

# 60 students: 12 excellent, 12 stable_good, 10 stable_average, 8 improving, 8 declining, 10 at_risk
_STUDENTS = [
    # ── excellent (index 0–11) ────────────────────────────────────────────────
    dict(email="student.star@large.iqplus.dev", first_name="Emma",    last_name="Sterling",  profile="excellent"),
    dict(email="maya.cohen@large.iqplus.dev",   first_name="Maya",    last_name="Cohen",     profile="excellent"),
    dict(email="ben.anderson@large.iqplus.dev", first_name="Ben",     last_name="Anderson",  profile="excellent"),
    dict(email="sophia.patel@large.iqplus.dev", first_name="Sophia",  last_name="Patel",     profile="excellent"),
    dict(email="daniel.kim@large.iqplus.dev",   first_name="Daniel",  last_name="Kim",       profile="excellent"),
    dict(email="rachel.levy@large.iqplus.dev",  first_name="Rachel",  last_name="Levy",      profile="excellent"),
    dict(email="noah.chen@large.iqplus.dev",    first_name="Noah",    last_name="Chen",      profile="excellent"),
    dict(email="isabela.santos@large.iqplus.dev",first_name="Isabela",last_name="Santos",    profile="excellent"),
    dict(email="lucas.wright@large.iqplus.dev", first_name="Lucas",   last_name="Wright",    profile="excellent"),
    dict(email="aisha.noor@large.iqplus.dev",   first_name="Aisha",   last_name="Noor",      profile="excellent"),
    dict(email="ethan.berg@large.iqplus.dev",   first_name="Ethan",   last_name="Berg",      profile="excellent"),
    dict(email="yui.tanaka@large.iqplus.dev",   first_name="Yui",     last_name="Tanaka",    profile="excellent"),
    # ── stable_good (index 12–23) ─────────────────────────────────────────────
    dict(email="liam.davis@large.iqplus.dev",   first_name="Liam",    last_name="Davis",     profile="stable_good"),
    dict(email="olivia.martin@large.iqplus.dev",first_name="Olivia",  last_name="Martin",    profile="stable_good"),
    dict(email="james.wilson@large.iqplus.dev", first_name="James",   last_name="Wilson",    profile="stable_good"),
    dict(email="hannah.clark@large.iqplus.dev", first_name="Hannah",  last_name="Clark",     profile="stable_good"),
    dict(email="alex.rob@large.iqplus.dev",     first_name="Alex",    last_name="Robinson",  profile="stable_good"),
    dict(email="zoe.garcia@large.iqplus.dev",   first_name="Zoe",     last_name="Garcia",    profile="stable_good"),
    dict(email="ryan.martinez@large.iqplus.dev",first_name="Ryan",    last_name="Martinez",  profile="stable_good"),
    dict(email="claire.thomas@large.iqplus.dev",first_name="Claire",  last_name="Thomas",    profile="stable_good"),
    dict(email="kevin.white@large.iqplus.dev",  first_name="Kevin",   last_name="White",     profile="stable_good"),
    dict(email="priya.kumar@large.iqplus.dev",  first_name="Priya",   last_name="Kumar",     profile="stable_good"),
    dict(email="tom.harris@large.iqplus.dev",   first_name="Tom",     last_name="Harris",    profile="stable_good"),
    dict(email="elena.popova@large.iqplus.dev", first_name="Elena",   last_name="Popova",    profile="stable_good"),
    # ── stable_average (index 24–33) ─────────────────────────────────────────
    dict(email="adam.johnson@large.iqplus.dev", first_name="Adam",    last_name="Johnson",   profile="stable_average"),
    dict(email="mia.taylor@large.iqplus.dev",   first_name="Mia",     last_name="Taylor",    profile="stable_average"),
    dict(email="sam.brown@large.iqplus.dev",    first_name="Sam",     last_name="Brown",     profile="stable_average"),
    dict(email="lily.jones@large.iqplus.dev",   first_name="Lily",    last_name="Jones",     profile="stable_average"),
    dict(email="mark.miller@large.iqplus.dev",  first_name="Mark",    last_name="Miller",    profile="stable_average"),
    dict(email="grace.scott@large.iqplus.dev",  first_name="Grace",   last_name="Scott",     profile="stable_average"),
    dict(email="jake.moore@large.iqplus.dev",   first_name="Jake",    last_name="Moore",     profile="stable_average"),
    dict(email="chloe.lee@large.iqplus.dev",    first_name="Chloe",   last_name="Lee",       profile="stable_average"),
    dict(email="ian.taylor2@large.iqplus.dev",  first_name="Ian",     last_name="Taylor",    profile="stable_average"),
    dict(email="nina.wolf@large.iqplus.dev",    first_name="Nina",    last_name="Wolf",      profile="stable_average"),
    # ── improving (index 34–41) ───────────────────────────────────────────────
    dict(email="carlos.diaz@large.iqplus.dev",  first_name="Carlos",  last_name="Diaz",      profile="improving"),
    dict(email="amber.reyes@large.iqplus.dev",  first_name="Amber",   last_name="Reyes",     profile="improving"),
    dict(email="felix.wang@large.iqplus.dev",   first_name="Felix",   last_name="Wang",      profile="improving"),
    dict(email="sara.ahmed@large.iqplus.dev",   first_name="Sara",    last_name="Ahmed",     profile="improving"),
    dict(email="david.hall@large.iqplus.dev",   first_name="David",   last_name="Hall",      profile="improving"),
    dict(email="luna.hern@large.iqplus.dev",    first_name="Luna",    last_name="Hernandez", profile="improving"),
    dict(email="marcus.lee@large.iqplus.dev",   first_name="Marcus",  last_name="Lee",       profile="improving"),
    dict(email="eva.klein@large.iqplus.dev",    first_name="Eva",     last_name="Klein",     profile="improving"),
    # ── declining (index 42–49) ───────────────────────────────────────────────
    dict(email="oliver.brown@large.iqplus.dev", first_name="Oliver",  last_name="Brown",     profile="declining"),
    dict(email="jessica.adams@large.iqplus.dev",first_name="Jessica", last_name="Adams",     profile="declining"),
    dict(email="michael.ford@large.iqplus.dev", first_name="Michael", last_name="Ford",      profile="declining"),
    dict(email="sofia.romano@large.iqplus.dev", first_name="Sofia",   last_name="Romano",    profile="declining"),
    dict(email="brendan.walsh@large.iqplus.dev",first_name="Brendan", last_name="Walsh",     profile="declining"),
    dict(email="mei.zhou@large.iqplus.dev",     first_name="Mei",     last_name="Zhou",      profile="declining"),
    dict(email="tyler.davis@large.iqplus.dev",  first_name="Tyler",   last_name="Davis",     profile="declining"),
    dict(email="ana.silva@large.iqplus.dev",    first_name="Ana",     last_name="Silva",     profile="declining"),
    # ── at_risk (index 50–59) ─────────────────────────────────────────────────
    dict(email="jay.ross@large.iqplus.dev",     first_name="Jay",     last_name="Ross",      profile="at_risk"),
    dict(email="kim.park@large.iqplus.dev",     first_name="Kim",     last_name="Park",      profile="at_risk"),
    dict(email="alex.jones@large.iqplus.dev",   first_name="Alex",    last_name="Jones",     profile="at_risk"),
    dict(email="nat.foster@large.iqplus.dev",   first_name="Nat",     last_name="Foster",    profile="at_risk"),
    dict(email="tim.reed@large.iqplus.dev",     first_name="Tim",     last_name="Reed",      profile="at_risk"),
    dict(email="cora.bell@large.iqplus.dev",    first_name="Cora",    last_name="Bell",      profile="at_risk"),
    dict(email="den.carr@large.iqplus.dev",     first_name="Den",     last_name="Carr",      profile="at_risk"),
    dict(email="fay.hunt@large.iqplus.dev",     first_name="Fay",     last_name="Hunt",      profile="at_risk"),
    dict(email="gus.price@large.iqplus.dev",    first_name="Gus",     last_name="Price",     profile="at_risk"),
    dict(email="hal.cook@large.iqplus.dev",     first_name="Hal",     last_name="Cook",      profile="at_risk"),
]

# 40 parents. Parent i is linked to student i (for i 0–19) and also to student i+20 (for i 0–19)
# Parents 20-39 are linked to students 40-59 (one child each).
# This means students 0-19 have one parent (who also has a sibling student 20-39),
# and students 40-59 each have a dedicated parent.
_PARENT_NAMES = [
    ("James",       "Sterling"),   # 0  → fixed account, child 0 (Emma Sterling) + child 20 (Adam)
    ("Robert",      "Cohen"),      # 1  → Maya + Liam
    ("Elizabeth",   "Anderson"),   # 2  → Ben + Olivia
    ("Patricia",    "Patel"),      # 3  → Sophia + James W
    ("John",        "Kim"),        # 4  → Daniel + Hannah
    ("Jennifer",    "Levy"),       # 5  → Rachel + Alex
    ("Michael",     "Chen"),       # 6  → Noah + Zoe
    ("Linda",       "Santos"),     # 7  → Isabela + Ryan
    ("William",     "Wright"),     # 8  → Lucas + Claire
    ("Barbara",     "Noor"),       # 9  → Aisha + Kevin
    ("David",       "Berg"),       # 10 → Ethan + Priya
    ("Susan",       "Tanaka"),     # 11 → Yui + Tom
    ("Richard",     "Davis"),      # 12 → Liam (idx12 — wait, mismatch)
    ("Joseph",      "Martin"),     # 13
    ("Thomas",      "Wilson"),     # 14
    ("Charles",     "Clark"),      # 15
    ("Christopher", "Robinson"),   # 16
    ("Daniel",      "Garcia"),     # 17
    ("Matthew",     "Martinez"),   # 18
    ("Anthony",     "Thomas"),     # 19
    # Parents 20-39: one child each (students 40-59)
    ("Mark",        "White"),      # 20 → Oliver (idx42)
    ("Donald",      "Adams"),      # 21 → Jessica
    ("Steven",      "Ford"),       # 22 → Michael F
    ("Paul",        "Romano"),     # 23 → Sofia
    ("Andrew",      "Walsh"),      # 24 → Brendan
    ("Kenneth",     "Zhou"),       # 25 → Mei
    ("George",      "Davis"),      # 26 → Tyler
    ("Kevin",       "Silva"),      # 27 → Ana
    ("Brian",       "Ross"),       # 28 → Jay
    ("Edward",      "Park"),       # 29 → Kim
    ("Ronald",      "Jones"),      # 30 → Alex J
    ("Timothy",     "Foster"),     # 31 → Nat
    ("Jason",       "Reed"),       # 32 → Tim
    ("Jeffrey",     "Bell"),       # 33 → Cora
    ("Ryan",        "Carr"),       # 34 → Den
    ("Jacob",       "Hunt"),       # 35 → Fay
    ("Gary",        "Price"),      # 36 → Gus
    ("Nicholas",    "Cook"),       # 37 → Hal
    ("Eric",        "Diaz"),       # 38 → Carlos (idx34 improving — extra coverage)
    ("Stephen",     "Reyes"),      # 39 → Amber (idx35 improving — extra coverage)
]

# ── Courses (22 courses across 12 subjects) ───────────────────────────────────
_COURSES = [
    dict(code="MATH101", name="Algebra Fundamentals",         subject="Mathematics",
         teacher_email="teacher.math@large.iqplus.dev",
         schedule={"monday": "09:00-10:30", "wednesday": "09:00-10:30"}, capacity=35),
    dict(code="MATH201", name="Advanced Calculus",            subject="Mathematics",
         teacher_email="teacher.math@large.iqplus.dev",
         schedule={"tuesday": "09:00-10:30", "thursday": "09:00-10:30"}, capacity=25),
    dict(code="MATH301", name="Statistics & Probability",     subject="Mathematics",
         teacher_email="sarah.morgan@large.iqplus.dev",
         schedule={"wednesday": "11:00-12:30", "friday": "09:00-10:30"}, capacity=22),
    dict(code="ENG101",  name="English Composition",          subject="English",
         teacher_email="leah.nir@large.iqplus.dev",
         schedule={"monday": "11:00-12:30", "thursday": "11:00-12:30"}, capacity=32),
    dict(code="ENG201",  name="Literature & Analysis",        subject="Literature",
         teacher_email="leah.nir@large.iqplus.dev",
         schedule={"tuesday": "11:00-12:30", "friday": "11:00-12:30"}, capacity=25),
    dict(code="ENG301",  name="Creative Writing",             subject="English",
         teacher_email="tal.green@large.iqplus.dev",
         schedule={"wednesday": "13:00-14:30", "friday": "13:00-14:30"}, capacity=20),
    dict(code="SCI101",  name="General Science",              subject="Science",
         teacher_email="rachel.chen@large.iqplus.dev",
         schedule={"tuesday": "13:00-14:30", "thursday": "13:00-14:30"}, capacity=30),
    dict(code="PHY201",  name="Physics Principles",           subject="Physics",
         teacher_email="rachel.chen@large.iqplus.dev",
         schedule={"monday": "13:00-14:30", "thursday": "15:00-16:30"}, capacity=22),
    dict(code="PHY301",  name="Advanced Physics",             subject="Physics",
         teacher_email="rachel.chen@large.iqplus.dev",
         schedule={"tuesday": "15:00-16:30", "friday": "15:00-16:30"}, capacity=18),
    dict(code="BIO101",  name="Biology Fundamentals",         subject="Biology",
         teacher_email="rachel.chen@large.iqplus.dev",
         schedule={"wednesday": "09:00-10:30", "friday": "11:00-12:30"}, capacity=28),
    dict(code="CHEM101", name="Chemistry Basics",             subject="Chemistry",
         teacher_email="james.hoffman@large.iqplus.dev",
         schedule={"tuesday": "09:00-10:30", "friday": "09:00-10:30"}, capacity=25),
    dict(code="CHEM201", name="Organic Chemistry",            subject="Chemistry",
         teacher_email="james.hoffman@large.iqplus.dev",
         schedule={"monday": "15:00-16:30", "wednesday": "15:00-16:30"}, capacity=18),
    dict(code="CS101",   name="Programming Fundamentals",     subject="Computer Science",
         teacher_email="yoav.ben@large.iqplus.dev",
         schedule={"monday": "09:00-10:30", "thursday": "09:00-10:30"}, capacity=25),
    dict(code="CS201",   name="Data Structures",              subject="Computer Science",
         teacher_email="yoav.ben@large.iqplus.dev",
         schedule={"tuesday": "11:00-12:30", "thursday": "13:00-14:30"}, capacity=20),
    dict(code="CS301",   name="Web Development",              subject="Computer Science",
         teacher_email="yoav.ben@large.iqplus.dev",
         schedule={"wednesday": "11:00-12:30", "friday": "13:00-14:30"}, capacity=18),
    dict(code="HIST101", name="World History",                subject="History",
         teacher_email="oren.malik@large.iqplus.dev",
         schedule={"monday": "11:00-12:30", "wednesday": "13:00-14:30"}, capacity=30),
    dict(code="HIST201", name="Modern History",               subject="History",
         teacher_email="oren.malik@large.iqplus.dev",
         schedule={"tuesday": "13:00-14:30", "friday": "11:00-12:30"}, capacity=22),
    dict(code="GEO101",  name="World Geography",              subject="Geography",
         teacher_email="noa.barak@large.iqplus.dev",
         schedule={"monday": "13:00-14:30", "thursday": "11:00-12:30"}, capacity=25),
    dict(code="ECON101", name="Introduction to Economics",    subject="Economics",
         teacher_email="sarah.morgan@large.iqplus.dev",
         schedule={"tuesday": "09:00-10:30", "thursday": "11:00-12:30"}, capacity=22),
    dict(code="ART101",  name="Visual Arts",                  subject="Arts",
         teacher_email="avi.silver@large.iqplus.dev",
         schedule={"wednesday": "15:00-16:30", "friday": "15:00-16:30"}, capacity=20),
    dict(code="MUS101",  name="Music Theory",                 subject="Music",
         teacher_email="avi.silver@large.iqplus.dev",
         schedule={"tuesday": "15:00-16:30", "thursday": "15:00-16:30"}, capacity=18),
    dict(code="PE101",   name="Physical Education",           subject="Physical Education",
         teacher_email="noa.barak@large.iqplus.dev",
         schedule={"monday": "15:00-16:30", "friday": "09:00-10:30"}, capacity=30),
]

# ── Enrollment assignment ─────────────────────────────────────────────────────
# Core courses (one per student, rotating): every student takes exactly 1
CORE_COURSES = ["MATH101", "ENG101", "HIST101", "SCI101"]
# Standard courses (one per student, rotating among 11)
STD_COURSES  = ["MATH201", "ENG201", "CS101", "CHEM101", "BIO101",
                 "GEO101", "ECON101", "PHY201", "ART101", "MUS101", "PE101"]
# Advanced courses (excellent + stable_good + improving students get one)
ADV_COURSES  = ["MATH301", "ENG301", "PHY301", "CHEM201", "CS201", "CS301", "HIST201"]

# Course materials (3–5 per course)
_MATERIALS: dict[str, list[str]] = {
    "MATH101": ["Week 1–4 Exercise Pack", "Linear Equations Reference Sheet", "Mid-Term Practice Paper", "Final Exam Study Guide"],
    "MATH201": ["Calculus Formula Booklet", "Integration Techniques Worksheet", "Differential Equations Primer", "Final Exam Prep Guide"],
    "MATH301": ["Statistics Fundamentals Handbook", "Probability Cheat Sheet", "Data Analysis Project Brief", "Normal Distribution Tables"],
    "ENG101":  ["Essay Structure Guide", "Grammar & Style Checklist", "Reading Comprehension Drills", "MLA Citation Reference"],
    "ENG201":  ["Literary Analysis Framework", "Annotated Poem Collection", "Critical Essay Rubric", "Author Study Reading List"],
    "ENG301":  ["Creative Writing Prompts Pack", "Narrative Structure Workbook", "Peer Review Checklist", "Portfolio Submission Guidelines"],
    "SCI101":  ["Lab Safety Guidelines", "Unit 1 Revision Notes", "Scientific Method Poster", "Midterm Review Packet"],
    "PHY201":  ["Newton's Laws Summary", "Wave & Optics Problems Set", "Physics Formula Sheet", "Lab Report Template"],
    "PHY301":  ["Quantum Mechanics Intro Notes", "Electromagnetic Fields Worksheet", "Advanced Problem Set", "Research Project Rubric"],
    "BIO101":  ["Cell Biology Diagram Sheet", "Genetics Problem Set", "Ecology Field Notes Template", "Lab Report Template"],
    "CHEM101": ["Periodic Table Poster", "Reaction Types Cheat Sheet", "Lab Report Template", "Balancing Equations Practice"],
    "CHEM201": ["Organic Compounds Reference", "Reaction Mechanisms Guide", "Spectroscopy Notes", "Synthesis Lab Protocol"],
    "CS101":   ["Python Quick Reference", "Algorithm Design Workbook", "Debugging Checklist", "Project Submission Guidelines"],
    "CS201":   ["Data Structures Cheat Sheet", "Big-O Complexity Guide", "Sorting Algorithms Workbook", "Implementation Project Brief"],
    "CS301":   ["HTML/CSS Reference Sheet", "JavaScript Fundamentals", "Responsive Design Checklist", "Final Project Rubric"],
    "HIST101": ["Timeline of World Events", "Primary Source Analysis Guide", "Essay Rubric", "Map of Ancient Civilisations"],
    "HIST201": ["20th Century Events Summary", "Source Critique Framework", "Comparative Essay Template", "Documentary Viewing Guide"],
    "GEO101":  ["World Map Reference", "Climate Zones Poster", "Population Data Sheet", "Case Study Research Template"],
    "ECON101": ["Supply & Demand Diagrams", "GDP & Indicators Reference", "Market Structures Summary", "Economic Policy Analysis Template"],
    "ART101":  ["Colour Theory Wheel", "Perspective Drawing Guide", "Art History Timeline", "Portfolio Submission Checklist"],
    "MUS101":  ["Music Notation Reference", "Chord Progression Chart", "Ear Training Exercises", "Composition Project Brief"],
    "PE101":   ["Fitness Assessment Protocol", "Sports Rules Summary", "Warm-up & Cool-down Guide", "Health & Wellness Reflection Sheet"],
}

# ── Syllabus topics by subject group ─────────────────────────────────────────
_TOPIC_POOL: dict[str, list[tuple]] = {
    "Mathematics": [
        ("Introduction & Core Concepts",        "Foundations of the subject and key terminology",         ["Understand core vocabulary", "Identify key principles"]),
        ("Basic Operations & Notation",          "Fundamental operations and mathematical notation",       ["Apply correct notation", "Perform basic calculations"]),
        ("Equations and Expressions",            "Setting up and solving equations",                       ["Solve linear equations", "Simplify expressions"]),
        ("Functions and Graphs",                 "Understanding functions and their visual representations",["Plot functions", "Identify key features of graphs"]),
        ("Problem-Solving Strategies",           "Structured approaches to complex problems",              ["Apply multi-step reasoning", "Check solutions"]),
        ("Applications in Context",              "Real-world applications of mathematical concepts",       ["Model real scenarios", "Interpret results"]),
        ("Mid-Course Review",                    "Consolidation of weeks 1–6",                             ["Revise key methods", "Complete practice paper"]),
        ("Advanced Techniques I",                "Extending knowledge with more sophisticated methods",    ["Apply advanced procedures", "Solve harder problems"]),
        ("Advanced Techniques II",               "Deeper exploration of complex topics",                   ["Tackle unseen problem types", "Justify solutions"]),
        ("Data Interpretation",                  "Reading and interpreting quantitative data",             ["Analyse charts", "Draw conclusions from data"]),
        ("Proof and Reasoning",                  "Mathematical proof and logical argument",                ["Construct simple proofs", "Identify fallacies"]),
        ("Interdisciplinary Connections",        "Links between mathematics and other subjects",           ["Apply maths in science contexts", "Interpret economic data"]),
        ("Exam Preparation I",                   "Structured revision and past paper practice",            ["Complete timed exercises", "Review weak areas"]),
        ("Exam Preparation II & Final Review",   "Final consolidation and exam technique",                 ["Final practice paper", "Peer marking exercise"]),
    ],
    "English": [
        ("Introduction to Academic Writing",     "Structure, purpose and audience in writing",             ["Identify audience", "Plan a structured essay"]),
        ("Grammar & Style Fundamentals",         "Core grammar rules and developing a personal style",     ["Correct common errors", "Vary sentence structure"]),
        ("Reading Comprehension Strategies",     "Techniques for close and critical reading",              ["Identify implicit meaning", "Annotate texts"]),
        ("Paragraph & Essay Structure",          "Building coherent paragraphs and essays",                ["Write a clear topic sentence", "Link paragraphs effectively"]),
        ("Persuasive & Argumentative Writing",   "Constructing and presenting arguments",                  ["Build an argument", "Counter opposing views"]),
        ("Creative and Descriptive Techniques",  "Using imagery, tone and voice in writing",               ["Employ literary devices", "Develop a distinct voice"]),
        ("Mid-Course Review",                    "Consolidation of core writing skills",                   ["Portfolio review", "Peer critique session"]),
        ("Research & Citation Skills",           "Finding, evaluating and citing sources",                 ["Evaluate source reliability", "Format citations correctly"]),
        ("Literary Analysis",                    "Analysing texts for meaning, theme and technique",       ["Identify themes", "Analyse writer's craft"]),
        ("Genre Study",                          "Exploring conventions of different text types",          ["Compare genres", "Write in a chosen genre"]),
        ("Revision and Editing",                 "Self-editing and improving draft writing",               ["Apply peer feedback", "Refine draft to final copy"]),
        ("Comparative Writing",                  "Comparing and contrasting multiple texts",               ["Write a comparative essay", "Identify common themes"]),
        ("Oral and Presentation Skills",         "Planning and delivering an effective presentation",      ["Deliver a 5-min talk", "Respond to questions"]),
        ("Final Portfolio & Review",             "Completing portfolio and exam preparation",              ["Submit final portfolio", "Complete timed writing task"]),
    ],
    "Sciences": [
        ("Scientific Method & Safety",           "Experimental design and laboratory safety",              ["Design a fair test", "Follow lab protocols"]),
        ("Core Concepts & Terminology",          "Foundational vocabulary and concepts",                   ["Define key terms", "Classify examples"]),
        ("Observation & Measurement",            "Quantitative and qualitative data collection",           ["Use measuring instruments", "Record data accurately"]),
        ("Analysis & Interpretation",            "Processing experimental results",                        ["Create graphs", "Identify trends"]),
        ("Theory in Depth I",                    "Deep dive into first major content area",                ["Explain underlying mechanisms", "Solve theory problems"]),
        ("Theory in Depth II",                   "Continuation of core content",                          ["Apply theory to new contexts", "Predict outcomes"]),
        ("Mid-Course Practical Review",          "Consolidation lab session",                              ["Complete lab report", "Evaluate sources of error"]),
        ("Applications & Real-World Links",      "How science applies to everyday and professional life",  ["Research a real application", "Present findings"]),
        ("Extended Theory III",                  "Advanced content and problem solving",                   ["Tackle complex problems", "Justify conclusions"]),
        ("Quantitative Skills",                  "Calculations and numerical literacy in science",         ["Perform calculations", "Convert units"]),
        ("Environmental & Ethical Dimensions",   "Science in society and ethical considerations",          ["Debate an ethical issue", "Evaluate impact"]),
        ("Interdisciplinary Science",            "Connections between science disciplines",                ["Identify cross-topic links", "Write a synoptic response"]),
        ("Exam Technique & Revision",            "Structured revision and past paper work",                ["Complete a past paper", "Peer mark answers"]),
        ("Final Assessment Preparation",         "Final consolidation and practice",                      ["Identify key formulae", "Final timed assessment"]),
    ],
    "Social Studies": [
        ("Introduction to the Subject",          "Overview of scope, themes and study skills",             ["Map the curriculum", "Practise note-taking"]),
        ("Key Concepts & Frameworks",            "Core theoretical frameworks",                            ["Define key terms", "Apply a framework to a case"]),
        ("Historical/Geographical Context",      "Background knowledge and context",                      ["Create a timeline or map", "Summarise context"]),
        ("Case Study I",                         "In-depth study of a significant case",                   ["Analyse causes", "Evaluate significance"]),
        ("Primary Sources & Evidence",           "Evaluating and using primary sources",                   ["Critique a source", "Build an argument from evidence"]),
        ("Comparative Analysis",                 "Comparing cases, regions or time periods",               ["Write a comparative paragraph", "Identify patterns"]),
        ("Mid-Course Review",                    "Consolidation of material so far",                       ["Practice exam question", "Peer review essays"]),
        ("Case Study II",                        "A second in-depth case study",                           ["Apply analytical framework", "Draw comparisons"]),
        ("Contemporary Connections",             "Linking historical/geographic themes to the present",    ["Research a current event", "Discuss implications"]),
        ("Data & Statistics in Context",         "Quantitative data relevant to the subject",              ["Interpret data sets", "Write a data commentary"]),
        ("Debate & Discussion Skills",           "Structured academic discussion",                         ["Prepare and deliver a viewpoint", "Challenge peers respectfully"]),
        ("Synthesis Across Topics",              "Drawing together themes from across the course",         ["Write a synoptic essay", "Identify overarching themes"]),
        ("Exam Preparation",                     "Past paper practice and revision strategies",            ["Complete timed questions", "Review mark schemes"]),
        ("Final Review & Consolidation",         "Summary of entire course",                               ["Final practice paper", "Individual revision plan"]),
    ],
    "Applied": [
        ("Introduction & Orientation",           "Course overview, tools, materials and expectations",     ["Set up working environment", "Understand course structure"]),
        ("Core Skills I",                        "Foundational skill-building activities",                 ["Complete skill exercise 1", "Reflect on progress"]),
        ("Core Skills II",                       "Continuation of foundational skills",                   ["Apply skills in a guided task", "Peer share work"]),
        ("Project Introduction",                 "Launching the first major project",                     ["Define project scope", "Create a plan"]),
        ("Project Development I",                "Active project work with guidance",                     ["Complete milestone 1", "Teacher check-in"]),
        ("Project Development II",               "Continuing project with increasing independence",        ["Complete milestone 2", "Address feedback"]),
        ("Mid-Course Showcase",                  "Presenting work in progress",                            ["Present to peers", "Give and receive critique"]),
        ("Theory Underpinning Practice",         "Key theoretical concepts supporting practical work",     ["Connect theory to practice", "Write a reflection"]),
        ("Advanced Techniques",                  "Developing more sophisticated skills",                  ["Apply advanced technique", "Experiment independently"]),
        ("Final Project Launch",                 "Beginning the final assessed project",                  ["Define final project", "Research and plan"]),
        ("Final Project Development",            "Independent work on final project",                     ["Complete 70% of project", "Self-assess progress"]),
        ("Refinement & Critique",                "Refining work based on peer and teacher feedback",       ["Revise work", "Document changes"]),
        ("Final Presentation Preparation",       "Preparing to present completed project",                ["Rehearse presentation", "Finalise documentation"]),
        ("Final Assessment & Reflection",        "Submitting and presenting final work",                  ["Submit final project", "Reflect on learning journey"]),
    ],
}

_SUBJECT_TO_TOPIC_GROUP = {
    "Mathematics":          "Mathematics",
    "English":              "English",
    "Literature":           "English",
    "Science":              "Sciences",
    "Physics":              "Sciences",
    "Biology":              "Sciences",
    "Chemistry":            "Sciences",
    "History":              "Social Studies",
    "Geography":            "Social Studies",
    "Economics":            "Social Studies",
    "Computer Science":     "Applied",
    "Arts":                 "Applied",
    "Music":                "Applied",
    "Physical Education":   "Applied",
}


# ── Lesson parameter generator ────────────────────────────────────────────────
def _lesson_params(profile: str, week_index: int, total_weeks: int, cseed: int) -> tuple:
    progress = week_index / max(total_weeks - 1, 1)
    rng = random.Random(42 + week_index * 17 + cseed)

    if profile == "at_risk":
        att   = rng.choices([_PRESENT, _ABSENT, _EXCUSED, _LATE], weights=[26, 44, 18, 12])[0]
        grade = round(rng.uniform(30, 55), 1) if att in (_PRESENT, _LATE) else None
        diff  = rng.choice([DifficultyEnum.HARD, DifficultyEnum.HARD, DifficultyEnum.MEDIUM])
        eng   = rng.randint(1, 2) if att != _ABSENT else None
        senti = SentimentEnum.NEGATIVE

    elif profile == "excellent":
        att   = rng.choices([_PRESENT, _LATE], weights=[96, 4])[0]
        grade = round(rng.uniform(88, 99), 1)
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.EASY, DifficultyEnum.MEDIUM])
        eng   = rng.randint(4, 5)
        senti = SentimentEnum.POSITIVE

    elif profile == "stable_good":
        att   = rng.choices([_PRESENT, _LATE, _ABSENT], weights=[82, 10, 8])[0]
        grade = round(rng.uniform(73, 88), 1) if att != _ABSENT else None
        diff  = rng.choice([DifficultyEnum.EASY, DifficultyEnum.MEDIUM, DifficultyEnum.MEDIUM])
        eng   = rng.randint(3, 5)
        senti = SentimentEnum.POSITIVE

    elif profile == "stable_average":
        att   = rng.choices([_PRESENT, _LATE, _ABSENT, _EXCUSED], weights=[60, 12, 18, 10])[0]
        grade = round(rng.uniform(55, 74), 1) if att in (_PRESENT, _LATE) else None
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
            att   = rng.choices([_PRESENT, _ABSENT, _LATE], weights=[50, 32, 18])[0]
            grade = round(rng.uniform(40, 62), 1) if att != _ABSENT else None
            eng   = rng.randint(1, 3)
            senti = SentimentEnum.NEGATIVE
        diff = rng.choice([DifficultyEnum.MEDIUM, DifficultyEnum.HARD])

    elif profile == "improving":
        if progress < 0.30:
            att   = rng.choices([_PRESENT, _ABSENT, _LATE], weights=[60, 25, 15])[0]
            grade = round(rng.uniform(44, 62), 1) if att != _ABSENT else None
            eng   = rng.randint(2, 3)
            senti = SentimentEnum.NEUTRAL
        elif progress < 0.65:
            att   = rng.choices([_PRESENT, _LATE, _ABSENT], weights=[72, 16, 12])[0]
            grade = round(rng.uniform(62, 76), 1) if att != _ABSENT else None
            eng   = rng.randint(3, 4)
            senti = SentimentEnum.NEUTRAL
        else:
            att   = rng.choices([_PRESENT, _LATE], weights=[86, 14])[0]
            grade = round(rng.uniform(74, 89), 1)
            eng   = rng.randint(4, 5)
            senti = SentimentEnum.POSITIVE
        diff = DifficultyEnum.MEDIUM

    else:
        att   = _PRESENT
        grade = round(rng.uniform(65, 80), 1)
        diff  = DifficultyEnum.MEDIUM
        eng   = 3
        senti = SentimentEnum.NEUTRAL

    feedback = None
    if att in (_PRESENT, _LATE):
        feedback = rng.choice(_FB.get(profile, _FB["stable_average"]))

    return att, grade, diff, eng, feedback, senti


# ── Metrics & score calculators ───────────────────────────────────────────────
def _compute_metrics(records: list) -> tuple[float, float, str]:
    grades   = [r.grade_value for r in records if r.grade_value is not None]
    avg      = round(sum(grades) / len(grades), 2) if grades else 0.0
    present  = sum(1 for r in records if r.attendance_status in (_PRESENT, _LATE))
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


def _sentiment_score(records: list) -> float:
    counts = {SentimentEnum.POSITIVE: 0, SentimentEnum.NEUTRAL: 0, SentimentEnum.NEGATIVE: 0}
    for r in records:
        if hasattr(r, "sentiment"):
            counts[r.sentiment] = counts.get(r.sentiment, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return 50.0
    return round((counts[SentimentEnum.POSITIVE] * 100 + counts[SentimentEnum.NEUTRAL] * 50) / total, 2)


def _classify(score: float) -> ScoreClassificationEnum:
    if score >= 80:
        return ScoreClassificationEnum.EXCELLENT
    if score >= 65:
        return ScoreClassificationEnum.GOOD
    if score >= 50:
        return ScoreClassificationEnum.AVERAGE
    return ScoreClassificationEnum.NEEDS_ATTENTION


def _compute_perf_score(avg_grade: float, att_rate: float, fb_score: float, trend: str) -> tuple[float, ScoreClassificationEnum]:
    trend_score = 80.0 if trend == "improving" else 20.0 if trend == "declining" else 50.0
    composite   = round(avg_grade * 0.50 + att_rate * 0.20 + fb_score * 0.20 + trend_score * 0.10, 2)
    return composite, _classify(composite)


# ── Registry helpers ──────────────────────────────────────────────────────────
async def _save_registry(db, ids: dict) -> None:
    await db[REGISTRY_COLLECTION].insert_one({
        "seeded_at":   datetime.utcnow(),
        "version":     "1.0",
        "collections": {k: list(v) for k, v in ids.items()},
    })


async def _clear(db) -> None:
    entries = await db[REGISTRY_COLLECTION].find({}).to_list(length=None)
    if not entries:
        print("  No large demo data found in registry.")
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
    print(f"\n  Total removed: {total} documents. Large-demo registry cleared.")


# ── Main seeder ───────────────────────────────────────────────────────────────
async def seed() -> None:
    do_reseed = "--reseed" in sys.argv or "--force" in sys.argv
    do_clear  = "--clear"  in sys.argv

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
            print("  Large demo data already exists. Use --reseed to regenerate.\n")
            return
        print("  Wiping existing large demo data...")
        await _clear(db)
        print()

    ids: dict[str, list] = defaultdict(list)
    now          = datetime.utcnow()
    total_lessons = WEEKS_BACK * LESSONS_PER_WEEK

    # ── 1. Users ──────────────────────────────────────────────────────────────
    print("  [1/15] Creating users...")

    admin_list: list[User] = []
    for ad in _ADMINS:
        u = User(firebase_uid=ad["email"], email=ad["email"],
                 first_name=ad["first_name"], last_name=ad["last_name"],
                 role=RoleEnum.ADMIN,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.ADMIN]),
                 is_active=True)
        await u.insert()
        admin_list.append(u)
        ids["users"].append(str(u.id))
    main_admin = admin_list[0]

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
    student_list: list[User]      = []
    for sd in _STUDENTS:
        s = User(firebase_uid=sd["email"], email=sd["email"],
                 first_name=sd["first_name"], last_name=sd["last_name"],
                 role=RoleEnum.STUDENT,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.STUDENT]),
                 is_active=True)
        await s.insert()
        student_map[sd["email"]] = s
        profile_map[sd["email"]] = sd["profile"]
        student_list.append(s)
        ids["users"].append(str(s.id))

    # Build parent linked_student_ids
    # Parents 0–19: 2 children each (student i and student i+20)
    # Parents 20–39: 1 child each (student 40+n for n in 0–19) → students 40–59
    parent_map: dict[str, User] = {}
    for pi, (pfirst, plast) in enumerate(_PARENT_NAMES):
        if pi < 20:
            child_ids = [str(student_list[pi].id), str(student_list[pi + 20].id)]
        else:
            child_ids = [str(student_list[40 + (pi - 20)].id)]
        pemail = (
            "parent.one@large.iqplus.dev" if pi == 0
            else f"p{pi}.{plast.lower().replace('-', '')}@large.iqplus.dev"
        )
        p = User(firebase_uid=pemail, email=pemail,
                 first_name=pfirst, last_name=plast,
                 role=RoleEnum.PARENT, linked_student_ids=child_ids,
                 hashed_password=_pwd.hash(_ROLE_PASSWORDS[RoleEnum.PARENT]),
                 is_active=True)
        await p.insert()
        parent_map[pemail] = p
        ids["users"].append(str(p.id))

    # Reverse map: student_id → list of parent Users
    student_id_to_parents: dict[str, list[User]] = defaultdict(list)
    for p in parent_map.values():
        for sid in p.linked_student_ids:
            student_id_to_parents[sid].append(p)

    print(f"    {len(admin_list)} admins, {len(teacher_map)} teachers, "
          f"{len(student_map)} students, {len(parent_map)} parents.")

    # ── 2. Courses ────────────────────────────────────────────────────────────
    print("  [2/15] Creating courses...")
    course_map:     dict[str, Course] = {}
    course_subject: dict[str, str]    = {}
    course_teacher: dict[str, User]   = {}

    for cd in _COURSES:
        teacher = teacher_map[cd["teacher_email"]]
        c = Course(
            code=cd["code"], name=cd["name"],
            description=f"{cd['name']} — large demo course covering {cd['subject']}.",
            teacher_id=str(teacher.id), created_by_role="teacher",
            schedule=cd["schedule"], capacity=cd["capacity"],
            status=CourseStatusEnum.PUBLISHED,
            visibility_scope=VisibilityScopeEnum.SCHOOL_ONLY,
        )
        await c.insert()
        course_map[cd["code"]]     = c
        course_subject[cd["code"]] = cd["subject"]
        course_teacher[cd["code"]] = teacher
        ids["courses"].append(str(c.id))
    print(f"    {len(course_map)} courses (PUBLISHED).")

    # ── 3. Enrollments ────────────────────────────────────────────────────────
    print("  [3/15] Creating enrollments...")
    enrollments: list[tuple[str, str]] = []  # (student_email, course_code)
    for i, sd in enumerate(_STUDENTS):
        s_email = sd["email"]
        profile = sd["profile"]
        # Core course (one per student)
        core = CORE_COURSES[i % len(CORE_COURSES)]
        # Standard course
        std = STD_COURSES[i % len(STD_COURSES)]
        chosen = [core]
        if std != core:
            chosen.append(std)
        # Advanced course for better-performing students
        if profile in ("excellent", "stable_good", "improving"):
            adv = ADV_COURSES[i % len(ADV_COURSES)]
            if adv not in chosen:
                chosen.append(adv)
        # Fourth course for excellent students
        if profile == "excellent":
            extra = STD_COURSES[(i + 5) % len(STD_COURSES)]
            if extra not in chosen:
                chosen.append(extra)
        for c_code in chosen:
            enrollments.append((s_email, c_code))
            e = Enrollment(
                student_id=str(student_map[s_email].id),
                course_id=str(course_map[c_code].id),
                status=EnrollmentStatusEnum.ACTIVE,
            )
            await e.insert()
            ids["enrollments"].append(str(e.id))

    print(f"    {len(enrollments)} enrollments.")

    # ── 4. Academic data (bulk) ───────────────────────────────────────────────
    print(f"  [4/15] Generating academic data "
          f"({len(enrollments)} enrollments × {total_lessons} lessons)...")

    all_records: dict[tuple, list[LessonRecord]]   = {}
    all_feedback: dict[tuple, list[Feedback]]       = {}
    lesson_count = att_count = grade_count = fb_count = 0

    for s_email, c_code in enrollments:
        student = student_map[s_email]
        course  = course_map[c_code]
        teacher = course_teacher[c_code]
        profile = profile_map[s_email]
        subject = course_subject[c_code]
        cseed   = abs(hash(s_email + c_code)) % 10000

        # Evenly-spaced lesson dates oldest → newest
        lesson_dates: list[datetime] = []
        for week in range(WEEKS_BACK - 1, -1, -1):
            base = now - timedelta(weeks=week)
            for ln in range(LESSONS_PER_WEEK):
                lesson_dates.append(
                    base.replace(hour=8 + ln * 3, minute=0, second=0, microsecond=0)
                    - timedelta(days=ln * 2)
                )
        lesson_dates.sort()

        lr_batch:  list[LessonRecord] = []
        att_batch: list[Attendance]   = []
        grd_batch: list[Grade]        = []
        fb_batch:  list[Feedback]     = []

        for idx, ldate in enumerate(lesson_dates):
            att, grade, diff, eng, feedback, senti = _lesson_params(profile, idx, total_lessons, cseed + idx)

            lr = LessonRecord(
                student_id=str(student.id), course_id=str(course.id),
                lesson_date=ldate, attendance_status=att,
                grade_value=grade, teacher_feedback=feedback,
                difficulty_level=diff, engagement_rating=eng,
                created_by_teacher_id=str(teacher.id), created_at=ldate,
            )
            lr_batch.append(lr)

            att_batch.append(Attendance(
                student_id=str(student.id), course_id=str(course.id),
                date=ldate, status=att,
                remarks=feedback[:60] if feedback and att == _LATE else None,
                created_at=ldate, updated_at=ldate,
            ))

            if grade is not None:
                grd_batch.append(Grade(
                    student_id=str(student.id), course_id=str(course.id),
                    score=grade, subject=subject,
                    recorded_at=ldate, created_at=ldate, updated_at=ldate,
                ))

            if feedback and idx % 2 == 0:
                vis = FeedbackVisibilityEnum.PUBLISHED if idx % 4 == 0 else FeedbackVisibilityEnum.PRIVATE
                fb_batch.append(Feedback(
                    student_id=str(student.id), course_id=str(course.id),
                    sentiment=senti, content=feedback,
                    visibility=vis,
                    delivery_target=FeedbackDeliveryEnum.BOTH if vis == FeedbackVisibilityEnum.PUBLISHED else FeedbackDeliveryEnum.NONE,
                    submitted_at=ldate, created_at=ldate, updated_at=ldate,
                ))

        # Bulk inserts
        await LessonRecord.insert_many(lr_batch)
        await Attendance.insert_many(att_batch)
        if grd_batch:
            await Grade.insert_many(grd_batch)
        if fb_batch:
            await Feedback.insert_many(fb_batch)

        ids["lesson_records"].extend(str(d.id) for d in lr_batch)
        ids["attendance"].extend(str(d.id) for d in att_batch)
        ids["grades"].extend(str(d.id) for d in grd_batch)
        ids["feedback"].extend(str(d.id) for d in fb_batch)

        all_records[(s_email, c_code)]  = lr_batch
        all_feedback[(s_email, c_code)] = fb_batch
        lesson_count += len(lr_batch)
        att_count    += len(att_batch)
        grade_count  += len(grd_batch)
        fb_count     += len(fb_batch)

    print(f"    {lesson_count} lesson records, {att_count} attendance, "
          f"{grade_count} grades, {fb_count} feedback.")

    # ── 5. Progress Metrics ───────────────────────────────────────────────────
    print("  [5/15] Computing progress metrics...")
    metrics_data: dict[tuple, tuple] = {}  # (s_email, c_code) → (avg, att_rate, trend)
    for (s_email, c_code), records in all_records.items():
        avg, att_rate, trend = _compute_metrics(records)
        m = ProgressMetrics(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            average_grade=avg, attendance_rate=att_rate,
            trend_direction=trend, last_updated=now,
        )
        await m.insert()
        ids["progress_metrics"].append(str(m.id))
        metrics_data[(s_email, c_code)] = (avg, att_rate, trend)
    print(f"    {len(ids['progress_metrics'])} progress metrics.")

    # ── 6. Performance Scores + Score History ─────────────────────────────────
    print("  [6/15] Computing performance scores...")
    for (s_email, c_code), (avg, att_rate, trend) in metrics_data.items():
        fbs   = all_feedback.get((s_email, c_code), [])
        fb_sc = _sentiment_score(fbs)
        comp, cls = _compute_perf_score(avg, att_rate, fb_sc, trend)

        ps = PerformanceScore(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            score=comp, classification=cls,
            grade_score=avg, attendance_score=att_rate,
            feedback_score=fb_sc,
            trend_score=80.0 if trend == "improving" else 20.0 if trend == "declining" else 50.0,
            computed_at=now,
        )
        await ps.insert()
        ids["performance_scores"].append(str(ps.id))

        # 5 historical score snapshots (monthly going back)
        hist_batch: list[ScoreHistory] = []
        for month in range(5, 0, -1):
            jitter = RNG.uniform(-8, 8)
            h_score = max(0.0, min(100.0, comp + jitter * month * 0.4))
            hist_batch.append(ScoreHistory(
                student_id=str(student_map[s_email].id),
                course_id=str(course_map[c_code].id),
                score=round(h_score, 2),
                classification=_classify(h_score),
                computed_at=now - timedelta(weeks=month * 4),
            ))
        await ScoreHistory.insert_many(hist_batch)
        ids["score_history"].extend(str(h.id) for h in hist_batch)

    print(f"    {len(ids['performance_scores'])} scores, {len(ids['score_history'])} history entries.")

    # ── 7. Syllabi ────────────────────────────────────────────────────────────
    print("  [7/15] Creating syllabi...")
    for cd in _COURSES:
        c_code   = cd["code"]
        subject  = cd["subject"]
        teacher  = course_teacher[c_code]
        tgroup   = _SUBJECT_TO_TOPIC_GROUP.get(subject, "Applied")
        pool     = _TOPIC_POOL[tgroup]

        topics = []
        for week_num, (title, desc, objectives) in enumerate(pool, start=1):
            topics.append(WeeklyTopic(
                week_number=week_num,
                title=title,
                description=desc,
                objectives=objectives,
                materials=[_MATERIALS[c_code][week_num % len(_MATERIALS[c_code])]],
                assignments=[f"Week {week_num} assignment — submit via portal by Sunday"],
                teacher_notes=f"Week {week_num}: check prior knowledge before introducing {title.lower()}.",
            ))

        completed = list(range(1, WEEKS_BACK + 1))  # weeks 1–14 completed
        syl = Syllabus(
            course_id=str(course_map[c_code].id),
            version=1,
            status=SyllabusStatusEnum.PUBLISHED,
            topics=topics,
            completed_weeks=completed,
            created_by=str(teacher.id),
            created_at=now - timedelta(days=90),
            updated_at=now - timedelta(days=2),
        )
        await syl.insert()
        ids["syllabi"].append(str(syl.id))
    print(f"    {len(ids['syllabi'])} syllabi (14 weekly topics each).")

    # ── 8. Learning Insights ──────────────────────────────────────────────────
    print("  [8/15] Generating learning insights...")

    def _insight(s_email, c_code, itype, pct, summary, prev, curr, days_ago=3):
        return LearningInsight(
            student_id=str(student_map[s_email].id),
            course_id=str(course_map[c_code].id),
            change_percentage=pct, insight_type=itype,
            summary=summary, metric_name="grade_average",
            prev_value=prev, curr_value=curr,
            email_sent=True, created_at=now - timedelta(days=days_ago),
        )

    insight_objs = []
    # Positive trends (excellent/stable_good/improving)
    insight_objs += [
        _insight("student.star@large.iqplus.dev", "MATH101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 14.0, "Grade average up 14% — consistent excellence maintained.", 85.0, 97.0),
        _insight("maya.cohen@large.iqplus.dev",   "ENG101",  InsightTypeEnum.ATTENDANCE_IMPROVEMENT, 10.0, "Perfect attendance for the past 8 weeks.", 90.0, 100.0),
        _insight("carlos.diaz@large.iqplus.dev",  "HIST101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 22.0, "Outstanding improvement — grade up from 51% to 73%.", 51.0, 73.0, 5),
        _insight("amber.reyes@large.iqplus.dev",  "SCI101",  InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 19.0, "Consistent upward trend — up from 54% to 73%.", 54.0, 73.0, 7),
        _insight("felix.wang@large.iqplus.dev",   "MATH101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 18.0, "Improving trajectory confirmed over past 6 weeks.", 57.0, 75.0, 4),
        _insight("sara.ahmed@large.iqplus.dev",   "ENG101",  InsightTypeEnum.ATTENDANCE_IMPROVEMENT, 15.0, "Attendance improved significantly — now above 85%.", 70.0, 85.0, 6),
        _insight("liam.davis@large.iqplus.dev",   "MATH101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 12.0, "Strong performance trajectory. Up from 75% to 87%.", 75.0, 87.0, 2),
        _insight("priya.kumar@large.iqplus.dev",  "MATH301", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 16.0, "Excellent growth in Statistics. Average rose 16%.", 70.0, 86.0, 3),
        _insight("noah.chen@large.iqplus.dev",    "HIST101", InsightTypeEnum.ATTENDANCE_IMPROVEMENT, 8.0,  "Zero absences for 10 consecutive weeks.", 92.0, 100.0, 1),
        _insight("isabela.santos@large.iqplus.dev","SCI101", InsightTypeEnum.PERFORMANCE_IMPROVEMENT, 11.0, "Science assessment scores up significantly this month.", 84.0, 95.0, 2),
    ]
    # Negative trends / concerns (declining / at_risk)
    insight_objs += [
        _insight("jay.ross@large.iqplus.dev",     "HIST101", InsightTypeEnum.PERFORMANCE_DECLINE,   -27.0, "Grade average dropped 27% over the past four weeks.", 68.0, 41.0, 2),
        _insight("jay.ross@large.iqplus.dev",     "HIST101", InsightTypeEnum.ATTENDANCE_CONCERN,    -40.0, "Attendance rate fell from 90% to 50% this month.",    90.0, 50.0, 1),
        _insight("kim.park@large.iqplus.dev",     "SCI101",  InsightTypeEnum.ATTENDANCE_CONCERN,    -35.0, "Attendance critically low at 45%.",                   80.0, 45.0, 3),
        _insight("oliver.brown@large.iqplus.dev", "HIST101", InsightTypeEnum.PERFORMANCE_DECLINE,   -22.0, "Declining trend — average fell from 80% to 58%.",     80.0, 58.0, 4),
        _insight("jessica.adams@large.iqplus.dev","SCI101",  InsightTypeEnum.PERFORMANCE_DECLINE,   -18.0, "Performance has dropped steadily over last 5 weeks.", 75.0, 57.0, 5),
        _insight("michael.ford@large.iqplus.dev", "MATH101", InsightTypeEnum.PERFORMANCE_DECLINE,   -20.0, "Assessment grades declining week on week.",           72.0, 52.0, 3),
        _insight("nat.foster@large.iqplus.dev",   "ENG101",  InsightTypeEnum.ATTENDANCE_CONCERN,    -32.0, "Missed 8 of the last 14 lessons. Urgent follow-up.",  85.0, 43.0, 1),
        _insight("tim.reed@large.iqplus.dev",     "HIST101", InsightTypeEnum.PERFORMANCE_DECLINE,   -25.0, "Three consecutive low assessments. Average now 38%.", 63.0, 38.0, 2),
        _insight("brendan.walsh@large.iqplus.dev","HIST101", InsightTypeEnum.PERFORMANCE_DECLINE,   -17.0, "Engagement and grades dropping in tandem.",           73.0, 56.0, 6),
        _insight("mei.zhou@large.iqplus.dev",     "SCI101",  InsightTypeEnum.ATTENDANCE_CONCERN,    -28.0, "Attendance below 60% — core content being missed.",   88.0, 60.0, 4),
    ]
    for li in insight_objs:
        await li.insert()
        ids["learning_insights"].append(str(li.id))
    print(f"    {len(ids['learning_insights'])} insights "
          f"({sum(1 for i in insight_objs if 'decline' in i.insight_type.value or 'concern' in i.insight_type.value)} concerns, "
          f"{sum(1 for i in insight_objs if 'improvement' in i.insight_type.value)} positive).")

    # ── 9. AI Alerts ──────────────────────────────────────────────────────────
    print("  [9/15] Generating AI alerts...")
    alert_defs = [
        # Critical
        ("jay.ross@large.iqplus.dev",      "HIST101", AlertLevelEnum.CRITICAL,
         "Critical: attendance 50%, average grade 41%. Immediate intervention required.",
         "Schedule urgent parent meeting and arrange supplementary sessions."),
        ("kim.park@large.iqplus.dev",      "SCI101",  AlertLevelEnum.CRITICAL,
         "Critical: attendance 45% in General Science. Core content is being missed.",
         "Contact parent immediately. Review records and explore support options."),
        ("nat.foster@large.iqplus.dev",    "ENG101",  AlertLevelEnum.CRITICAL,
         "Critical: missed 8 of 14 recent lessons. Academic continuity at risk.",
         "Arrange catch-up sessions and notify parent. Consider counselling referral."),
        ("tim.reed@large.iqplus.dev",      "HIST101", AlertLevelEnum.CRITICAL,
         "Critical: average grade 38% — three consecutive failing assessments.",
         "Assign remedial plan. One-on-one teacher session required immediately."),
        # Warning
        ("oliver.brown@large.iqplus.dev",  "HIST101", AlertLevelEnum.WARNING,
         "Performance declining in World History. Average dropped from 80% to 58%.",
         "One-on-one session recommended to identify root cause of decline."),
        ("jessica.adams@large.iqplus.dev", "SCI101",  AlertLevelEnum.WARNING,
         "Declining trend in General Science. Five weeks of consecutive grade drops.",
         "Review written assignments together. Encourage revision of fundamentals."),
        ("michael.ford@large.iqplus.dev",  "MATH101", AlertLevelEnum.WARNING,
         "Assessment grades falling week on week. Average now 52%.",
         "Provide targeted feedback on problem areas. Recommend peer study group."),
        ("brendan.walsh@large.iqplus.dev", "HIST101", AlertLevelEnum.WARNING,
         "Engagement and attendance both declining. Academic risk if trend continues.",
         "Check-in conversation recommended. Notify parent of pattern."),
        ("mei.zhou@large.iqplus.dev",      "SCI101",  AlertLevelEnum.WARNING,
         "Attendance below 60% in General Science. Missing key assessment content.",
         "Contact parent. Provide missed lesson materials and schedule catch-up."),
        # Info
        ("cora.bell@large.iqplus.dev",     "SCI101",  AlertLevelEnum.INFO,
         "Below-average engagement rating for three consecutive lessons.",
         "Check in with student informally. Consider varied learning activities."),
        ("den.carr@large.iqplus.dev",      "MATH101", AlertLevelEnum.INFO,
         "Homework submission rate dropped to 60% over the past two weeks.",
         "Remind student of submission expectations. Brief parent if pattern continues."),
        ("hal.cook@large.iqplus.dev",      "SCI101",  AlertLevelEnum.INFO,
         "Performance score just below average threshold — monitoring recommended.",
         "Continue monitoring. Offer optional revision session."),
    ]

    alert_objects: list[tuple] = []
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
            created_at=now - timedelta(hours=RNG.randint(1, 72)),
        )
        await al.insert()
        ids["ai_alerts"].append(str(al.id))
        alert_objects.append((al, s_email, c_code))

    n_crit = sum(1 for a, _, _ in alert_objects if a.alert_level == AlertLevelEnum.CRITICAL)
    n_warn = sum(1 for a, _, _ in alert_objects if a.alert_level == AlertLevelEnum.WARNING)
    print(f"    {len(alert_objects)} alerts ({n_crit} critical, {n_warn} warning, {len(alert_objects)-n_crit-n_warn} info).")

    # ── 10. Notifications ─────────────────────────────────────────────────────
    print("  [10/15] Creating notifications...")
    notif_count = 0
    for alert, s_email, c_code in alert_objects:
        student = student_map[s_email]
        teacher = course_teacher[c_code]
        cname   = course_map[c_code].name
        lvl_str = alert.alert_level.value.upper()

        n = Notification(user_id=str(student.id), type=NotificationTypeEnum.AI_ALERT,
                         message=f"[{lvl_str}] {alert.message[:120]}",
                         read_status=False, created_at=alert.created_at)
        await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

        n = Notification(user_id=str(teacher.id), type=NotificationTypeEnum.AI_ALERT,
                         message=f"AI Alert for {student.first_name} {student.last_name} in {cname}: {alert.message[:90]}",
                         read_status=False, created_at=alert.created_at)
        await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

        for parent in student_id_to_parents.get(str(student.id), []):
            n = Notification(user_id=str(parent.id), type=NotificationTypeEnum.AI_ALERT,
                             message=f"[{lvl_str}] Alert for your child {student.first_name} in {cname}. Please review.",
                             read_status=False, created_at=alert.created_at)
            await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

    # Enrollment approved notifications for first 30 enrollments
    for s_email, c_code in enrollments[:30]:
        n = Notification(
            user_id=str(student_map[s_email].id),
            type=NotificationTypeEnum.ENROLLMENT_APPROVED,
            message=f"Your enrollment in {course_map[c_code].name} has been approved.",
            read_status=RNG.random() > 0.4,
            created_at=now - timedelta(days=RNG.randint(60, 90)),
        )
        await n.insert(); ids["notifications"].append(str(n.id)); notif_count += 1

    print(f"    {notif_count} notifications.")

    # ── 11. Weekly Summaries ──────────────────────────────────────────────────
    print("  [11/15] Creating weekly summaries...")
    week_start = now - timedelta(days=now.weekday() + 7)
    obs_map = {
        "at_risk":       "Persistent issues require immediate intervention.",
        "declining":     "Notable performance drop; intervention recommended.",
        "stable_average":"Meeting baseline expectations; focused revision advised.",
        "stable_good":   "Strong, consistent performance this week.",
        "improving":     "Positive upward trend continues. Encourage the student.",
        "excellent":     "Exceptional results and engagement this week.",
    }
    for (s_email, c_code), records in all_records.items():
        profile   = profile_map[s_email]
        week_recs = [r for r in records if r.lesson_date >= week_start] or records[-3:]
        present   = sum(1 for r in week_recs if r.attendance_status in (_PRESENT, _LATE))
        absent    = len(week_recs) - present
        wgrades   = [r.grade_value for r in week_recs if r.grade_value is not None]
        wavg      = round(sum(wgrades) / len(wgrades), 2) if wgrades else 0.0
        _, _, trend = _compute_metrics(records)
        highlights  = [r.teacher_feedback for r in week_recs if r.teacher_feedback][:3]
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
    print(f"    {len(ids['weekly_summaries'])} weekly summaries.")

    # ── 12. Course Materials ──────────────────────────────────────────────────
    print("  [12/15] Creating course materials...")
    for c_code, titles in _MATERIALS.items():
        if c_code not in course_map:
            continue
        teacher = course_teacher[c_code]
        for title in titles:
            mat = CourseMaterial(
                course_id=str(course_map[c_code].id),
                title=title, uploaded_by=str(teacher.id),
                file_url=None, link_url=None,
                created_at=now - timedelta(days=RNG.randint(3, 60)),
            )
            await mat.insert()
            ids["course_materials"].append(str(mat.id))
    print(f"    {len(ids['course_materials'])} materials.")

    # ── 13. Messages ──────────────────────────────────────────────────────────
    print("  [13/15] Creating messages...")

    msg_templates = [
        # (sender_role_key, recipient_role_key, subject, content, msg_type)
        ("teacher", "student", "Weekly progress update",
         "Hi {student_name}, I wanted to share your progress this week. Keep up the great work and don't hesitate to reach out if you need support.",
         MessageTypeEnum.ACADEMIC),
        ("teacher", "parent",  "Update on {student_name}'s progress",
         "Dear Parent, I am writing to provide an update on {student_name}'s academic progress. Please feel free to contact me with any questions.",
         MessageTypeEnum.ACADEMIC),
        ("teacher", "student", "Reminder: assignment due Friday",
         "Hi {student_name}, a quick reminder that this week's assignment is due by Friday at 23:59. Please submit via the portal.",
         MessageTypeEnum.GENERAL),
        ("admin",   "teacher", "Upcoming assessment period reminder",
         "Dear {teacher_name}, please ensure all grade records are up to date before the end-of-term assessment window.",
         MessageTypeEnum.ANNOUNCEMENT),
        ("admin",   "student", "Platform update: new features available",
         "Hi {student_name}, we have added new features to your dashboard. Log in to explore your updated progress charts and insights.",
         MessageTypeEnum.ANNOUNCEMENT),
        ("teacher", "parent",  "Attendance concern — {student_name}",
         "Dear Parent, I wanted to flag a concern regarding {student_name}'s recent attendance. Please contact me at your earliest convenience.",
         MessageTypeEnum.ALERT),
    ]

    msg_count = 0
    # Teacher → top students (positive updates)
    for i, (s_email, c_code) in enumerate(enrollments[:25]):
        student  = student_map[s_email]
        teacher  = course_teacher[c_code]
        parents  = student_id_to_parents.get(str(student.id), [])
        sname    = student.first_name + " " + student.last_name
        tname    = teacher.first_name + " " + teacher.last_name

        # Teacher → student
        m = Message(
            sender_id=str(teacher.id), recipient_id=str(student.id),
            subject=f"Progress update — {course_map[c_code].name}",
            content=f"Hi {student.first_name}, just a note to say your recent performance in {course_map[c_code].name} has been impressive. Keep it up!",
            message_type=MessageTypeEnum.ACADEMIC,
            read_status=RNG.random() > 0.5,
            created_at=now - timedelta(days=RNG.randint(1, 14)),
        )
        await m.insert(); ids["messages"].append(str(m.id)); msg_count += 1

        # Teacher → parent (for first 15)
        if i < 15 and parents:
            m = Message(
                sender_id=str(teacher.id), recipient_id=str(parents[0].id),
                subject=f"Update on {sname}'s progress in {course_map[c_code].name}",
                content=f"Dear {parents[0].first_name}, I wanted to share that {sname} is performing well in {course_map[c_code].name}. Their recent assessment scores reflect strong effort and understanding.",
                message_type=MessageTypeEnum.ACADEMIC,
                read_status=RNG.random() > 0.4,
                created_at=now - timedelta(days=RNG.randint(3, 21)),
            )
            await m.insert(); ids["messages"].append(str(m.id)); msg_count += 1

    # Teacher → at-risk student parents (alert messages)
    for al, s_email, c_code in alert_objects[:6]:
        if al.alert_level not in (AlertLevelEnum.CRITICAL, AlertLevelEnum.WARNING):
            continue
        student = student_map[s_email]
        teacher = course_teacher[c_code]
        parents = student_id_to_parents.get(str(student.id), [])
        if not parents:
            continue
        m = Message(
            sender_id=str(teacher.id), recipient_id=str(parents[0].id),
            subject=f"Urgent: Attendance/performance concern — {student.first_name} {student.last_name}",
            content=f"Dear {parents[0].first_name}, I am reaching out to discuss a concern regarding {student.first_name}'s recent attendance and performance in {course_map[c_code].name}. {al.message} I would appreciate the opportunity to discuss this. Please reply to this message or contact the school.",
            message_type=MessageTypeEnum.ALERT,
            read_status=False,
            created_at=now - timedelta(days=RNG.randint(1, 5)),
        )
        await m.insert(); ids["messages"].append(str(m.id)); msg_count += 1

    # Admin announcements to all teachers
    for teacher in list(teacher_map.values())[:5]:
        m = Message(
            sender_id=str(main_admin.id), recipient_id=str(teacher.id),
            subject="End-of-term grade submission deadline",
            content=f"Dear {teacher.first_name}, please ensure all grades and lesson records are finalised by next Friday. Contact the admin office if you have any questions.",
            message_type=MessageTypeEnum.ANNOUNCEMENT,
            read_status=RNG.random() > 0.3,
            created_at=now - timedelta(days=RNG.randint(2, 7)),
        )
        await m.insert(); ids["messages"].append(str(m.id)); msg_count += 1

    print(f"    {msg_count} messages.")

    # ── 14. Usability Feedback ────────────────────────────────────────────────
    print("  [14/15] Creating usability feedback...")
    uf_comments = [
        "The dashboard is very intuitive. I can find everything I need quickly.",
        "Reports are clear and well-organised. Would love PDF export per student.",
        "Navigation is smooth. The alerts system is extremely helpful.",
        "Very impressed by the progress charts. Students love seeing their own data.",
        "Would appreciate a mobile-optimised view for parents.",
        "The notification system keeps me on top of everything. Excellent tool.",
        "Easy to use overall. Some menus could be streamlined.",
        "The weekly summary emails are a great feature for parents.",
        "Grade entry is straightforward. The bulk import would be a useful addition.",
        "Very useful platform. Would benefit from a calendar integration.",
    ]
    uf_batch: list[UsabilityFeedback] = []
    all_users_sample = (
        list(teacher_map.values())[:8] +
        student_list[::6] +
        list(parent_map.values())[::5]
    )
    for idx, user in enumerate(all_users_sample):
        uf_batch.append(UsabilityFeedback(
            user_id=str(user.id),
            report_clarity=RNG.randint(3, 5),
            dashboard_usability=RNG.randint(3, 5),
            navigation_ease=RNG.randint(3, 5),
            comment=uf_comments[idx % len(uf_comments)],
            created_at=now - timedelta(days=RNG.randint(1, 30)),
        ))
    await UsabilityFeedback.insert_many(uf_batch)
    ids["usability_feedback"].extend(str(u.id) for u in uf_batch)
    print(f"    {len(uf_batch)} usability feedback entries.")

    # ── 15. Audit Logs ────────────────────────────────────────────────────────
    print("  [15/15] Creating audit logs...")
    audit_batch: list[AuditLog] = []
    for cd in _COURSES:
        teacher = teacher_map[cd["teacher_email"]]
        audit_batch.append(AuditLog(
            user_id=str(teacher.id), action="create", resource_type="course",
            resource_id=str(course_map[cd["code"]].id),
            details={"code": cd["code"], "name": cd["name"]},
            timestamp=now - timedelta(days=RNG.randint(60, 120)),
        ))
        audit_batch.append(AuditLog(
            user_id=str(teacher.id), action="publish", resource_type="course",
            resource_id=str(course_map[cd["code"]].id),
            details={"code": cd["code"]},
            timestamp=now - timedelta(days=RNG.randint(55, 90)),
        ))
    for td in _TEACHERS:
        audit_batch.append(AuditLog(
            user_id=str(main_admin.id), action="register_user",
            resource_type="user", resource_id=str(teacher_map[td["email"]].id),
            details={"role": "teacher", "email": td["email"]},
            timestamp=now - timedelta(days=RNG.randint(90, 150)),
        ))
    for s_email, c_code in enrollments[:40]:
        teacher = course_teacher[c_code]
        audit_batch.append(AuditLog(
            user_id=str(teacher.id), action="approve_enrollment",
            resource_type="enrollment",
            resource_id=str(course_map[c_code].id),
            details={"student": s_email, "course": c_code},
            timestamp=now - timedelta(days=RNG.randint(60, 90)),
        ))
    for al, s_email, c_code in alert_objects:
        audit_batch.append(AuditLog(
            user_id=str(main_admin.id), action="review_alert",
            resource_type="ai_alert", resource_id=str(al.id),
            details={"level": al.alert_level.value, "student": s_email},
            timestamp=now - timedelta(hours=RNG.randint(2, 48)),
        ))
    await AuditLog.insert_many(audit_batch)
    ids["audit_logs"].extend(str(a.id) for a in audit_batch)
    print(f"    {len(ids['audit_logs'])} audit log entries.")

    # ── Save registry ─────────────────────────────────────────────────────────
    await _save_registry(db, ids)

    # ── Summary ───────────────────────────────────────────────────────────────
    grand_total = sum(len(v) for v in ids.values())
    _banner()
    print(f"  Database   : {DB_NAME}")
    print(f"  Documents  : {grand_total} total across {len(ids)} collections")
    print()
    print(f"  {'Collection':<24} Count")
    print(f"  {'-'*24} -----")
    for coll, doc_ids in sorted(ids.items()):
        print(f"  {coll:<24} {len(doc_ids)}")
    print()
    print("  FIXED TEST ACCOUNTS  (development — Bearer token = email)")
    print()
    print(f"  {'ROLE':<22}  EMAIL")
    print(f"  {'-'*22}  {'-'*46}")
    _cred("Admin",            "admin.demo@large.iqplus.dev")
    _cred("Coordinator",      "coord.academic@large.iqplus.dev")
    _cred("Teacher (Math)",   "teacher.math@large.iqplus.dev")
    _cred("Teacher (CS)",     "yoav.ben@large.iqplus.dev")
    _cred("Student (excellent)","student.star@large.iqplus.dev")
    _cred("Student (at_risk)","jay.ross@large.iqplus.dev")
    _cred("Student (improving)","carlos.diaz@large.iqplus.dev")
    _cred("Parent",           "parent.one@large.iqplus.dev")
    print()
    print(f"  {'PROFILE':<16}  COUNT")
    print(f"  {'-'*16}  -----")
    for profile in ("excellent", "stable_good", "stable_average", "improving", "declining", "at_risk"):
        count = sum(1 for sd in _STUDENTS if sd["profile"] == profile)
        print(f"  {profile:<16}  {count}")
    print()
    print("  Critical / Warning alerts seeded:")
    for al, s_email, c_code in alert_objects:
        if al.alert_level in (AlertLevelEnum.CRITICAL, AlertLevelEnum.WARNING):
            sname = next(sd["first_name"] + " " + sd["last_name"] for sd in _STUDENTS if sd["email"] == s_email)
            print(f"    [{al.alert_level.value.upper():<8}] {sname:<24} -> {c_code}")
    _banner()
    print()


def _banner():
    print("\n  " + "=" * 72)


def _cred(role: str, email: str):
    print(f"  {role:<22}  {email}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(seed())
