"""Academic data API routes (grades, attendance, feedback)"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models import User, RoleEnum
from app.schemas import GradeCreate, GradeResponse, AttendanceCreate, AttendanceResponse, FeedbackCreate, FeedbackResponse
from app.security import get_current_user, get_teacher_user
from app.repositories import GradeRepository, AttendanceRepository, FeedbackRepository, CourseRepository, UserRepository, EnrollmentRepository, GradeSuggestionRepository
from app.models import EnrollmentStatusEnum, GradeSuggestionStatusEnum
from app.services import InsightService

router = APIRouter(prefix="/api/academic", tags=["academic"])


def _serialize_grade(g) -> dict:
    return {
        "id": str(g.id),
        "student_id": g.student_id,
        "course_id": g.course_id,
        "score": g.score,
        "subject": g.subject,
        "recorded_at": g.recorded_at,
    }


def _serialize_attendance(a) -> dict:
    return {
        "id": str(a.id),
        "student_id": a.student_id,
        "course_id": a.course_id,
        "date": a.date,
        "status": a.status,
        "remarks": a.remarks,
    }


def _serialize_feedback(f) -> dict:
    return {
        "id": str(f.id),
        "student_id": f.student_id,
        "course_id": f.course_id,
        "sentiment": f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment,
        "content": f.content,
        "visibility": f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private"),
        "delivery_target": f.delivery_target.value if hasattr(f.delivery_target, "value") else getattr(f, "delivery_target", "none"),
        "email_delivered": getattr(f, "email_delivered", False),
        "submitted_at": f.submitted_at,
    }


async def _deliver_feedback_email(feedback, delivery_target: str) -> None:
    """Send feedback by email to student/parent/both depending on delivery_target."""
    try:
        from app.services.email_service import EmailNotificationService
        student = await UserRepository.get_by_id(feedback.student_id)
        if not student:
            return

        sentiment_label = feedback.sentiment.value if hasattr(feedback.sentiment, "value") else str(feedback.sentiment)
        import html as _html
        html = (
            f"<p>A new feedback entry has been recorded for <strong>{_html.escape(student.full_name())}</strong>.</p>"
            f"<p><strong>Sentiment:</strong> {_html.escape(sentiment_label).capitalize()}</p>"
            f"<p><strong>Feedback:</strong></p><p>{_html.escape(feedback.content)}</p>"
        )
        subject = f"IQ PLUS — Feedback for {student.full_name()}"

        recipients: list[str] = []
        if delivery_target in ("student", "both"):
            recipients.append(student.email)
        if delivery_target in ("parent", "both"):
            from app.models import RoleEnum as RE
            # Query only parents linked to this student
            parents = await User.find(
                User.role == RE.PARENT,
                {"linked_student_ids": feedback.student_id}
            ).to_list()
            for p in parents:
                recipients.append(p.email)

        email_delivered = False
        for email in recipients:
            ok = EmailNotificationService.send_email(
                recipient=email, subject=subject, html_content=html
            )
            email_delivered = email_delivered or ok

        if email_delivered:
            await feedback.set({"email_delivered": True})
    except Exception:
        pass  # Never block the response


# ==================== Grades ====================

@router.post("/grades", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
async def record_grade(
    grade: GradeCreate,
    current_user: User = Depends(get_teacher_user)
):
    course = await CourseRepository.get_by_id(grade.course_id)
    if not course or (course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to record grades for this course"
        )

    new_grade = await GradeRepository.create(**grade.model_dump())
    try:
        await InsightService.check_and_generate_insights(grade.student_id, grade.course_id)
    except Exception:
        pass  # Never block the response
    try:
        from app.services.score_service import compute_and_save as compute_score
        await compute_score(grade.student_id, grade.course_id)
    except Exception:
        pass  # Never block the response
    return GradeResponse(**_serialize_grade(new_grade))


@router.get("/grades", response_model=List[GradeResponse])
async def list_grades(
    current_user: User = Depends(get_current_user),
    student_id: str = None,
    course_id: str = None
):
    if student_id and course_id:
        if current_user.role == RoleEnum.TEACHER:
            course = await CourseRepository.get_by_id(course_id)
            if not course or course.teacher_id != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view grades for this course")
        elif current_user.role == RoleEnum.STUDENT:
            if str(current_user.id) != student_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only view their own grades")
        elif current_user.role == RoleEnum.PARENT:
            if student_id not in current_user.linked_student_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to this student")
        grades = await GradeRepository.get_recent_grades(student_id, course_id, days=365)
        return [GradeResponse(**_serialize_grade(g)) for g in grades]
    return []


# ==================== Attendance ====================

@router.post("/attendance", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def record_attendance(
    attendance: AttendanceCreate,
    current_user: User = Depends(get_teacher_user)
):
    course = await CourseRepository.get_by_id(attendance.course_id)
    if not course or (course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Prevent duplicate: same student + course + calendar day
    existing = await AttendanceRepository.find_by_student_course_date(
        attendance.student_id, attendance.course_id, attendance.date
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already recorded for this student on this date"
        )

    new_attendance = await AttendanceRepository.create(**attendance.model_dump())
    try:
        await InsightService.check_attendance_insights(attendance.student_id, attendance.course_id)
    except Exception:
        pass  # Never block the response
    try:
        from app.services.score_service import compute_and_save as compute_score
        await compute_score(attendance.student_id, attendance.course_id)
    except Exception:
        pass  # Never block the response
    return AttendanceResponse(**_serialize_attendance(new_attendance))


@router.get("/attendance", response_model=List[AttendanceResponse])
async def list_attendance(
    current_user: User = Depends(get_current_user),
    student_id: str = None,
    course_id: str = None
):
    if student_id and course_id:
        if current_user.role == RoleEnum.TEACHER:
            course = await CourseRepository.get_by_id(course_id)
            if not course or course.teacher_id != str(current_user.id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view attendance for this course")
        elif current_user.role == RoleEnum.STUDENT:
            if str(current_user.id) != student_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only view their own attendance")
        elif current_user.role == RoleEnum.PARENT:
            if student_id not in current_user.linked_student_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not linked to this student")
        records = await AttendanceRepository.get_recent_attendance(student_id, course_id, days=365)
        return [AttendanceResponse(**_serialize_attendance(a)) for a in records]
    return []


# ==================== Feedback ====================

@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback: FeedbackCreate,
    current_user: User = Depends(get_current_user)
):
    if current_user.role == RoleEnum.STUDENT:
        # Students can only submit feedback for themselves
        if feedback.student_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Students can only submit their own feedback")
    elif current_user.role == RoleEnum.TEACHER:
        # Teachers can only submit feedback for students in their own courses
        course = await CourseRepository.get_by_id(feedback.course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your course")
        # Verify student is actively enrolled in this course
        enrollment = await EnrollmentRepository.get_by_student_course(feedback.student_id, feedback.course_id)
        if not enrollment or enrollment.status != EnrollmentStatusEnum.ACTIVE:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not enrolled in this course")
    elif current_user.role == RoleEnum.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to submit feedback")
    # ADMIN: no restrictions

    new_feedback = await FeedbackRepository.create(**feedback.model_dump())

    # ── Post-save processing — all best-effort, never block the response ──────
    import logging as _log
    _fb_logger = _log.getLogger(__name__)

    # Optional email delivery based on delivery_target
    delivery = feedback.delivery_target
    if delivery != "none":
        await _deliver_feedback_email(new_feedback, delivery)

    # Run text analysis on the feedback content (stores FeedbackAnalysis doc)
    try:
        from app.services.feedback_analysis_service import FeedbackAnalysisService
        await FeedbackAnalysisService.analyze_and_save(new_feedback)
    except Exception as _exc:
        _fb_logger.warning("FeedbackAnalysis failed (non-critical): %s", _exc)

    # Recalculate performance score (score engine will use the new FeedbackAnalysis)
    try:
        from app.services.score_service import compute_and_save as compute_score
        await compute_score(feedback.student_id, feedback.course_id)
    except Exception as _exc:
        _fb_logger.warning("Score recompute after feedback failed (non-critical): %s", _exc)

    # Check for repeated negative feedback pattern
    try:
        await InsightService.check_feedback_pattern(feedback.student_id, feedback.course_id)
    except Exception as _exc:
        _fb_logger.warning("Feedback pattern check failed (non-critical): %s", _exc)

    # Notify teacher that new feedback was recorded (if submitted by admin)
    if current_user.role == RoleEnum.STUDENT:
        # Notify the course teacher that student submitted feedback
        course_obj = await CourseRepository.get_by_id(feedback.course_id)
        if course_obj:
            from app.repositories import NotificationRepository
            from app.models import NotificationTypeEnum as NTE
            await NotificationRepository.create(
                user_id=course_obj.teacher_id,
                title="Student Feedback Submitted",
                message=f"New feedback submitted for your course by a student.",
                type=NTE.FEEDBACK_ADDED,
                course_id=feedback.course_id,
                related_entity_type="feedback",
                related_entity_id=str(new_feedback.id),
            )
    else:
        # Notify the student that feedback was added for them
        from app.repositories import NotificationRepository
        from app.models import NotificationTypeEnum as NTE
        await NotificationRepository.create(
            user_id=feedback.student_id,
            title="New Feedback Received",
            message=f"New feedback has been recorded for you.",
            type=NTE.FEEDBACK_ADDED,
            course_id=feedback.course_id,
            related_entity_type="feedback",
            related_entity_id=str(new_feedback.id),
        )

    return FeedbackResponse(**_serialize_feedback(new_feedback))


@router.get("/feedback", response_model=List[FeedbackResponse])
async def list_feedback(
    current_user: User = Depends(get_current_user),
    course_id: str = None
):
    if not course_id:
        return []
    if current_user.role == RoleEnum.TEACHER:
        course = await CourseRepository.get_by_id(course_id)
        if not course or course.teacher_id != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view feedback for this course")
    feedbacks = await FeedbackRepository.list_by_course(course_id)
    # Students and parents can only see PUBLISHED feedback
    if current_user.role in (RoleEnum.STUDENT, RoleEnum.PARENT):
        from app.models import FeedbackVisibilityEnum
        feedbacks = [
            f for f in feedbacks
            if (f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private"))
            == FeedbackVisibilityEnum.PUBLISHED.value
        ]
    return [FeedbackResponse(**_serialize_feedback(f)) for f in feedbacks]


# ==================== Grade Suggestions ====================

def _serialize_suggestion(s) -> dict:
    return {
        "id":              str(s.id),
        "student_id":      s.student_id,
        "course_id":       s.course_id,
        "feedback_id":     s.feedback_id,
        "suggested_score": s.suggested_score,
        "reason":          s.reason,
        "status":          s.status.value if hasattr(s.status, "value") else s.status,
        "reviewed_by":     s.reviewed_by,
        "reviewed_at":     s.reviewed_at,
        "created_at":      s.created_at,
    }


@router.get("/grade-suggestions")
async def list_grade_suggestions(
    course_id: str,
    current_user: User = Depends(get_teacher_user),
):
    """List pending AI grade suggestions for a course (teacher / admin only)."""
    course = await CourseRepository.get_by_id(course_id)
    if not course or (course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    suggestions = await GradeSuggestionRepository.list_pending_by_course(course_id)
    return [_serialize_suggestion(s) for s in suggestions]


@router.post("/grade-suggestions/{suggestion_id}/approve", status_code=status.HTTP_200_OK)
async def approve_grade_suggestion(
    suggestion_id: str,
    current_user: User = Depends(get_teacher_user),
):
    """Approve a pending grade suggestion — creates a Grade record for the student."""
    from datetime import datetime as dt
    suggestion = await GradeSuggestionRepository.get_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != GradeSuggestionStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Suggestion already reviewed")

    course = await CourseRepository.get_by_id(suggestion.course_id)
    if not course or (course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Create the Grade record
    new_grade = await GradeRepository.create(
        student_id=suggestion.student_id,
        course_id=suggestion.course_id,
        score=suggestion.suggested_score,
        subject=f"AI-suggested (approved by teacher)",
    )

    # Mark suggestion approved
    await suggestion.set({
        "status":      GradeSuggestionStatusEnum.APPROVED,
        "reviewed_by": str(current_user.id),
        "reviewed_at": dt.utcnow(),
    })

    # Recompute performance score
    from app.services.score_service import compute_and_save as compute_score
    await compute_score(suggestion.student_id, suggestion.course_id)

    return {"ok": True, "grade_id": str(new_grade.id)}


@router.post("/grade-suggestions/{suggestion_id}/reject", status_code=status.HTTP_200_OK)
async def reject_grade_suggestion(
    suggestion_id: str,
    current_user: User = Depends(get_teacher_user),
):
    """Reject a pending grade suggestion without creating any Grade record."""
    from datetime import datetime as dt
    suggestion = await GradeSuggestionRepository.get_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != GradeSuggestionStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Suggestion already reviewed")

    course = await CourseRepository.get_by_id(suggestion.course_id)
    if not course or (course.teacher_id != str(current_user.id) and current_user.role != RoleEnum.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    await suggestion.set({
        "status":      GradeSuggestionStatusEnum.REJECTED,
        "reviewed_by": str(current_user.id),
        "reviewed_at": dt.utcnow(),
    })
    return {"ok": True}
