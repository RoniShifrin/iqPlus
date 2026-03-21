"""Business logic services"""
from datetime import datetime
from typing import List, Optional, Tuple
import logging

from app.models import (
    User, Course, Enrollment, LearningInsight,
    RoleEnum, EnrollmentStatusEnum, InsightTypeEnum,
    AIAlert, AlertLevelEnum, NotificationTypeEnum,
)
from app.repositories import (
    CourseRepository, EnrollmentRepository, GradeRepository,
    AttendanceRepository, LearningInsightRepository,
    NotificationRepository, FeedbackRepository,
)

logger = logging.getLogger(__name__)


class EnrollmentService:
    @staticmethod
    async def check_schedule_conflict(student_id: str, new_course: Course) -> Optional[dict]:
        """
        Returns None if no conflict, or a dict with conflict details if a real
        day-and-time overlap is found against the student's active enrollments.

        Returned dict keys: course_name, day, start_time, end_time
        (all from the already-enrolled conflicting course)
        """
        enrollments = await EnrollmentRepository.list_by_student(student_id)

        if not enrollments or not new_course.schedule:
            return None

        # Extract days and times from the new course's schedule dict
        new_days  = new_course.schedule.get("days") or []
        new_start = new_course.schedule.get("start_time")
        new_end   = new_course.schedule.get("end_time")

        # Cannot determine an overlap without days and both time boundaries
        if not new_days or not new_start or not new_end:
            return None

        for enrollment in enrollments:
            if enrollment.status != EnrollmentStatusEnum.ACTIVE:
                continue

            enrolled_course = await CourseRepository.get_by_id(enrollment.course_id)
            if not enrolled_course or not enrolled_course.schedule:
                continue

            enrolled_days  = enrolled_course.schedule.get("days") or []
            enrolled_start = enrolled_course.schedule.get("start_time")
            enrolled_end   = enrolled_course.schedule.get("end_time")

            if not enrolled_days or not enrolled_start or not enrolled_end:
                continue

            # Only conflicts if they share at least one day
            shared_days = set(new_days) & set(enrolled_days)
            if not shared_days:
                continue

            # Time overlap: startA < endB AND startB < endA
            # HH:MM strings compare correctly lexicographically for 24-hour format
            if new_start < enrolled_end and enrolled_start < new_end:
                return {
                    "course_id": str(enrolled_course.id),
                    "course_name": enrolled_course.name,
                    "day": sorted(shared_days)[0],
                    "start_time": enrolled_start,
                    "end_time": enrolled_end,
                }

        return None

    @staticmethod
    async def enroll_student(student_id: str, course_id: str) -> Tuple[Optional[Enrollment], Optional[str]]:
        existing = await EnrollmentRepository.get_by_student_course(student_id, course_id)
        if existing:
            return None, "Student already enrolled in this course"

        course = await CourseRepository.get_by_id(course_id)
        if not course:
            return None, "Course not found"

        active_count = await EnrollmentRepository.count_active(course_id)
        if active_count >= course.capacity:
            return None, "Course is at capacity"

        conflict = await EnrollmentService.check_schedule_conflict(student_id, course)
        if conflict:
            return None, f"Schedule conflict: already enrolled in '{conflict['course_name']}' at that time"

        try:
            enrollment = await EnrollmentRepository.create(
                student_id=student_id,
                course_id=course_id,
                status=EnrollmentStatusEnum.ACTIVE
            )
            logger.info(f"Student {student_id} enrolled in course {course_id}")
            return enrollment, None
        except Exception as e:
            logger.error(f"Enrollment error: {e}")
            return None, "Enrollment failed"


class ProgressService:
    @staticmethod
    async def get_student_progress(student_id: str, course_id: str) -> dict:
        avg_grade = await GradeRepository.get_average(student_id, course_id)
        attendance_rate = await AttendanceRepository.get_attendance_rate(student_id, course_id)

        recent_grades = await GradeRepository.get_recent_grades(student_id, course_id, days=30)
        recent_attendance = await AttendanceRepository.get_recent_attendance(student_id, course_id, days=30)

        return {
            "student_id": student_id,
            "course_id": course_id,
            "average_grade": avg_grade or 0.0,
            "attendance_rate": attendance_rate,
            "grades_count": len(recent_grades),
            "attendance_count": len(recent_attendance),
            "last_grade_date": recent_grades[0].recorded_at if recent_grades else None,
            "last_attendance_date": recent_attendance[0].date if recent_attendance else None,
            "grade_trend": ProgressService._calculate_trend([g.score for g in recent_grades])
        }

    @staticmethod
    def _calculate_trend(scores: List[float]) -> str:
        if len(scores) < 2:
            return "stable"

        recent = scores[:5]
        older = scores[5:]

        if not older:
            return "stable"

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        change = ((recent_avg - older_avg) / older_avg) * 100

        if change > 5:
            return "improving"
        elif change < -5:
            return "declining"
        return "stable"


class CourseService:
    @staticmethod
    async def create_course(teacher_id: str, **course_data) -> Course:
        return await CourseRepository.create(teacher_id=teacher_id, **course_data)

    @staticmethod
    async def get_teacher_courses(teacher_id: str) -> List[Course]:
        return await CourseRepository.list_by_teacher(teacher_id)

    @staticmethod
    async def get_courses_for_students(
        student_ids: List[str],
        statuses: Optional[List[EnrollmentStatusEnum]] = None,
    ) -> List[dict]:
        """
        Shared core: children → enrollments → courses.

        Accepts one *or many* student IDs so both Student and Parent flows
        use identical logic.  Parent passes its full list of child IDs;
        Student passes [student_id].

        Returns a list of dicts:
            { "course": Course, "student_id": str, "enrollment_status": EnrollmentStatusEnum }

        Each (student_id, course) pair produces one entry, so the caller can
        attach child_name / teacher_name without any extra DB lookups.
        """
        if statuses is None:
            statuses = [EnrollmentStatusEnum.ACTIVE]

        logger.debug(
            "[CourseService] get_courses_for_students ids=%s statuses=%s",
            student_ids, [s.value for s in statuses],
        )

        course_cache: dict = {}   # course_id → Course  (avoid re-fetching the same course)
        rows: List[dict] = []

        for student_id in student_ids:
            enrollments = await EnrollmentRepository.list_by_student(student_id)
            matching = [e for e in enrollments if e.status in statuses]
            logger.debug(
                "[CourseService] student=%s  enrollments found: %d", student_id, len(matching)
            )

            for enr in matching:
                if enr.course_id not in course_cache:
                    course = await CourseRepository.get_by_id(enr.course_id)
                    if course and course.deleted_at is None:
                        course_cache[enr.course_id] = course

                course = course_cache.get(enr.course_id)
                if course:
                    rows.append({
                        "course": course,
                        "student_id": student_id,
                        "enrollment_status": enr.status,
                    })

        logger.debug("[CourseService] courses returned: %d rows", len(rows))
        return rows

    @staticmethod
    async def get_student_courses(student_id: str) -> List[Course]:
        """Backward-compatible wrapper — returns active Course objects for one student."""
        rows = await CourseService.get_courses_for_students([student_id])
        return [row["course"] for row in rows]


class InsightService:
    THRESHOLD_PERCENTAGE = 15.0
    TIME_WINDOW_DAYS = 30

    @staticmethod
    async def check_and_generate_insights(student_id: str, course_id: str) -> Optional[LearningInsight]:
        recent_grades = await GradeRepository.get_recent_grades(
            student_id, course_id, days=InsightService.TIME_WINDOW_DAYS
        )

        if len(recent_grades) < 2:
            return None

        recent_score = recent_grades[0].score
        older_score = recent_grades[-1].score

        if older_score == 0:
            return None

        change_pct = ((recent_score - older_score) / older_score) * 100

        if abs(change_pct) < InsightService.THRESHOLD_PERCENTAGE:
            return None

        if change_pct > 0:
            insight_type = InsightTypeEnum.PERFORMANCE_IMPROVEMENT
            summary = f"Great work! Your grade improved from {older_score:.1f} to {recent_score:.1f} ({change_pct:.1f}% increase)"
        else:
            insight_type = InsightTypeEnum.PERFORMANCE_DECLINE
            summary = f"Your grade declined from {older_score:.1f} to {recent_score:.1f} ({abs(change_pct):.1f}% decrease). Consider reaching out to your teacher."

        insight = await LearningInsightRepository.create(
            student_id=student_id,
            course_id=course_id,
            change_percentage=change_pct,
            insight_type=insight_type,
            summary=summary,
            metric_name="grade",
            prev_value=older_score,
            curr_value=recent_score,
            email_sent=False
        )

        # Create in-app notification for student
        await NotificationRepository.create(
            user_id=student_id,
            message=summary,
            type=NotificationTypeEnum.AI_ALERT,
        )

        # Create AIAlert record for significant performance declines
        if insight_type == InsightTypeEnum.PERFORMANCE_DECLINE:
            alert_level = (
                AlertLevelEnum.CRITICAL if abs(change_pct) > 30
                else AlertLevelEnum.WARNING
            )
            existing_alert = await AIAlert.find_one(
                AIAlert.student_id == student_id,
                AIAlert.course_id == course_id,
                AIAlert.parent_acknowledged == False,  # noqa: E712
            )
            if not existing_alert:
                await AIAlert(
                    student_id=student_id,
                    course_id=course_id,
                    alert_level=alert_level,
                    message=summary,
                    recommendation=(
                        "Reach out to your teacher immediately for additional support."
                        if abs(change_pct) > 30
                        else "Review recent lessons and consider forming a study group."
                    ),
                ).insert()

        logger.info(f"Generated insight for student {student_id}")
        return insight

    @staticmethod
    async def check_attendance_insights(student_id: str, course_id: str) -> Optional[LearningInsight]:
        current_rate = await AttendanceRepository.get_attendance_rate(student_id, course_id, days=30)
        previous_rate = await AttendanceRepository.get_attendance_rate(student_id, course_id, days=60)

        if previous_rate == 0:
            return None

        change_pct = ((current_rate - previous_rate) / previous_rate) * 100

        if abs(change_pct) < InsightService.THRESHOLD_PERCENTAGE:
            return None

        if change_pct > 0:
            insight_type = InsightTypeEnum.ATTENDANCE_IMPROVEMENT
            summary = f"Excellent attendance improvement! Your attendance rate increased from {previous_rate:.1f}% to {current_rate:.1f}%"
        else:
            insight_type = InsightTypeEnum.ATTENDANCE_CONCERN
            summary = f"Your attendance has declined from {previous_rate:.1f}% to {current_rate:.1f}%. Please prioritize attending classes."

        insight = await LearningInsightRepository.create(
            student_id=student_id,
            course_id=course_id,
            change_percentage=change_pct,
            insight_type=insight_type,
            summary=summary,
            metric_name="attendance_rate",
            prev_value=previous_rate,
            curr_value=current_rate,
            email_sent=False
        )

        # Create in-app notification for student
        await NotificationRepository.create(
            user_id=student_id,
            message=summary,
            type=NotificationTypeEnum.AI_ALERT,
        )

        # Create AIAlert for low-attendance concerns (deduplicated)
        if insight_type == InsightTypeEnum.ATTENDANCE_CONCERN:
            existing_alert = await AIAlert.find_one(
                AIAlert.student_id == student_id,
                AIAlert.course_id == course_id,
                AIAlert.parent_acknowledged == False,  # noqa: E712
            )
            if not existing_alert:
                await AIAlert(
                    student_id=student_id,
                    course_id=course_id,
                    alert_level=AlertLevelEnum.WARNING,
                    message=summary,
                    recommendation="Regular attendance is mandatory. Please prioritize attending all classes.",
                ).insert()

        return insight

    @staticmethod
    async def check_feedback_pattern(student_id: str, course_id: str) -> None:
        """Detect repeated negative feedback and create an AIAlert if threshold exceeded."""
        NEGATIVE_THRESHOLD = 3  # 3+ consecutive negative feedbacks triggers alert
        try:
            from app.models import SentimentEnum
            # Fetch only the N most recent feedbacks (DB-level limit + sort)
            feedbacks = await FeedbackRepository.list_by_student_course(
                student_id, course_id, limit=NEGATIVE_THRESHOLD
            )
            if len(feedbacks) < NEGATIVE_THRESHOLD:
                return

            # Already sorted newest-first by the repository query
            recent = feedbacks
            all_negative = all(
                (f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment)
                == SentimentEnum.NEGATIVE.value
                for f in recent
            )
            if not all_negative:
                return

            # Deduplication: skip if an unacknowledged alert already exists for this pattern
            existing = await AIAlert.find_one(
                AIAlert.student_id == student_id,
                AIAlert.course_id == course_id,
                AIAlert.alert_level == AlertLevelEnum.WARNING,
                AIAlert.parent_acknowledged == False,  # noqa: E712
            )
            if existing:
                return

            summary = (
                f"Student has received {NEGATIVE_THRESHOLD} consecutive negative feedback entries. "
                "Immediate teacher review recommended."
            )
            await AIAlert(
                student_id=student_id,
                course_id=course_id,
                alert_level=AlertLevelEnum.WARNING,
                message=summary,
                recommendation="Schedule a one-on-one session with the student to discuss performance concerns.",
            ).insert()

            await NotificationRepository.create(
                user_id=student_id,
                message=summary,
                type=NotificationTypeEnum.AI_ALERT,
            )
        except Exception as exc:
            logger.error("check_feedback_pattern failed: %s", exc)
