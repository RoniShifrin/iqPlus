"""Weekly academic summary + feedback digest scheduler.

Uses APScheduler AsyncIOScheduler.
- Weekly summaries:  every Monday at 07:00 UTC
- Feedback digest:   every Friday  at 16:00 UTC
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


# ── Public lifecycle ──────────────────────────────────────────────────────────

def start_scheduler() -> None:
    _scheduler.add_job(
        _run_weekly_summaries,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        id="weekly_summaries",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_feedback_digest,
        trigger="cron",
        day_of_week="fri",
        hour=16,
        minute=0,
        id="feedback_digest",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — weekly summaries Mon 07:00 UTC, feedback digest Fri 16:00 UTC"
    )


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


# ── Main job ──────────────────────────────────────────────────────────────────

async def _run_weekly_summaries() -> None:
    logger.info("Weekly summary job starting…")
    try:
        from app.models import Enrollment, EnrollmentStatusEnum

        enrollments = await Enrollment.find(
            Enrollment.status == EnrollmentStatusEnum.ACTIVE
        ).to_list()

        week_start = datetime.utcnow() - timedelta(days=7)
        processed = 0
        for e in enrollments:
            await _process_enrollment(e.student_id, e.course_id, week_start)
            processed += 1

        logger.info("Weekly summary job done — %d enrollments processed", processed)
    except Exception as exc:
        logger.error("Weekly summary job failed: %s", exc)


async def _process_enrollment(
    student_id: str, course_id: str, week_start: datetime
) -> None:
    try:
        from app.models import User, RoleEnum, Course, AttendanceStatusEnum
        from app.repositories import (
            LessonRecordRepository, WeeklySummaryRepository,
            UserRepository, AIAlertRepository,
        )
        from app.services.email_service import EmailNotificationService

        records = await LessonRecordRepository.get_by_student_course(
            student_id, course_id, since=week_start
        )
        if not records:
            return

        # Compute attendance stats
        present = sum(
            1 for r in records
            if (r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status)
            in ("present", "late")
        )
        absent = len(records) - present
        grades = [r.grade_value for r in records if r.grade_value is not None]
        avg_grade = sum(grades) / len(grades) if grades else 0.0
        feedback_highlights = [r.teacher_feedback for r in records if r.teacher_feedback][:3]

        # Engagement and difficulty pattern analysis
        engagements = [r.engagement_rating for r in records if r.engagement_rating is not None]
        avg_engagement = sum(engagements) / len(engagements) if engagements else None

        difficulties = [
            (r.difficulty_level.value if hasattr(r.difficulty_level, "value") else r.difficulty_level)
            for r in records if r.difficulty_level is not None
        ]
        hard_pct = (difficulties.count("hard") / len(difficulties) * 100) if difficulties else 0

        # Build academic pattern observations
        pattern_notes: list[str] = []
        if avg_engagement is not None:
            if avg_engagement < 2.5:
                pattern_notes.append(f"Low average engagement this week ({avg_engagement:.1f}/5).")
            elif avg_engagement >= 4:
                pattern_notes.append(f"High engagement observed ({avg_engagement:.1f}/5).")
        if hard_pct > 60:
            pattern_notes.append(f"{hard_pct:.0f}% of lessons rated as difficult — may need support.")
        if absent > 0 and (absent / len(records)) > 0.5:
            pattern_notes.append("More than half of sessions were missed this week.")

        from app.repositories import ProgressMetricsRepository
        metrics = await ProgressMetricsRepository.get(student_id, course_id)
        trend = metrics.trend_direction if metrics else "stable"

        # Latest AI observation for this course
        recent_alerts = await AIAlertRepository.list_by_student_course(
            student_id, course_id, limit=1
        )
        ai_obs_parts = []
        if recent_alerts:
            ai_obs_parts.append(recent_alerts[0].message)
        ai_obs_parts.extend(pattern_notes)
        ai_obs = " ".join(ai_obs_parts) if ai_obs_parts else None

        summary = await WeeklySummaryRepository.create(
            student_id=student_id,
            course_id=course_id,
            week_start=week_start,
            attendance_present=present,
            attendance_absent=absent,
            average_grade=avg_grade,
            trend_vs_previous=trend,
            teacher_feedback_highlights=feedback_highlights,
            ai_observations=ai_obs,
            email_sent=False,
        )

        student = await UserRepository.get_by_id(student_id)
        course = await Course.get(course_id)
        if not student or not course:
            return

        recipients: list[str] = []

        # Teacher
        teacher = await UserRepository.get_by_id(course.teacher_id)
        if teacher:
            recipients.append(teacher.email)

        # Parents linked to this student — query only parents with this student linked
        parents = await User.find(
            User.role == RoleEnum.PARENT,
            {"linked_student_ids": student_id}
        ).to_list()
        for p in parents:
            recipients.append(p.email)

        for email in recipients:
            EmailNotificationService.send_weekly_report(
                recipient_email=email,
                student_name=student.full_name(),
                course_name=course.name,
                present=present,
                absent=absent,
                avg_grade=avg_grade,
                trend=trend,
                feedback_highlights=feedback_highlights,
                ai_observations=ai_obs,
            )

        await summary.set({"email_sent": bool(recipients)})

    except Exception as exc:
        logger.error(
            "Failed processing enrollment student=%s course=%s: %s",
            student_id, course_id, exc,
        )


# ── Feedback digest job ───────────────────────────────────────────────────────

async def _run_feedback_digest() -> None:
    """Every Friday: email a grouped feedback digest to students/parents based on delivery_target."""
    logger.info("Feedback digest job starting…")
    try:
        from app.models import Feedback, FeedbackDeliveryEnum, User, RoleEnum, Course
        from app.services.email_service import EmailNotificationService

        week_start = datetime.utcnow() - timedelta(days=7)

        # Fetch all feedback submitted in the past week that has a delivery target
        feedbacks = await Feedback.find(
            Feedback.submitted_at >= week_start,
            {"delivery_target": {"$ne": FeedbackDeliveryEnum.NONE.value}},
        ).to_list()

        if not feedbacks:
            logger.info("Feedback digest: no pending feedback this week.")
            return

        # Group by (student_id, course_id, delivery_target)
        from collections import defaultdict
        groups: dict = defaultdict(list)
        for f in feedbacks:
            dt = f.delivery_target.value if hasattr(f.delivery_target, "value") else f.delivery_target
            groups[(f.student_id, f.course_id, dt)].append(f)

        sent_total = 0
        for (student_id, course_id, delivery), items in groups.items():
            try:
                student = await User.get(student_id)
                course = await Course.get(course_id)
                if not student or not course:
                    continue

                lines = "".join(
                    f"<li><strong>{i.sentiment.value if hasattr(i.sentiment,'value') else i.sentiment}:</strong> {i.content}</li>"
                    for i in items
                )
                html = (
                    f"<h2>Weekly Feedback Digest — {student.full_name()}</h2>"
                    f"<p><strong>Course:</strong> {course.name}</p>"
                    f"<ul>{lines}</ul>"
                )
                subject = f"IQ PLUS — Weekly Feedback: {student.full_name()} / {course.name}"

                recipients: list[str] = []
                if delivery in ("student", "both"):
                    recipients.append(student.email)
                if delivery in ("parent", "both"):
                    # Query only parents linked to this student, not all parents
                    parents = await User.find(
                        User.role == RoleEnum.PARENT,
                        {"linked_student_ids": student_id}
                    ).to_list()
                    for p in parents:
                        recipients.append(p.email)

                for email in recipients:
                    EmailNotificationService.send_email(
                        recipient=email, subject=subject, html_content=html
                    )
                    sent_total += 1
            except Exception as exc:
                logger.error("Feedback digest group error: %s", exc)

        logger.info("Feedback digest job done — %d emails queued.", sent_total)
    except Exception as exc:
        logger.error("Feedback digest job failed: %s", exc)
