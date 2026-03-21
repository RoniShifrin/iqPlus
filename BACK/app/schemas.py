"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ==================== Auth Schemas ====================

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    role: str = Field("student", pattern="^(teacher|student|parent|TEACHER|STUDENT|PARENT)$")
    subject: Optional[str] = None
    employee_id: Optional[str] = None
    grade: Optional[str] = None
    dob: Optional[str] = None
    parent_contact: Optional[str] = None
    child_name: Optional[str] = None
    child_grade: Optional[str] = None
    relationship: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: str
    firebase_uid: Optional[str] = None
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    display_name: Optional[str]
    role: str
    avatar_url: Optional[str]
    age: Optional[int] = None
    linked_student_ids: List[str] = []
    is_active: bool
    created_at: datetime
    courses: List[Any] = []

    class Config:
        from_attributes = True


# ==================== Profile Schemas ====================

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=1, le=120)

class AvatarResponse(BaseModel):
    avatar_url: str


# ==================== Course Schemas ====================

class CourseCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    schedule: Optional[dict] = None
    capacity: int = Field(30, ge=1, le=500)
    visibility_scope: str = Field("school_only", pattern="^(public|school_only|teacher_only)$")
    teacher_id: Optional[str] = None  # Admin-only: assign a specific teacher

class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    schedule: Optional[dict] = None
    capacity: Optional[int] = Field(None, ge=1, le=500)
    visibility_scope: Optional[str] = Field(None, pattern="^(public|school_only|teacher_only)$")

class CourseResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str]
    teacher_id: str
    created_by_role: str
    schedule: Optional[dict]
    capacity: int
    status: str
    visibility_scope: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Enrollment Schemas ====================

class EnrollmentCreate(BaseModel):
    student_id: str
    course_id: str

class EnrollmentResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    status: str
    enrolled_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== Grade Schemas ====================

class GradeCreate(BaseModel):
    student_id: str
    course_id: str
    score: float = Field(..., ge=0, le=100)
    subject: str = Field(..., min_length=1, max_length=100)

class GradeResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    score: float
    subject: str
    recorded_at: datetime

    class Config:
        from_attributes = True


# ==================== Attendance Schemas ====================

class AttendanceCreate(BaseModel):
    student_id: str
    course_id: str
    date: datetime
    status: str = Field(..., pattern="^(present|absent|late|excused)$")
    remarks: Optional[str] = Field(None, max_length=500)

class AttendanceResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    date: datetime
    status: str
    remarks: Optional[str]

    class Config:
        from_attributes = True


# ==================== Feedback Schemas ====================

class FeedbackCreate(BaseModel):
    student_id: str
    course_id: str
    sentiment: str = Field(..., pattern="^(positive|neutral|negative)$")
    content: str = Field(..., min_length=10, max_length=1000)
    visibility: str = Field("private", pattern="^(private|published)$")
    delivery_target: str = Field("none", pattern="^(none|student|parent|both)$")

class FeedbackResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    sentiment: str
    content: str
    visibility: str = "private"
    delivery_target: str = "none"
    email_delivered: bool = False
    submitted_at: datetime

    class Config:
        from_attributes = True


# ==================== Learning Insight Schemas ====================

class LearningInsightResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    change_percentage: float
    insight_type: str
    summary: str
    metric_name: Optional[str]
    prev_value: Optional[float]
    curr_value: Optional[float]
    email_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Progress Schemas ====================

class StudentProgressResponse(BaseModel):
    student_id: str
    course_id: str
    average_grade: float
    attendance_rate: float
    last_grade_date: Optional[datetime]
    last_attendance_date: Optional[datetime]
    recent_insights: List[LearningInsightResponse]

class CourseProgressResponse(BaseModel):
    course_id: str
    total_enrolled: int
    average_class_grade: float
    average_attendance_rate: float
    students_at_risk: int


# ==================== Dashboard Schemas ====================

class DashboardCourse(BaseModel):
    id: str
    code: str
    name: str
    status: str
    visibility_scope: str
    capacity: int
    enrolled_count: Optional[int] = None
    description: Optional[str] = None
    teacher_name: Optional[str] = None
    schedule: Optional[dict] = None

class DashboardAlert(BaseModel):
    type: str       # "warning" | "info" | "success"
    message: str
    course_name: Optional[str] = None

class DashboardResponse(BaseModel):
    role: str
    allowed_actions: List[str]
    courses: List[DashboardCourse]
    alerts: List[DashboardAlert] = []
    metrics: dict = {}


# ==================== Enrollment Request Schemas ====================

class EnrollmentRequest(BaseModel):
    course_id: str
    student_id: Optional[str] = None  # parent use: which linked child to enroll

class EnrollmentAction(BaseModel):
    reason: Optional[str] = None


# ==================== Notification Schemas ====================

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    message: str
    type: str
    title: Optional[str] = None
    course_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    read_status: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Course Material Schemas ====================

class CourseMaterialCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    link_url: Optional[str] = Field(None, max_length=500)

class CourseMaterialResponse(BaseModel):
    id: str
    course_id: str
    title: str
    file_url: Optional[str]
    link_url: Optional[str]
    uploaded_by: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Search Schemas ====================

class SearchResult(BaseModel):
    type: str       # "course" | "student" | "teacher"
    id: str
    title: str
    subtitle: Optional[str] = None
    status: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


# ==================== Audit Log Schemas ====================

class AuditLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[dict]
    timestamp: datetime

    class Config:
        from_attributes = True


# ==================== Lesson Record Schemas ====================

class LessonRecordCreate(BaseModel):
    student_id: str
    course_id: str
    lesson_date: datetime
    attendance_status: str = Field(..., pattern="^(present|absent|late|excused)$")
    grade_value: Optional[float] = Field(None, ge=0, le=100)
    teacher_feedback: Optional[str] = Field(None, max_length=1000)
    difficulty_level: Optional[str] = Field(None, pattern="^(easy|medium|hard)$")
    engagement_rating: Optional[int] = Field(None, ge=1, le=5)

class LessonRecordResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    lesson_date: datetime
    attendance_status: str
    grade_value: Optional[float]
    teacher_feedback: Optional[str]
    difficulty_level: Optional[str]
    engagement_rating: Optional[int]
    created_by_teacher_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Progress Metrics Schemas ====================

class ProgressMetricsResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    average_grade: float
    attendance_rate: float
    trend_direction: str
    last_updated: datetime

    class Config:
        from_attributes = True


# ==================== AI Alert Schemas ====================

class AIAlertResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    alert_level: str
    message: str
    recommendation: str
    lesson_record_id: Optional[str]
    notification_sent: bool
    parent_seen: bool = False
    parent_acknowledged: bool = False
    parent_acknowledged_at: Optional[datetime] = None
    parent_comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ParentAcknowledgeRequest(BaseModel):
    comment: Optional[str] = Field(None, max_length=500)


# ==================== Weekly Summary Schemas ====================

class WeeklySummaryResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    week_start: datetime
    attendance_present: int
    attendance_absent: int
    average_grade: float
    trend_vs_previous: str
    teacher_feedback_highlights: List[str]
    ai_observations: Optional[str]
    email_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Timeline Schemas ====================

class TimelineEntry(BaseModel):
    """One event in a student's chronological academic timeline."""
    entry_type: str          # "lesson" | "grade" | "attendance" | "feedback" | "alert"
    timestamp: datetime
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    summary: str
    detail: Optional[str] = None
    icon: str = "📋"
    severity: Optional[str] = None  # for alert entries

class TimelineResponse(BaseModel):
    student_id: str
    entries: List[TimelineEntry]
    total: int


# ==================== Trend Schemas ====================

class TrendPoint(BaseModel):
    """One data point in a weekly trend series."""
    week_label: str          # e.g. "2025-W12"
    week_start: datetime
    average_grade: Optional[float]
    attendance_rate: Optional[float]
    lesson_count: int
    avg_engagement: Optional[float]

class TrendDataset(BaseModel):
    student_id: str
    course_id: Optional[str]
    direction: str           # "improving" | "declining" | "stable"
    points: List[TrendPoint]


# ==================== System Health Schemas ====================

class SystemHealthResponse(BaseModel):
    active_users: int
    total_lesson_records: int
    lesson_records_last_7_days: int
    total_ai_alerts: int
    alerts_last_7_days: int
    critical_alerts_open: int
    weekly_summaries_sent: int
    parent_acknowledgements_pending: int


# ==================== Performance Score Schemas ====================

class PerformanceScoreResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    score: float
    classification: str
    grade_score: float
    attendance_score: float
    feedback_score: float
    trend_score: float
    computed_at: datetime

    class Config:
        from_attributes = True


# ==================== Message Schemas ====================

class MessageCreate(BaseModel):
    recipient_id: str
    subject: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = Field("general", pattern="^(general|academic|alert|announcement)$")
    course_id: Optional[str] = None
    send_email: bool = False

class MessageResponse(BaseModel):
    id: str
    sender_id: str
    recipient_id: str
    subject: str
    content: str
    message_type: str
    course_id: Optional[str] = None
    read_status: bool
    email_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Syllabus Schemas ====================

class WeeklyTopicSchema(BaseModel):
    week_number: int = Field(..., ge=1, le=52)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    objectives: List[str] = Field(default_factory=list)
    materials: List[str] = Field(default_factory=list)
    assignments: List[str] = Field(default_factory=list)
    teacher_notes: Optional[str] = Field(None, max_length=1000)

class SyllabusCreate(BaseModel):
    course_id: str
    topics: List[WeeklyTopicSchema] = Field(default_factory=list)

class SyllabusUpdate(BaseModel):
    topics: Optional[List[WeeklyTopicSchema]] = None
    status: Optional[str] = Field(None, pattern="^(draft|published)$")

class SyllabusResponse(BaseModel):
    id: str
    course_id: str
    version: int
    status: str
    topics: List[WeeklyTopicSchema]
    completed_weeks: List[int] = []
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MilestoneCompleteRequest(BaseModel):
    week_number: int = Field(..., ge=1, le=52)


# ==================== Usability Feedback Schemas ====================

# ── Chat ────────────────────────────────────────────────────────────────────

class ConversationStartRequest(BaseModel):
    type: str = Field(..., pattern="^(direct|course)$")
    participant_id: Optional[str] = None  # for direct chats
    course_id: Optional[str] = None       # for course chats

class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_avatar_url: Optional[str] = None
    content: str
    read_by: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationResponse(BaseModel):
    id: str
    type: str
    participant_ids: List[str]
    course_id: Optional[str]
    other_participant_name: Optional[str]          # for direct chats
    other_participant_avatar_url: Optional[str] = None  # for direct chats
    course_name: Optional[str]                     # for course chats
    last_message_at: datetime
    last_message_preview: Optional[str]
    unread_count: int
    created_at: datetime

    class Config:
        from_attributes = True

class ChatContactResponse(BaseModel):
    id: str
    name: str
    role: str
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    last_active_at: Optional[datetime] = None  # for presence indicator


class PresenceItem(BaseModel):
    user_id: str
    is_online: bool
    last_active_at: Optional[datetime] = None


class UsabilityFeedbackCreate(BaseModel):
    report_clarity: int = Field(..., ge=1, le=5)
    dashboard_usability: int = Field(..., ge=1, le=5)
    navigation_ease: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)

class UsabilityFeedbackResponse(BaseModel):
    id: str
    user_id: str
    report_clarity: int
    dashboard_usability: int
    navigation_ease: int
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
