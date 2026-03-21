# IQ PLUS Database Schema

## Entity Relationship Diagram

```
┌─────────────────┐
│     User        │
├─────────────────┤
│ id (PK)         │
│ firebase_uid    │
│ email           │
│ first_name      │
│ last_name       │
│ role (enum)     │
│ is_active       │
│ created_at      │
└─────────────────┘
        │
        ├──────────────────────────┬──────────────────┐
        │                          │                  │
        ▼                          ▼                  ▼
┌─────────────────┐    ┌──────────────────┐  ┌──────────────────┐
│  Enrollment     │    │      Grade       │  │   Attendance     │
├─────────────────┤    ├──────────────────┤  ├──────────────────┤
│ id (PK)         │    │ id (PK)          │  │ id (PK)          │
│ student_id (FK) │    │ student_id (FK)  │  │ student_id (FK)  │
│ course_id (FK)  │    │ course_id (FK)   │  │ course_id (FK)   │
│ status (enum)   │    │ score (0-100)    │  │ date             │
│ enrolled_at     │    │ subject          │  │ status (enum)    │
│ completed_at    │    │ recorded_at      │  │ remarks          │
└─────────────────┘    └──────────────────┘  └──────────────────┘
        │
        └──────────────────────────┬──────────────────────────┐
                                   │                          │
                                   ▼                          ▼
                            ┌──────────────────┐    ┌──────────────────┐
                            │     Course       │    │    Feedback      │
                            ├──────────────────┤    ├──────────────────┤
                            │ id (PK)          │    │ id (PK)          │
                            │ code             │    │ student_id (FK)  │
                            │ name             │    │ course_id (FK)   │
                            │ description      │    │ sentiment        │
                            │ teacher_id (FK)  │    │ content          │
                            │ schedule         │    │ submitted_at     │
                            │ capacity         │    └──────────────────┘
                            │ created_at       │
                            └──────────────────┘
                                    │
                                    │
                            (taught by Teacher)
                                    │
                                    └──► references User(teacher_id)

        ┌─────────────────────────────────────────┐
        │         LearningInsight                 │
        ├─────────────────────────────────────────┤
        │ id (PK)                                 │
        │ student_id (FK)                         │
        │ course_id (FK)                          │
        │ change_percentage (float)               │
        │ insight_type (enum)                     │
        │ summary (text)                          │
        │ metric_name (string)                    │
        │ prev_value (float)                      │
        │ curr_value (float)                      │
        │ email_sent (boolean)                    │
        │ created_at                              │
        └─────────────────────────────────────────┘
        │
        └──► references User(student_id) + Course(course_id)
```

## Core Tables

### Users (Authentication Domain)
- Stores Firebase UID, not passwords
- Roles: ADMIN, TEACHER, STUDENT, PARENT
- Soft delete support (deleted_at)

### Courses (Curriculum Domain)
- Created and managed by teachers
- Schedule stored as JSON
- Capacity tracking for enrollments
- Teacher assignment

### Enrollments (Enrollment Domain)
- Links students to courses
- Status tracking (ACTIVE, COMPLETED, WITHDRAWN)
- Conflict detection logic prevents scheduling overlaps

### Grades (Academic Domain)
- Per-course, per-subject tracking
- Score ranges 0-100
- Timestamped for audit trail

### Attendance (Academic Domain)
- Daily tracking per student-course combination
- Statuses: PRESENT, ABSENT, LATE, EXCUSED
- Remarks field for context

### Feedback (Academic Domain)
- Student feedback on courses
- Sentiment analysis (POSITIVE, NEUTRAL, NEGATIVE)
- Stores student opinions

### LearningInsights (AI Domain)
- Trigger: After significant changes in grades or attendance
- Threshold: ±15% change over configurable time window
- Stores explainable insights
- Email notification flag to prevent duplicate sends

## Key Design Decisions

1. **Firebase UID Primary**: No password storage - all auth via Firebase
2. **Soft Deletes**: deleted_at field for audit compliance
3. **Timestamps**: All tables track created_at, modified_at for audit trail
4. **AI Trigger**: LearningInsight created only when threshold met
5. **Email Notification**: Tracks sent status to avoid spam
6. **Schedule Conflict Detection**: Logic in application layer uses course schedule JSON
