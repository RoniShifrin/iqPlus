"""Course management API routes — full RBAC enforcement"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime

from app.models import User, RoleEnum, Course, CourseStatusEnum, VisibilityScopeEnum
from app.schemas import CourseCreate, CourseUpdate, CourseResponse
from app.security import get_current_user, require_course_owner_or_admin
from app.repositories import CourseRepository, UserRepository, AuditLogRepository

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _serialize(course: Course) -> dict:
    return {
        "id": str(course.id),
        "code": course.code,
        "name": course.name,
        "description": course.description,
        "teacher_id": course.teacher_id,
        "created_by_role": course.created_by_role,
        "schedule": course.schedule,
        "capacity": course.capacity,
        "status": course.status,
        "visibility_scope": course.visibility_scope,
        "created_at": course.created_at,
    }


# ── POST /api/courses  (Admin + Teacher only) ────────────────────────────────
@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.TEACHER]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can create courses")

    existing = await CourseRepository.get_by_code(body.code)
    if existing:
        raise HTTPException(status_code=400, detail="Course code already exists")

    # Determine which teacher owns this course
    if current_user.role == RoleEnum.ADMIN:
        if not body.teacher_id:
            raise HTTPException(status_code=400, detail="Admin must assign a teacher when creating a course")
        teacher = await UserRepository.get_by_id(body.teacher_id)
        if not teacher or teacher.role != RoleEnum.TEACHER or not teacher.is_active or teacher.deleted_at is not None:
            raise HTTPException(status_code=400, detail="Invalid or inactive teacher")
        assigned_teacher_id = body.teacher_id
    else:
        # Teacher creates a course — always assigned to themselves
        assigned_teacher_id = str(current_user.id)

    course = await CourseRepository.create(
        code=body.code,
        name=body.name,
        description=body.description,
        schedule=body.schedule,
        capacity=body.capacity,
        visibility_scope=body.visibility_scope,
        teacher_id=assigned_teacher_id,
        created_by_role=current_user.role.value,
        status=CourseStatusEnum.DRAFT,
    )
    return CourseResponse(**_serialize(course))


# ── GET /api/courses  (role-filtered) ────────────────────────────────────────
@router.get("/", response_model=List[CourseResponse])
async def list_courses(current_user: User = Depends(get_current_user)):
    if current_user.role == RoleEnum.ADMIN:
        # Admin sees every non-deleted course
        courses = await Course.find(Course.deleted_at == None).to_list()

    elif current_user.role == RoleEnum.TEACHER:
        # Teacher sees own courses (all statuses) + published school_only/public from others
        own = await Course.find(
            Course.teacher_id == str(current_user.id),
            Course.deleted_at == None
        ).to_list()
        others = await Course.find(
            Course.teacher_id != str(current_user.id),
            Course.status == CourseStatusEnum.PUBLISHED,
            Course.visibility_scope != VisibilityScopeEnum.TEACHER_ONLY,
            Course.deleted_at == None
        ).to_list()
        seen = {str(c.id) for c in own}
        courses = own + [c for c in others if str(c.id) not in seen]

    elif current_user.role == RoleEnum.STUDENT:
        # Student sees published, non-teacher-only courses
        courses = await Course.find(
            Course.status == CourseStatusEnum.PUBLISHED,
            Course.visibility_scope != VisibilityScopeEnum.TEACHER_ONLY,
            Course.deleted_at == None
        ).to_list()

    elif current_user.role == RoleEnum.PARENT:
        # Parent: all published non-teacher-only courses (same scope as student)
        courses = await Course.find(
            Course.status == CourseStatusEnum.PUBLISHED,
            Course.visibility_scope != VisibilityScopeEnum.TEACHER_ONLY,
            Course.deleted_at == None
        ).to_list()

    else:
        courses = []

    return [CourseResponse(**_serialize(c)) for c in courses]


# ── GET /api/courses/my-courses ───────────────────────────────────────────────
@router.get("/my-courses", response_model=List[CourseResponse])
async def my_courses(current_user: User = Depends(get_current_user)):
    if current_user.role == RoleEnum.TEACHER:
        courses = await CourseRepository.list_by_teacher(str(current_user.id))
    elif current_user.role == RoleEnum.STUDENT:
        from app.services import CourseService
        courses = await CourseService.get_student_courses(str(current_user.id))
    elif current_user.role == RoleEnum.PARENT:
        from app.services import CourseService
        linked_ids = current_user.linked_student_ids or []
        rows = await CourseService.get_courses_for_students(linked_ids)
        seen_ids: set = set()
        courses = []
        for row in rows:
            cid = str(row["course"].id)
            if cid not in seen_ids:
                seen_ids.add(cid)
                courses.append(row["course"])
    else:
        courses = []
    return [CourseResponse(**_serialize(c)) for c in courses]


# ── GET /api/courses/{id} ────────────────────────────────────────────────────
@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    try:
        course = await CourseRepository.get_by_id(course_id)
    except Exception:
        course = None

    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Course not found")

    # Visibility check
    if current_user.role == RoleEnum.ADMIN:
        pass  # sees all
    elif current_user.role == RoleEnum.TEACHER:
        if course.teacher_id != str(current_user.id):
            if course.status != CourseStatusEnum.PUBLISHED:
                raise HTTPException(status_code=404, detail="Course not found")
            if course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
                raise HTTPException(status_code=404, detail="Course not found")
    elif current_user.role == RoleEnum.PARENT:
        # Parent: same scope as the list — any published, non-teacher-only course
        if course.status != CourseStatusEnum.PUBLISHED or course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        # Student (and any other non-admin, non-teacher, non-parent role)
        if course.status != CourseStatusEnum.PUBLISHED:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
            raise HTTPException(status_code=404, detail="Course not found")

    return CourseResponse(**_serialize(course))


# ── PUT /api/courses/{id} ────────────────────────────────────────────────────
@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    body: CourseUpdate,
    ownership=Depends(require_course_owner_or_admin),
):
    course, current_user = ownership
    if course.status == CourseStatusEnum.ARCHIVED and current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Archived courses cannot be edited. Only admin can modify archived courses.",
        )
    updates = body.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.utcnow()
    updated = await CourseRepository.update(str(course.id), **updates)
    return CourseResponse(**_serialize(updated))


# ── DELETE /api/courses/{id}  (soft-delete) ───────────────────────────────────
@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    ownership=Depends(require_course_owner_or_admin),
):
    course, _ = ownership
    await course.set({"deleted_at": datetime.utcnow()})


# ── POST /api/courses/{id}/publish ────────────────────────────────────────────
@router.post("/{course_id}/publish", response_model=CourseResponse)
async def publish_course(
    course_id: str,
    ownership=Depends(require_course_owner_or_admin),
):
    course, _ = ownership
    if course.status == CourseStatusEnum.ARCHIVED:
        raise HTTPException(status_code=400, detail="Cannot publish an archived course")
    await course.set({"status": CourseStatusEnum.PUBLISHED, "updated_at": datetime.utcnow()})
    return CourseResponse(**_serialize(course))


# ── POST /api/courses/{id}/archive ────────────────────────────────────────────
@router.post("/{course_id}/archive", response_model=CourseResponse)
async def archive_course(
    course_id: str,
    ownership=Depends(require_course_owner_or_admin),
):
    course, _ = ownership
    await course.set({"status": CourseStatusEnum.ARCHIVED, "updated_at": datetime.utcnow()})
    return CourseResponse(**_serialize(course))


# ── POST /api/courses/{id}/restore ───────────────────────────────────────────
@router.post("/{course_id}/restore", response_model=CourseResponse)
async def restore_course(
    course_id: str,
    ownership=Depends(require_course_owner_or_admin),
):
    """Restore an archived course back to published status. Allowed for owner-teacher and admin."""
    course, _ = ownership
    if course.status != CourseStatusEnum.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archived courses can be restored.",
        )
    await course.set({"status": CourseStatusEnum.PUBLISHED, "updated_at": datetime.utcnow()})
    return CourseResponse(**_serialize(course))


# ── POST /api/courses/{id}/announce ──────────────────────────────────────────
@router.post("/{course_id}/announce")
async def announce_course(
    course_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Send a group email/message to all enrolled students (optionally their parents too)."""
    from app.repositories import EnrollmentRepository, MessageRepository
    from app.services.email_service import EmailNotificationService

    try:
        course = await CourseRepository.get_by_id(course_id)
    except Exception:
        course = None
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Course not found")

    if current_user.role not in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        raise HTTPException(status_code=403, detail="Only teachers and admins can send announcements")
    if current_user.role == RoleEnum.TEACHER and course.teacher_id != str(current_user.id):
        raise HTTPException(status_code=403, detail="You can only announce to your own courses")

    subject = (body.get("subject") or "").strip()
    content = (body.get("content") or "").strip()
    include_parents = bool(body.get("include_parents", False))

    if not subject or not content:
        raise HTTPException(status_code=400, detail="Subject and content are required")

    from app.models import MessageTypeEnum
    from app.repositories import UserRepository as _UR

    all_enrs = await EnrollmentRepository.list_by_course(course_id)
    active_enrs = [
        e for e in all_enrs
        if (e.status.value if hasattr(e.status, "value") else e.status) in ("active", "completed")
    ]
    if not active_enrs:
        return {"sent_count": 0, "message": "No active students enrolled"}

    sender_name = current_user.full_name()
    html = (
        f"<p>Announcement from <strong>{sender_name}</strong> ({course.name}):</p>"
        f"<h3>{subject}</h3><p>{content}</p>"
    )

    parent_map: dict = {}
    if include_parents:
        parents = await User.find(User.role == RoleEnum.PARENT).to_list()
        for p in parents:
            for sid in (p.linked_student_ids or []):
                parent_map[sid] = p

    # Batch-load all students at once instead of N individual queries
    from beanie import PydanticObjectId as _POID
    _student_oids = []
    for enr in active_enrs:
        try:
            _student_oids.append(_POID(enr.student_id))
        except Exception:
            pass
    if _student_oids:
        from app.models import User as _User
        _students_batch = await _User.find({"_id": {"$in": _student_oids}}).to_list()
        _student_map = {str(s.id): s for s in _students_batch}
    else:
        _student_map = {}

    sent_count = 0
    for enr in active_enrs:
        student = _student_map.get(enr.student_id)
        if not student:
            continue
        try:
            await MessageRepository.create(
                sender_id=str(current_user.id),
                recipient_id=enr.student_id,
                subject=subject,
                content=content,
                message_type=MessageTypeEnum.ANNOUNCEMENT,
                email_sent=False,
            )
        except Exception:
            pass
        if student.email:
            ok = EmailNotificationService.send_email(student.email, f"IQ PLUS: {subject}", html)
            if ok:
                sent_count += 1

        if include_parents and enr.student_id in parent_map:
            parent = parent_map[enr.student_id]
            try:
                await MessageRepository.create(
                    sender_id=str(current_user.id),
                    recipient_id=str(parent.id),
                    subject=subject,
                    content=content,
                    message_type=MessageTypeEnum.ANNOUNCEMENT,
                    email_sent=False,
                )
            except Exception:
                pass
            if parent.email:
                ok = EmailNotificationService.send_email(parent.email, f"IQ PLUS: {subject}", html)
                if ok:
                    sent_count += 1

    return {"sent_count": sent_count, "message": f"Sent to {sent_count} recipient(s)"}


# ── GET /api/courses/{id}/detail ──────────────────────────────────────────────
@router.get("/{course_id}/detail")
async def get_course_detail(
    course_id: str,
    current_user: User = Depends(get_current_user),
):
    """Aggregated course detail — syllabus, materials, roster (teacher/admin), feedback."""
    from app.repositories import (
        EnrollmentRepository, CourseMaterialRepository,
        PerformanceScoreRepository, FeedbackRepository,
    )

    # ── same visibility check as get_course ──────────────────────────────────
    try:
        course = await CourseRepository.get_by_id(course_id)
    except Exception:
        course = None
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Course not found")

    uid  = str(current_user.id)
    role = current_user.role

    if role == RoleEnum.ADMIN:
        pass
    elif role == RoleEnum.TEACHER:
        if course.teacher_id != uid:
            if course.status != CourseStatusEnum.PUBLISHED or course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
                raise HTTPException(status_code=404, detail="Course not found")
    elif role == RoleEnum.PARENT:
        # Parent: same scope as the list — any published, non-teacher-only course
        if course.status != CourseStatusEnum.PUBLISHED or course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
            raise HTTPException(status_code=404, detail="Course not found")
    else:
        # Student (and any other non-admin, non-teacher, non-parent role)
        if course.status != CourseStatusEnum.PUBLISHED:
            raise HTTPException(status_code=404, detail="Course not found")
        if course.visibility_scope == VisibilityScopeEnum.TEACHER_ONLY:
            raise HTTPException(status_code=404, detail="Course not found")

    # ── common data ───────────────────────────────────────────────────────────
    from app.repositories import UserRepository as UR, SyllabusRepository as SR
    teacher = await UR.get_by_id(course.teacher_id)
    teacher_name = teacher.full_name() if teacher else "Unknown"

    # Syllabus
    syllabus = await SR.get_by_course(course_id)
    syllabus_data = None
    if syllabus:
        syl_status = syllabus.status.value if hasattr(syllabus.status, "value") else syllabus.status
        if role in (RoleEnum.STUDENT, RoleEnum.PARENT) and syl_status != "published":
            syllabus_data = None
        else:
            topics = []
            for t in (syllabus.topics or []):
                td = {
                    "week_number": t.week_number,
                    "title": t.title,
                    "description": t.description,
                    "objectives": list(t.objectives or []),
                    "materials": list(t.materials or []),
                    "assignments": list(t.assignments or []),
                }
                if role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
                    td["teacher_notes"] = t.teacher_notes
                topics.append(td)
            syllabus_data = {
                "id": str(syllabus.id),
                "status": syl_status,
                "version": syllabus.version,
                "topics": topics,
                "completed_weeks": list(syllabus.completed_weeks or []),
            }

    # Materials
    mats = await CourseMaterialRepository.list_by_course(course_id)
    materials_data = [{
        "id": str(m.id),
        "title": m.title,
        "file_url": m.file_url,
        "link_url": m.link_url,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in mats]

    # Enrollment count
    all_enrs = await EnrollmentRepository.list_by_course(course_id)
    active_enrs = [
        e for e in all_enrs
        if (e.status.value if hasattr(e.status, "value") else e.status) in ("active", "completed")
    ]

    # ── role-specific roster / progress ──────────────────────────────────────
    roster: list = []
    unenrolled_children: list = []
    my_progress = None
    feedback_list: list = []
    pending_requests: list = []
    my_enrollment_status: Optional[str] = None

    if role in (RoleEnum.TEACHER, RoleEnum.ADMIN):
        from beanie import PydanticObjectId

        # Batch load all students for this roster (1 query instead of N)
        student_ids = [e.student_id for e in active_enrs if e.student_id]
        student_map: dict = {}
        if student_ids:
            valid_oids = []
            for sid in student_ids:
                try:
                    valid_oids.append(PydanticObjectId(sid))
                except Exception:
                    pass
            if valid_oids:
                students_batch = await User.find({"_id": {"$in": valid_oids}}).to_list()
                student_map = {str(u.id): u for u in students_batch}

        # Batch load all scores for this course (1 query instead of N)
        scores_batch = await PerformanceScoreRepository.list_by_course(course_id) if student_ids else []
        score_map: dict = {ps.student_id: ps for ps in scores_batch}

        # Load all parents once for O(1) lookup (scoped to students in this course)
        parent_map: dict = {}
        if student_ids:
            parents_batch = await User.find(
                {"role": "parent", "linked_student_ids": {"$in": student_ids}}
            ).to_list()
            for p in parents_batch:
                for sid in (p.linked_student_ids or []):
                    if sid in student_ids:
                        parent_map[sid] = {"parent_id": str(p.id), "parent_email": p.email}

        for enr in active_enrs:
            student = student_map.get(enr.student_id)
            if not student:
                continue
            score = score_map.get(enr.student_id)
            pinfo = parent_map.get(enr.student_id, {})
            roster.append({
                "enrollment_id": str(enr.id),
                "student_id": enr.student_id,
                "student_name": student.full_name(),
                "student_email": student.email,
                "enrollment_status": enr.status.value if hasattr(enr.status, "value") else enr.status,
                "score": score.score if score else None,
                "classification": (
                    score.classification.value if hasattr(score.classification, "value") else score.classification
                ) if score else None,
                "parent_id": pinfo.get("parent_id"),
                "parent_email": pinfo.get("parent_email"),
            })

        feedbacks = await FeedbackRepository.list_by_course(course_id)
        for f in feedbacks:
            feedback_list.append({
                "id": str(f.id),
                "student_id": f.student_id,
                "sentiment": f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment,
                "content": f.content,
                "visibility": f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private"),
                "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
            })

        # Pending enrollment requests for this course
        pending_enrs = [
            e for e in all_enrs
            if (e.status.value if hasattr(e.status, "value") else e.status) == "pending"
        ]
        if pending_enrs:
            pending_ids = [e.student_id for e in pending_enrs]
            valid_pending_oids = []
            for sid in pending_ids:
                try:
                    valid_pending_oids.append(PydanticObjectId(sid))
                except Exception:
                    pass
            pending_student_map: dict = {}
            if valid_pending_oids:
                ps_batch = await User.find({"_id": {"$in": valid_pending_oids}}).to_list()
                pending_student_map = {str(u.id): u for u in ps_batch}
            for enr in pending_enrs:
                st = pending_student_map.get(enr.student_id)
                pending_requests.append({
                    "enrollment_id": str(enr.id),
                    "student_id": enr.student_id,
                    "student_name": st.full_name() if st else enr.student_id,
                    "student_email": st.email if st else None,
                    "requested_at": enr.enrolled_at.isoformat() if enr.enrolled_at else None,
                })

    elif role == RoleEnum.STUDENT:
        score = await PerformanceScoreRepository.get(uid, course_id)
        if score:
            my_progress = {
                "score": score.score,
                "classification": score.classification.value if hasattr(score.classification, "value") else score.classification,
            }
        feedbacks = await FeedbackRepository.list_by_student_course(uid, course_id)
        for f in feedbacks:
            vis = f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private")
            if vis == "published":
                feedback_list.append({
                    "id": str(f.id),
                    "sentiment": f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment,
                    "content": f.content,
                    "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
                })
        my_enr = await EnrollmentRepository.get_by_student_course(uid, course_id)
        my_enrollment_status = (
            my_enr.status.value if my_enr and hasattr(my_enr.status, "value") else (my_enr.status if my_enr else None)
        )

    elif role == RoleEnum.PARENT:
        from app.repositories import EnrollmentRepository as ER
        unenrolled_children: list = []
        for sid in (current_user.linked_student_ids or []):
            enr = await ER.get_by_student_course(sid, course_id)
            enr_status = (enr.status.value if enr and hasattr(enr.status, "value") else (enr.status if enr else None))
            if enr_status in ("active", "completed"):
                child = await UR.get_by_id(sid)
                score = await PerformanceScoreRepository.get(sid, course_id)
                feedbacks = await FeedbackRepository.list_by_student_course(sid, course_id)
                pub_fb = []
                for f in feedbacks:
                    vis = f.visibility.value if hasattr(f.visibility, "value") else getattr(f, "visibility", "private")
                    if vis == "published":
                        pub_fb.append({
                            "id": str(f.id),
                            "sentiment": f.sentiment.value if hasattr(f.sentiment, "value") else f.sentiment,
                            "content": f.content,
                            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
                        })
                roster.append({
                    "student_id": sid,
                    "student_name": child.full_name() if child else sid,
                    "score": score.score if score else None,
                    "classification": (
                        score.classification.value if hasattr(score.classification, "value") else score.classification
                    ) if score else None,
                    "feedback": pub_fb,
                })
            else:
                # child is pending, rejected, withdrawn, or not enrolled — parent can request enrollment
                child = await UR.get_by_id(sid)
                unenrolled_children.append({
                    "student_id": sid,
                    "student_name": child.full_name() if child else sid,
                    "enrollment_status": enr_status,  # None | "pending" | "rejected" | "withdrawn"
                })

    return {
        "course": {
            **_serialize(course),
            "teacher_name": teacher_name,
            "enrolled_count": len(active_enrs),
        },
        "syllabus": syllabus_data,
        "materials": materials_data,
        "roster": roster,
        "unenrolled_children": unenrolled_children if role == RoleEnum.PARENT else [],
        "pending_requests": pending_requests,
        "my_progress": my_progress,
        "my_enrollment_status": my_enrollment_status,
        "feedback": feedback_list,
    }


# ── PATCH /api/courses/{course_id}/teacher  (Admin only) ─────────────────────
@router.patch("/{course_id}/teacher")
async def change_course_teacher(
    course_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Admin only: reassign a course to a different teacher."""
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

    course = await CourseRepository.get_by_id(course_id)
    if not course or course.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    new_teacher_id = body.get("teacher_id", "").strip()
    if not new_teacher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="teacher_id is required")

    teacher = await UserRepository.get_by_id(new_teacher_id)
    if not teacher or teacher.role != RoleEnum.TEACHER or not teacher.is_active or teacher.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive teacher")

    old_teacher_id = course.teacher_id
    await CourseRepository.update(course_id, teacher_id=new_teacher_id)

    await AuditLogRepository.log(
        user_id=str(current_user.id),
        action="course_teacher_changed",
        resource_type="course",
        resource_id=course_id,
        details={"old_teacher_id": old_teacher_id, "new_teacher_id": new_teacher_id},
    )

    updated = await CourseRepository.get_by_id(course_id)
    return _serialize(updated)
