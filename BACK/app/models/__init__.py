"""Beanie Document Models for IQ PLUS (MongoDB)"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from beanie import Document, Indexed
from pydantic import BaseModel, Field


class RoleEnum(str, Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


class EnrollmentStatusEnum(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"


class NotificationTypeEnum(str, Enum):
    AI_ALERT = "ai_alert"
    COURSE_PUBLISHED = "course_published"
    ENROLLMENT_APPROVED = "enrollment_approved"
    ENROLLMENT_REJECTED = "enrollment_rejected"
    ENROLLMENT_PENDING = "enrollment_pending"
    FEEDBACK_ADDED = "feedback_added"
    SCHEDULE_CHANGED = "schedule_changed"
    MESSAGE_RECEIVED = "message_received"
    CHAT_MESSAGE = "chat_message"


class ConversationTypeEnum(str, Enum):
    DIRECT = "direct"
    COURSE = "course"


class AttendanceStatusEnum(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AlertLevelEnum(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SentimentEnum(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class InsightTypeEnum(str, Enum):
    PERFORMANCE_IMPROVEMENT = "performance_improvement"
    PERFORMANCE_DECLINE = "performance_decline"
    ATTENDANCE_CONCERN = "attendance_concern"
    ATTENDANCE_IMPROVEMENT = "attendance_improvement"


class CourseStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VisibilityScopeEnum(str, Enum):
    PUBLIC = "public"
    SCHOOL_ONLY = "school_only"
    TEACHER_ONLY = "teacher_only"


class FeedbackDeliveryEnum(str, Enum):
    NONE = "none"
    STUDENT = "student"
    PARENT = "parent"
    BOTH = "both"


class FeedbackVisibilityEnum(str, Enum):
    PRIVATE = "private"     # visible to teachers/admins only
    PUBLISHED = "published" # visible to students and parents


class MessageTypeEnum(str, Enum):
    GENERAL = "general"
    ACADEMIC = "academic"
    ALERT = "alert"
    ANNOUNCEMENT = "announcement"


class SyllabusStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ScoreClassificationEnum(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    NEEDS_ATTENTION = "needs_attention"


# ==================== Users ====================

class User(Document):
    firebase_uid: Indexed(str, unique=True)
    email: Indexed(str, unique=True)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None          # editable display name
    role: RoleEnum = RoleEnum.STUDENT
    avatar_url: Optional[str] = None            # path served via /uploads/avatars/
    age: Optional[int] = None                   # user-provided age
    linked_student_ids: List[str] = Field(default_factory=list)  # parent → student ids
    hashed_password: Optional[str] = None       # bcrypt hash; None for legacy/Firebase users
    session_token: Optional[str] = None         # opaque Bearer token issued at login
    is_active: bool = True
    is_approved: bool = True                   # False until admin approves self-registrations
    approved_at: Optional[datetime] = None     # set when admin approves the account
    last_login_at: Optional[datetime] = None   # set on successful password login
    last_active_at: Optional[datetime] = None  # set on dashboard access
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    class Settings:
        name = "users"

    def full_name(self) -> str:
        if self.display_name:
            return self.display_name
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else self.email

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ==================== Courses ====================

class Course(Document):
    code: Indexed(str, unique=True)
    name: str
    description: Optional[str] = None
    teacher_id: str                  # owner user ObjectId string
    created_by_role: str = "teacher" # "teacher" | "admin"
    schedule: Optional[dict] = None
    capacity: int = 30
    status: CourseStatusEnum = CourseStatusEnum.DRAFT
    visibility_scope: VisibilityScopeEnum = VisibilityScopeEnum.SCHOOL_ONLY
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None

    class Settings:
        name = "courses"

    def __repr__(self):
        return f"<Course {self.code} [{self.status}]>"


# ==================== Enrollments ====================

class Enrollment(Document):
    student_id: str
    course_id: str
    status: EnrollmentStatusEnum = EnrollmentStatusEnum.ACTIVE
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "enrollments"


# ==================== Academic Data ====================

class Grade(Document):
    student_id: str
    course_id: str
    score: float
    subject: str
    recorded_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "grades"


class Attendance(Document):
    student_id: str
    course_id: str
    date: datetime
    status: AttendanceStatusEnum = AttendanceStatusEnum.ABSENT
    remarks: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "attendance"


class Feedback(Document):
    student_id: str
    course_id: str
    sentiment: SentimentEnum
    content: str
    visibility: FeedbackVisibilityEnum = FeedbackVisibilityEnum.PRIVATE
    delivery_target: FeedbackDeliveryEnum = FeedbackDeliveryEnum.NONE
    email_delivered: bool = False
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "feedback"


# ==================== AI/Insights ====================

class LearningInsight(Document):
    student_id: str
    course_id: str
    change_percentage: float
    insight_type: InsightTypeEnum
    summary: str
    metric_name: Optional[str] = None
    prev_value: Optional[float] = None
    curr_value: Optional[float] = None
    email_sent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "learning_insights"


# ==================== Notifications ====================

class Notification(Document):
    user_id: str
    message: str
    type: NotificationTypeEnum
    title: Optional[str] = None
    course_id: Optional[str] = None
    related_entity_type: Optional[str] = None   # e.g. "feedback", "message", "enrollment"
    related_entity_id: Optional[str] = None
    read_status: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "notifications"


# ==================== Course Materials ====================

class CourseMaterial(Document):
    course_id: str
    title: str
    file_url: Optional[str] = None
    link_url: Optional[str] = None
    uploaded_by: str  # teacher user ObjectId string
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "course_materials"


# ==================== Audit Logs ====================

class AuditLog(Document):
    user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "audit_logs"


# ==================== Lesson Records ====================

class DifficultyEnum(str, Enum):
    EASY   = "easy"
    MEDIUM = "medium"
    HARD   = "hard"


class LessonRecord(Document):
    student_id: str
    course_id: str
    lesson_date: datetime
    attendance_status: AttendanceStatusEnum = AttendanceStatusEnum.PRESENT
    grade_value: Optional[float] = None            # 0–100
    teacher_feedback: Optional[str] = None
    # Lesson completion workflow fields
    difficulty_level: Optional[DifficultyEnum] = None   # easy | medium | hard
    engagement_rating: Optional[int] = None             # 1–5
    created_by_teacher_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "lesson_records"


# ==================== Progress Metrics ====================

class ProgressMetrics(Document):
    student_id: str
    course_id: str
    average_grade: float = 0.0
    attendance_rate: float = 0.0
    trend_direction: str = "stable"          # "improving" | "declining" | "stable"
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "progress_metrics"


# ==================== AI Alerts ====================

class AIAlert(Document):
    student_id: str
    course_id: str
    alert_level: AlertLevelEnum = AlertLevelEnum.INFO
    message: str
    recommendation: str
    lesson_record_id: Optional[str] = None
    notification_sent: bool = False
    # Parent acknowledgement
    parent_seen: bool = False
    parent_acknowledged: bool = False
    parent_acknowledged_at: Optional[datetime] = None
    parent_comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ai_alerts"


# ==================== Weekly Summaries ====================

class WeeklySummary(Document):
    student_id: str
    course_id: str
    week_start: datetime
    attendance_present: int = 0
    attendance_absent: int = 0
    average_grade: float = 0.0
    trend_vs_previous: str = "stable"
    teacher_feedback_highlights: List[str] = Field(default_factory=list)
    ai_observations: Optional[str] = None
    email_sent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "weekly_summaries"


# ==================== Feedback Analysis ====================

class FeedbackAnalysis(Document):
    """Derived text-analysis layer for a teacher Feedback document.

    The original Feedback record is never modified.
    This document stores the keyword/NLP result that the score engine reads
    instead of the raw sentiment enum when available.
    """
    feedback_id: str                            # FK → Feedback._id
    student_id: str
    course_id: str
    original_feedback_text: str                 # snapshot of content at analysis time
    sentiment_label: str                        # "positive" | "neutral" | "negative"
    sentiment_score: float                      # 0–100, text-derived sentiment strength
    extracted_tags: List[str] = Field(default_factory=list)   # e.g. ["participation","effort"]
    confidence: float = 0.0                     # 0.0–1.0: how many indicators matched
    calculated_contribution: float              # 0–100, fed into score engine
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "feedback_analyses"


# ==================== Performance Scores ====================

class PerformanceScore(Document):
    student_id: str
    course_id: str
    score: float                          # composite 0–100
    classification: ScoreClassificationEnum
    grade_score: float                    # raw grade component 0–100
    attendance_score: float               # raw attendance component 0–100
    feedback_score: float                 # raw feedback sentiment component 0–100
    trend_score: float                    # raw trend component 0–100
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "performance_scores"


class ScoreHistory(Document):
    student_id: str
    course_id: str
    score: float
    classification: ScoreClassificationEnum
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "score_history"


# ==================== Progress Prediction ====================

class ProgressPrediction(Document):
    """Rule-based academic prediction for a student in a course.

    Recomputed whenever the PerformanceScore is recomputed.
    Always includes a human-readable explanation — never opaque.
    """
    student_id: str
    course_id: str
    prediction_label: str        # "likely_improving" | "likely_stable" | "at_risk" | "needs_intervention"
    explanation: str             # human-readable reason
    recommendation: str          # actionable advice for teacher/parent/student
    risk_level: str              # "low" | "medium" | "high"
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "progress_predictions"


# ==================== Messages ====================

class Message(Document):
    sender_id: str
    recipient_id: str
    subject: str
    content: str
    message_type: MessageTypeEnum = MessageTypeEnum.GENERAL
    course_id: Optional[str] = None
    read_status: bool = False
    email_sent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "messages"


# ==================== Chat (Conversations + ChatMessages) ====================

class Conversation(Document):
    type: ConversationTypeEnum = ConversationTypeEnum.DIRECT
    participant_ids: List[str] = Field(default_factory=list)  # used for direct chats
    course_id: Optional[str] = None                           # used for course chats
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_preview: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "conversations"


class ChatMessage(Document):
    conversation_id: str
    sender_id: str
    content: str
    read_by: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "chat_messages"


# ==================== Syllabus ====================

class WeeklyTopic(BaseModel):
    week_number: int
    title: str
    description: Optional[str] = None
    objectives: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    assignments: List[str] = Field(default_factory=list)
    teacher_notes: Optional[str] = None   # internal, visible to teachers only


class Syllabus(Document):
    course_id: str
    version: int = 1
    status: SyllabusStatusEnum = SyllabusStatusEnum.DRAFT
    topics: List[WeeklyTopic] = Field(default_factory=list)
    completed_weeks: List[int] = Field(default_factory=list)  # week_numbers marked done
    created_by: str                       # teacher user id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "syllabi"


# ==================== Usability Feedback ====================

class UsabilityFeedback(Document):
    user_id: str
    report_clarity: int               # 1–5
    dashboard_usability: int          # 1–5
    navigation_ease: int              # 1–5
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "usability_feedback"


class GradeSuggestionStatusEnum(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GradeSuggestion(Document):
    """AI-generated grade suggestion awaiting teacher review.

    Created automatically when feedback analysis produces a significant
    contribution signal.  The teacher must approve or reject it; no Grade
    record is written until approval.
    """
    student_id:      str
    course_id:       str
    feedback_id:     str
    suggested_score: float            # 0-100
    reason:          str              # human-readable explanation
    status: GradeSuggestionStatusEnum = GradeSuggestionStatusEnum.PENDING
    reviewed_by:  Optional[str]      = None
    reviewed_at:  Optional[datetime] = None
    created_at:   datetime           = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "grade_suggestions"


ALL_DOCUMENTS = [
    User, Course, Enrollment, Grade, Attendance, Feedback,
    LearningInsight, Notification, CourseMaterial, AuditLog,
    LessonRecord, ProgressMetrics, AIAlert, WeeklySummary,
    PerformanceScore, ScoreHistory, Message, Conversation, ChatMessage,
    Syllabus, UsabilityFeedback, FeedbackAnalysis, ProgressPrediction,
    GradeSuggestion,
]
