#!/usr/bin/env python3
"""
Database seeding script for IQ PLUS.
Creates: Admin, Teacher, Student, Parent + courses + enrollment + parent-student link.
"""
import asyncio
import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../BACK'))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models import (
    ALL_DOCUMENTS, User, Course, Enrollment,
    RoleEnum, CourseStatusEnum, VisibilityScopeEnum, EnrollmentStatusEnum
)

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
DB_NAME     = os.getenv('DB_NAME', 'iqplus_db')

USERS = [
    dict(email='admin@iqplus.com',   firebase_uid='admin@iqplus.com',
         first_name='Admin',   last_name='System',  role=RoleEnum.ADMIN,
         display_name='Admin System'),
    dict(email='teacher@iqplus.com', firebase_uid='teacher@iqplus.com',
         first_name='Sarah',   last_name='Cohen',   role=RoleEnum.TEACHER,
         display_name='Sarah Cohen'),
    dict(email='student@iqplus.com', firebase_uid='student@iqplus.com',
         first_name='David',   last_name='Levi',    role=RoleEnum.STUDENT,
         display_name='David Levi'),
    dict(email='parent@iqplus.com',  firebase_uid='parent@iqplus.com',
         first_name='Rachel',  last_name='Levi',    role=RoleEnum.PARENT,
         display_name='Rachel Levi'),
]

PASSWORDS = {
    'admin@iqplus.com':   'Admin123!',
    'teacher@iqplus.com': 'Teacher123!',
    'student@iqplus.com': 'Student123!',
    'parent@iqplus.com':  'Parent123!',
}

COURSES = [
    dict(
        code="MATH101",
        name="Mathematics — Grade 10",
        description="Algebra, geometry, and trigonometry for Grade 10 students.",
        created_by_role="teacher",
        capacity=30,
        schedule={"days": ["Sunday", "Tuesday", "Thursday"], "start_time": "09:00", "end_time": "10:00"},
        status=CourseStatusEnum.PUBLISHED,
        visibility_scope=VisibilityScopeEnum.SCHOOL_ONLY,
    ),
    dict(
        code="SCI101",
        name="Science — Grade 10",
        description="Physics, chemistry, and biology fundamentals.",
        created_by_role="teacher",
        capacity=28,
        schedule={"days": ["Monday", "Wednesday"], "start_time": "11:00", "end_time": "12:30"},
        status=CourseStatusEnum.PUBLISHED,
        visibility_scope=VisibilityScopeEnum.SCHOOL_ONLY,
    ),
    dict(
        code="ENG101",
        name="English Literature — Grade 10",
        description="Reading comprehension, essay writing, and literature analysis.",
        created_by_role="teacher",
        capacity=25,
        schedule={"days": ["Tuesday", "Thursday"], "start_time": "13:00", "end_time": "14:00"},
        status=CourseStatusEnum.DRAFT,
        visibility_scope=VisibilityScopeEnum.SCHOOL_ONLY,
    ),
]


async def seed():
    logger.info("\n" + "=" * 60)
    logger.info("IQ PLUS Database Seeding")
    logger.info("=" * 60)

    client = AsyncIOMotorClient(MONGODB_URL)
    await init_beanie(database=client[DB_NAME], document_models=ALL_DOCUMENTS)
    logger.info(f"\nConnected to: {DB_NAME}")

    # ── Users ──────────────────────────────────────────────────────────────
    logger.info("\nUsers:")
    created_users = {}
    for u in USERS:
        existing = await User.find_one(User.email == u['email'])
        if existing:
            # Update display_name if missing
            if not existing.display_name and u.get('display_name'):
                await existing.set({'display_name': u['display_name']})
            logger.info(f"  existing  {u['role'].value:<10} {u['email']}")
            created_users[u['role']] = existing
        else:
            user = User(**u, is_active=True)
            await user.insert()
            logger.info(f"  created   {u['role'].value:<10} {u['email']}")
            created_users[u['role']] = user

    teacher = created_users[RoleEnum.TEACHER]
    student = created_users[RoleEnum.STUDENT]
    parent  = created_users[RoleEnum.PARENT]

    # ── Courses ─────────────────────────────────────────────────────────────
    logger.info("\nCourses:")
    created_courses = {}
    for cd in COURSES:
        existing = await Course.find_one(Course.code == cd['code'])
        if existing:
            logger.info(f"  existing  {cd['code']:<12} status={existing.status}")
            created_courses[cd['code']] = existing
        else:
            course = Course(**cd, teacher_id=str(teacher.id))
            await course.insert()
            logger.info(f"  created   {cd['code']:<12} {cd['name']}")
            created_courses[cd['code']] = course

    # ── Enrollment: Student → MATH101 + SCI101 ──────────────────────────────
    logger.info("\nEnrollments:")
    for code in ["MATH101", "SCI101"]:
        course = created_courses[code]
        existing = await Enrollment.find_one(
            Enrollment.student_id == str(student.id),
            Enrollment.course_id == str(course.id)
        )
        if existing:
            logger.info(f"  existing  {student.email} -> {code}")
        else:
            enr = Enrollment(
                student_id=str(student.id),
                course_id=str(course.id),
                status=EnrollmentStatusEnum.ACTIVE,
            )
            await enr.insert()
            logger.info(f"  created   {student.email} -> {code}")

    # ── Parent link → Student ────────────────────────────────────────────────
    logger.info("\nParent-Student link:")
    student_id = str(student.id)
    if student_id not in (parent.linked_student_ids or []):
        await parent.set({'linked_student_ids': [student_id]})
        logger.info(f"  linked    {parent.email} -> {student.email}")
    else:
        logger.info(f"  existing  {parent.email} -> {student.email}")

    # ── Summary ─────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("SEEDING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"\n{'Role':<12} {'Email':<26} {'Password':<14} Dashboard Route")
    logger.info(f"{'-'*12} {'-'*26} {'-'*14} {'-'*20}")
    for u in USERS:
        route = f"/dashboard/{u['role'].value}"
        logger.info(f"{u['role'].value:<12} {u['email']:<26} {PASSWORDS[u['email']]:<14} {route}")
    logger.info("\nAvatar upload: POST /api/me/avatar  (multipart/form-data, field: file)")
    logger.info("Profile update: PUT /api/me/profile\n")

    client.close()


if __name__ == '__main__':
    try:
        asyncio.run(seed())
    except Exception as e:
        logger.error(f"\nSeeding failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
