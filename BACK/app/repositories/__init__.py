"""Repository layer for data access (MongoDB/Beanie)"""
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from app.models import (
    User, Course, Enrollment, Grade, Attendance,
    Feedback, LearningInsight, Notification, CourseMaterial, AuditLog,
    LessonRecord, ProgressMetrics, AIAlert, WeeklySummary,
    RoleEnum, EnrollmentStatusEnum, AttendanceStatusEnum, NotificationTypeEnum, AlertLevelEnum,
    PerformanceScore, ScoreHistory, Message, Conversation, ChatMessage,
    ConversationTypeEnum, Syllabus, FeedbackAnalysis, ProgressPrediction,
    GradeSuggestion, GradeSuggestionStatusEnum,
)

logger = logging.getLogger(__name__)


class UserRepository:
    @staticmethod
    async def get_by_firebase_uid(firebase_uid: str) -> Optional[User]:
        return await User.find_one(User.firebase_uid == firebase_uid)

    @staticmethod
    async def get_by_id(user_id: str) -> Optional[User]:
        return await User.get(user_id)

    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        return await User.find_one(User.email == email)

    @staticmethod
    async def create(**kwargs) -> User:
        user = User(**kwargs)
        await user.insert()
        return user

    @staticmethod
    async def list_by_role(role: RoleEnum) -> List[User]:
        return await User.find(User.role == role).to_list()

    @staticmethod
    async def update(user_id: str, **kwargs) -> Optional[User]:
        user = await User.get(user_id)
        if user:
            kwargs["updated_at"] = datetime.utcnow()
            await user.set(kwargs)
        return user


class CourseRepository:
    @staticmethod
    async def get_by_id(course_id: str) -> Optional[Course]:
        return await Course.get(course_id)

    @staticmethod
    async def get_by_code(code: str) -> Optional[Course]:
        return await Course.find_one(Course.code == code)

    @staticmethod
    async def list_by_teacher(teacher_id: str) -> List[Course]:
        return await Course.find(
            Course.teacher_id == teacher_id,
            Course.deleted_at == None
        ).to_list()

    @staticmethod
    async def list_all() -> List[Course]:
        return await Course.find(Course.deleted_at == None).to_list()

    @staticmethod
    async def create(**kwargs) -> Course:
        course = Course(**kwargs)
        await course.insert()
        return course

    @staticmethod
    async def update(course_id: str, **kwargs) -> Optional[Course]:
        course = await Course.get(course_id)
        if course:
            kwargs["updated_at"] = datetime.utcnow()
            await course.set(kwargs)
        return course


class EnrollmentRepository:
    @staticmethod
    async def get_by_id(enrollment_id: str) -> Optional[Enrollment]:
        return await Enrollment.get(enrollment_id)

    @staticmethod
    async def get_by_student_course(student_id: str, course_id: str) -> Optional[Enrollment]:
        return await Enrollment.find_one(
            Enrollment.student_id == student_id,
            Enrollment.course_id == course_id
        )

    @staticmethod
    async def list_by_student(student_id: str) -> List[Enrollment]:
        return await Enrollment.find(Enrollment.student_id == student_id).to_list()

    @staticmethod
    async def list_by_course(course_id: str) -> List[Enrollment]:
        return await Enrollment.find(Enrollment.course_id == course_id).to_list()

    @staticmethod
    async def create(**kwargs) -> Enrollment:
        enrollment = Enrollment(**kwargs)
        await enrollment.insert()
        return enrollment

    @staticmethod
    async def count_active(course_id: str) -> int:
        return await Enrollment.find(
            Enrollment.course_id == course_id,
            Enrollment.status == EnrollmentStatusEnum.ACTIVE
        ).count()


class GradeRepository:
    @staticmethod
    async def get_recent_grades(student_id: str, course_id: str, days: int = 30) -> List[Grade]:
        delta = datetime.utcnow() - timedelta(days=days)
        return await Grade.find(
            Grade.student_id == student_id,
            Grade.course_id == course_id,
            Grade.recorded_at >= delta
        ).sort(-Grade.recorded_at).to_list()

    @staticmethod
    async def get_average(student_id: str, course_id: str) -> Optional[float]:
        grades = await Grade.find(
            Grade.student_id == student_id,
            Grade.course_id == course_id
        ).to_list()
        if not grades:
            return None
        return sum(g.score for g in grades) / len(grades)

    @staticmethod
    async def create(**kwargs) -> Grade:
        grade = Grade(**kwargs)
        await grade.insert()
        return grade


class AttendanceRepository:
    @staticmethod
    async def find_by_student_course_date(student_id: str, course_id: str, date: datetime) -> Optional[Attendance]:
        """Return an existing record for this student+course on the same calendar day."""
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return await Attendance.find_one(
            Attendance.student_id == student_id,
            Attendance.course_id  == course_id,
            Attendance.date       >= day_start,
            Attendance.date       <= day_end,
        )

    @staticmethod
    async def get_recent_attendance(student_id: str, course_id: str, days: int = 30) -> List[Attendance]:
        delta = datetime.utcnow() - timedelta(days=days)
        return await Attendance.find(
            Attendance.student_id == student_id,
            Attendance.course_id == course_id,
            Attendance.date >= delta
        ).sort(-Attendance.date).to_list()

    @staticmethod
    async def get_attendance_rate(student_id: str, course_id: str, days: int = 30) -> float:
        delta = datetime.utcnow() - timedelta(days=days)
        records = await Attendance.find(
            Attendance.student_id == student_id,
            Attendance.course_id == course_id,
            Attendance.date >= delta
        ).to_list()

        total = len(records)
        if total == 0:
            return 0.0

        present = sum(
            1 for r in records
            if r.status in [AttendanceStatusEnum.PRESENT, AttendanceStatusEnum.LATE]
        )
        return (present / total) * 100

    @staticmethod
    async def create(**kwargs) -> Attendance:
        attendance = Attendance(**kwargs)
        await attendance.insert()
        return attendance


class LearningInsightRepository:
    @staticmethod
    async def list_by_student(student_id: str, limit: int = 10) -> List[LearningInsight]:
        return await LearningInsight.find(
            LearningInsight.student_id == student_id
        ).sort(-LearningInsight.created_at).limit(limit).to_list()

    @staticmethod
    async def list_unsent() -> List[LearningInsight]:
        return await LearningInsight.find(LearningInsight.email_sent == False).to_list()

    @staticmethod
    async def create(**kwargs) -> LearningInsight:
        insight = LearningInsight(**kwargs)
        await insight.insert()
        return insight

    @staticmethod
    async def mark_sent(insight_id: str) -> Optional[LearningInsight]:
        insight = await LearningInsight.get(insight_id)
        if insight:
            await insight.set({LearningInsight.email_sent: True})
        return insight


class FeedbackRepository:
    @staticmethod
    async def create(**kwargs) -> Feedback:
        feedback = Feedback(**kwargs)
        await feedback.insert()
        return feedback

    @staticmethod
    async def list_by_course(course_id: str) -> List[Feedback]:
        return await Feedback.find(Feedback.course_id == course_id).to_list()

    @staticmethod
    async def list_by_student_course(
        student_id: str, course_id: str, limit: Optional[int] = None
    ) -> List[Feedback]:
        q = Feedback.find(
            Feedback.student_id == student_id,
            Feedback.course_id == course_id,
        ).sort(-Feedback.submitted_at)
        if limit is not None:
            q = q.limit(limit)
        return await q.to_list()

    @staticmethod
    async def get_by_id(feedback_id: str) -> Optional[Feedback]:
        return await Feedback.get(feedback_id)


class NotificationRepository:
    @staticmethod
    async def create(user_id: str, message: str, type: NotificationTypeEnum, **kwargs) -> Notification:
        notif = Notification(user_id=user_id, message=message, type=type, **kwargs)
        await notif.insert()
        return notif

    @staticmethod
    async def list_by_user(user_id: str, limit: int = 20) -> List[Notification]:
        return await Notification.find(
            Notification.user_id == user_id
        ).sort(-Notification.created_at).limit(limit).to_list()

    @staticmethod
    async def mark_read(notification_id: str) -> Optional[Notification]:
        notif = await Notification.get(notification_id)
        if notif:
            await notif.set({Notification.read_status: True})
        return notif

    @staticmethod
    async def unread_count(user_id: str) -> int:
        return await Notification.find(
            Notification.user_id == user_id,
            Notification.read_status == False
        ).count()

    @staticmethod
    async def mark_all_read(user_id: str) -> None:
        """Bulk-mark all unread notifications as read in a single DB round-trip."""
        collection = Notification.get_motor_collection()
        await collection.update_many(
            {"user_id": user_id, "read_status": False},
            {"$set": {"read_status": True}},
        )


class CourseMaterialRepository:
    @staticmethod
    async def create(**kwargs) -> CourseMaterial:
        material = CourseMaterial(**kwargs)
        await material.insert()
        return material

    @staticmethod
    async def list_by_course(course_id: str) -> List[CourseMaterial]:
        return await CourseMaterial.find(
            CourseMaterial.course_id == course_id
        ).sort(-CourseMaterial.created_at).to_list()

    @staticmethod
    async def get_by_id(material_id: str) -> Optional[CourseMaterial]:
        return await CourseMaterial.get(material_id)

    @staticmethod
    async def delete(material_id: str) -> bool:
        material = await CourseMaterial.get(material_id)
        if material:
            await material.delete()
            return True
        return False


class AuditLogRepository:
    @staticmethod
    async def log(user_id: str, action: str, resource_type: str,
                  resource_id: Optional[str] = None, details: Optional[dict] = None) -> AuditLog:
        entry = AuditLog(
            user_id=user_id, action=action, resource_type=resource_type,
            resource_id=resource_id, details=details
        )
        await entry.insert()
        return entry

    @staticmethod
    async def list_all(limit: int = 100, skip: int = 0) -> List[AuditLog]:
        return await AuditLog.find_all().sort(-AuditLog.timestamp).skip(skip).limit(limit).to_list()

    @staticmethod
    async def list_by_user(user_id: str, limit: int = 50) -> List[AuditLog]:
        return await AuditLog.find(
            AuditLog.user_id == user_id
        ).sort(-AuditLog.timestamp).limit(limit).to_list()


class LessonRecordRepository:
    @staticmethod
    async def create(**kwargs) -> LessonRecord:
        record = LessonRecord(**kwargs)
        await record.insert()
        return record

    @staticmethod
    async def get_by_id(record_id: str) -> Optional[LessonRecord]:
        return await LessonRecord.get(record_id)

    @staticmethod
    async def get_by_student_course(
        student_id: str, course_id: str,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[LessonRecord]:
        query = LessonRecord.find(
            LessonRecord.student_id == student_id,
            LessonRecord.course_id == course_id
        )
        if since:
            query = LessonRecord.find(
                LessonRecord.student_id == student_id,
                LessonRecord.course_id == course_id,
                LessonRecord.lesson_date >= since
            )
        return await query.sort(-LessonRecord.lesson_date).limit(limit).to_list()

    @staticmethod
    async def list_by_course(course_id: str, limit: int = 200) -> List[LessonRecord]:
        return await LessonRecord.find(
            LessonRecord.course_id == course_id
        ).sort(-LessonRecord.lesson_date).limit(limit).to_list()


class ProgressMetricsRepository:
    @staticmethod
    async def get(student_id: str, course_id: str) -> Optional[ProgressMetrics]:
        return await ProgressMetrics.find_one(
            ProgressMetrics.student_id == student_id,
            ProgressMetrics.course_id == course_id
        )

    @staticmethod
    async def upsert(student_id: str, course_id: str, **kwargs) -> ProgressMetrics:
        existing = await ProgressMetricsRepository.get(student_id, course_id)
        if existing:
            kwargs["last_updated"] = datetime.utcnow()
            await existing.set(kwargs)
            return existing
        metrics = ProgressMetrics(
            student_id=student_id, course_id=course_id,
            last_updated=datetime.utcnow(), **kwargs
        )
        await metrics.insert()
        return metrics


class AIAlertRepository:
    @staticmethod
    async def create(**kwargs) -> AIAlert:
        alert = AIAlert(**kwargs)
        await alert.insert()
        return alert

    @staticmethod
    async def list_by_student(student_id: str, limit: int = 20) -> List[AIAlert]:
        return await AIAlert.find(
            AIAlert.student_id == student_id
        ).sort(-AIAlert.created_at).limit(limit).to_list()

    @staticmethod
    async def list_by_student_course(
        student_id: str, course_id: str, limit: int = 20
    ) -> List[AIAlert]:
        return await AIAlert.find(
            AIAlert.student_id == student_id,
            AIAlert.course_id == course_id
        ).sort(-AIAlert.created_at).limit(limit).to_list()

    @staticmethod
    async def list_by_course(course_id: str, limit: int = 50) -> List[AIAlert]:
        return await AIAlert.find(
            AIAlert.course_id == course_id
        ).sort(-AIAlert.created_at).limit(limit).to_list()

    @staticmethod
    async def mark_notification_sent(alert_id: str) -> Optional[AIAlert]:
        alert = await AIAlert.get(alert_id)
        if alert:
            await alert.set({AIAlert.notification_sent: True})
        return alert


class WeeklySummaryRepository:
    @staticmethod
    async def create(**kwargs) -> WeeklySummary:
        summary = WeeklySummary(**kwargs)
        await summary.insert()
        return summary

    @staticmethod
    async def list_by_student(student_id: str, limit: int = 10) -> List[WeeklySummary]:
        return await WeeklySummary.find(
            WeeklySummary.student_id == student_id
        ).sort(-WeeklySummary.created_at).limit(limit).to_list()

    @staticmethod
    async def list_unsent() -> List[WeeklySummary]:
        return await WeeklySummary.find(
            WeeklySummary.email_sent == False
        ).to_list()


class PerformanceScoreRepository:
    @staticmethod
    async def get(student_id: str, course_id: str) -> Optional[PerformanceScore]:
        return await PerformanceScore.find_one(
            PerformanceScore.student_id == student_id,
            PerformanceScore.course_id == course_id,
        )

    @staticmethod
    async def list_by_student(student_id: str) -> List[PerformanceScore]:
        return await PerformanceScore.find(
            PerformanceScore.student_id == student_id
        ).to_list()

    @staticmethod
    async def list_by_course(course_id: str) -> List[PerformanceScore]:
        """Batch load all scores for a course — avoids N per-student queries."""
        return await PerformanceScore.find(
            PerformanceScore.course_id == course_id
        ).to_list()

    @staticmethod
    async def get_history(student_id: str, course_id: str, limit: int = 20) -> List[ScoreHistory]:
        return await ScoreHistory.find(
            ScoreHistory.student_id == student_id,
            ScoreHistory.course_id == course_id,
        ).sort(-ScoreHistory.computed_at).limit(limit).to_list()


class MessageRepository:
    @staticmethod
    async def create(**kwargs) -> Message:
        msg = Message(**kwargs)
        await msg.insert()
        return msg

    @staticmethod
    async def get_by_id(message_id: str) -> Optional[Message]:
        return await Message.get(message_id)

    @staticmethod
    async def inbox(recipient_id: str, limit: int = 50) -> List[Message]:
        return await Message.find(
            Message.recipient_id == recipient_id
        ).sort(-Message.created_at).limit(limit).to_list()

    @staticmethod
    async def sent(sender_id: str, limit: int = 50) -> List[Message]:
        return await Message.find(
            Message.sender_id == sender_id
        ).sort(-Message.created_at).limit(limit).to_list()

    @staticmethod
    async def mark_read(message_id: str) -> Optional[Message]:
        msg = await Message.get(message_id)
        if msg:
            await msg.set({Message.read_status: True})
        return msg


class SyllabusRepository:
    @staticmethod
    async def get_by_course(course_id: str) -> Optional[Syllabus]:
        return await Syllabus.find_one(Syllabus.course_id == course_id)

    @staticmethod
    async def get_by_id(syllabus_id: str) -> Optional[Syllabus]:
        return await Syllabus.get(syllabus_id)

    @staticmethod
    async def create(**kwargs) -> Syllabus:
        syllabus = Syllabus(**kwargs)
        await syllabus.insert()
        return syllabus


class FeedbackAnalysisRepository:
    @staticmethod
    async def create(**kwargs) -> FeedbackAnalysis:
        fa = FeedbackAnalysis(**kwargs)
        await fa.insert()
        return fa

    @staticmethod
    async def list_by_student_course(
        student_id: str, course_id: str
    ) -> List[FeedbackAnalysis]:
        return await FeedbackAnalysis.find(
            FeedbackAnalysis.student_id == student_id,
            FeedbackAnalysis.course_id == course_id,
        ).sort(-FeedbackAnalysis.created_at).to_list()

    @staticmethod
    async def get_by_feedback_id(feedback_id: str) -> Optional[FeedbackAnalysis]:
        return await FeedbackAnalysis.find_one(
            FeedbackAnalysis.feedback_id == feedback_id
        )


class ProgressPredictionRepository:
    @staticmethod
    async def upsert(student_id: str, course_id: str, **kwargs) -> ProgressPrediction:
        from datetime import datetime
        existing = await ProgressPrediction.find_one(
            ProgressPrediction.student_id == student_id,
            ProgressPrediction.course_id == course_id,
        )
        if existing:
            await existing.set({**kwargs, ProgressPrediction.computed_at: datetime.utcnow()})
            return existing
        pred = ProgressPrediction(student_id=student_id, course_id=course_id, **kwargs)
        await pred.insert()
        return pred

    @staticmethod
    async def get(student_id: str, course_id: str) -> Optional[ProgressPrediction]:
        return await ProgressPrediction.find_one(
            ProgressPrediction.student_id == student_id,
            ProgressPrediction.course_id == course_id,
        )

    @staticmethod
    async def list_by_student(student_id: str) -> List[ProgressPrediction]:
        return await ProgressPrediction.find(
            ProgressPrediction.student_id == student_id
        ).to_list()

    @staticmethod
    async def list_high_risk() -> List[ProgressPrediction]:
        """Return all 'at_risk' or 'needs_intervention' predictions (admin use)."""
        return await ProgressPrediction.find(
            {"risk_level": {"$in": ["medium", "high"]}}
        ).to_list()


class ConversationRepository:
    @staticmethod
    async def find_direct(user1_id: str, user2_id: str) -> Optional[Conversation]:
        return await Conversation.find_one(
            {"type": "direct", "participant_ids": {"$all": [user1_id, user2_id]}}
        )

    @staticmethod
    async def find_course_chat(course_id: str) -> Optional[Conversation]:
        return await Conversation.find_one({"type": "course", "course_id": course_id})

    @staticmethod
    async def get_by_id(conv_id: str) -> Optional[Conversation]:
        return await Conversation.get(conv_id)

    @staticmethod
    async def create(**kwargs) -> Conversation:
        conv = Conversation(**kwargs)
        await conv.insert()
        return conv

    @staticmethod
    async def list_direct_for_user(user_id: str) -> List[Conversation]:
        return await Conversation.find(
            {"type": "direct", "participant_ids": user_id}
        ).sort(-Conversation.last_message_at).to_list()

    @staticmethod
    async def list_course_for_ids(course_ids: List[str]) -> List[Conversation]:
        if not course_ids:
            return []
        return await Conversation.find(
            {"type": "course", "course_id": {"$in": course_ids}}
        ).sort(-Conversation.last_message_at).to_list()

    @staticmethod
    async def update_last_message(conv_id: str, preview: str) -> None:
        conv = await Conversation.get(conv_id)
        if conv:
            conv.last_message_at = datetime.utcnow()
            conv.last_message_preview = preview[:100]
            await conv.save()


class ChatMessageRepository:
    @staticmethod
    async def create(conversation_id: str, sender_id: str, content: str) -> ChatMessage:
        msg = ChatMessage(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            read_by=[sender_id],
        )
        await msg.insert()
        return msg

    @staticmethod
    async def list_by_conversation(conv_id: str, limit: int = 50) -> List[ChatMessage]:
        return await ChatMessage.find(
            ChatMessage.conversation_id == conv_id
        ).sort(+ChatMessage.created_at).limit(limit).to_list()

    @staticmethod
    async def count_unread(conv_id: str, user_id: str) -> int:
        return await ChatMessage.find(
            {"conversation_id": conv_id, "read_by": {"$not": {"$elemMatch": {"$eq": user_id}}}}
        ).count()

    @staticmethod
    async def mark_conversation_read(conv_id: str, user_id: str) -> None:
        collection = ChatMessage.get_motor_collection()
        await collection.update_many(
            {
                "conversation_id": conv_id,
                "read_by": {"$not": {"$elemMatch": {"$eq": user_id}}},
            },
            {"$addToSet": {"read_by": user_id}},
        )


class GradeSuggestionRepository:
    @staticmethod
    async def create(**kwargs) -> GradeSuggestion:
        suggestion = GradeSuggestion(**kwargs)
        await suggestion.insert()
        return suggestion

    @staticmethod
    async def get_by_id(suggestion_id: str) -> Optional[GradeSuggestion]:
        return await GradeSuggestion.get(suggestion_id)

    @staticmethod
    async def list_pending_by_course(course_id: str) -> List[GradeSuggestion]:
        return await GradeSuggestion.find(
            GradeSuggestion.course_id == course_id,
            GradeSuggestion.status   == GradeSuggestionStatusEnum.PENDING,
        ).sort(-GradeSuggestion.created_at).to_list()

    @staticmethod
    async def list_by_course(course_id: str, limit: int = 50) -> List[GradeSuggestion]:
        return await GradeSuggestion.find(
            GradeSuggestion.course_id == course_id,
        ).sort(-GradeSuggestion.created_at).limit(limit).to_list()
