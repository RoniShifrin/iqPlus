"""Role-specific dashboard data endpoints"""
from fastapi import APIRouter, Depends
from typing import List

from app.models import (
    User, Course, Enrollment, LearningInsight,
    RoleEnum, CourseStatusEnum, VisibilityScopeEnum, EnrollmentStatusEnum
)
from app.schemas import DashboardResponse, DashboardCourse, DashboardAlert
from app.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _course_dto(c: Course, enrolled_count: int = None, teacher_name: str = None) -> DashboardCourse:
    return DashboardCourse(
        id=str(c.id),
        code=c.code,
        name=c.name,
        status=c.status,
        visibility_scope=c.visibility_scope,
        capacity=c.capacity,
        description=c.description,
        enrolled_count=enrolled_count,
        teacher_name=teacher_name,
        schedule=c.schedule,
    )


@router.get("", response_model=DashboardResponse)
async def get_dashboard(current_user: User = Depends(get_current_user)):
    from datetime import datetime as dt
    # Lightweight activity stamp — fire-and-forget, never blocks the response
    try:
        await current_user.set({"last_active_at": dt.utcnow()})
    except Exception:
        pass

    role = current_user.role
    if role == RoleEnum.ADMIN:
        return await _admin_dashboard(current_user)
    elif role == RoleEnum.TEACHER:
        return await _teacher_dashboard(current_user)
    elif role == RoleEnum.STUDENT:
        return await _student_dashboard(current_user)
    else:
        return await _parent_dashboard(current_user)


async def _admin_dashboard(user: User) -> DashboardResponse:
    from app.models import LessonRecord
    all_courses = await Course.find(Course.deleted_at == None).to_list()
    total_users = await User.find(User.deleted_at == None).count()
    total_enrollments = await Enrollment.find().count()
    total_students = await User.find(User.role == RoleEnum.STUDENT, User.deleted_at == None).count()
    total_teachers = await User.find(User.role == RoleEnum.TEACHER, User.deleted_at == None).count()

    from datetime import timedelta
    from datetime import datetime as dt
    upcoming_window = dt.utcnow() + timedelta(days=7)
    upcoming_lessons = await LessonRecord.find(
        LessonRecord.lesson_date >= dt.utcnow(),
        LessonRecord.lesson_date <= upcoming_window,
    ).count()

    # Batch-fetch teacher names for all courses in a single query
    from beanie import PydanticObjectId
    admin_teacher_ids: set = set(c.teacher_id for c in all_courses if c.teacher_id)
    admin_teacher_map: dict = {}
    if admin_teacher_ids:
        valid_oids = []
        for tid in admin_teacher_ids:
            try:
                valid_oids.append(PydanticObjectId(tid))
            except Exception:
                pass
        if valid_oids:
            teachers_batch = await User.find(
                {"_id": {"$in": valid_oids}, "role": RoleEnum.TEACHER, "deleted_at": None}
            ).to_list()
            admin_teacher_map = {str(t.id): t.full_name() for t in teachers_batch}

    # Batch-load all active enrollment counts in one query instead of N .count() calls
    all_course_ids = [str(c.id) for c in all_courses]
    enr_count_map: dict = {}
    if all_course_ids:
        active_enrs_all = await Enrollment.find(
            {"course_id": {"$in": all_course_ids}, "status": EnrollmentStatusEnum.ACTIVE}
        ).to_list()
        for e in active_enrs_all:
            enr_count_map[e.course_id] = enr_count_map.get(e.course_id, 0) + 1

    course_dtos = [
        _course_dto(c, enr_count_map.get(str(c.id), 0), teacher_name=admin_teacher_map.get(c.teacher_id))
        for c in all_courses
    ]

    draft_count     = sum(1 for c in all_courses if c.status == CourseStatusEnum.DRAFT)
    active_courses  = sum(1 for c in all_courses if c.status == CourseStatusEnum.PUBLISHED)
    archived_courses = sum(1 for c in all_courses if c.status == CourseStatusEnum.ARCHIVED)
    active_users    = await User.find(User.is_active == True, User.deleted_at == None).count()  # noqa: E712

    # Average students per published course
    published_dtos = [dto for dto in course_dtos if str(dto.status) in ("published", "CourseStatusEnum.PUBLISHED")]
    # Use raw counts from all course_dtos; filter by status
    published_enrolled = [
        (dto.enrolled_count or 0) for dto, c in zip(course_dtos, all_courses)
        if c.status == CourseStatusEnum.PUBLISHED
    ]
    avg_students = round(sum(published_enrolled) / len(published_enrolled), 1) if published_enrolled else 0

    # Teacher workload: {teacher_id: course_count} — only active teachers, non-archived courses
    teacher_workload: dict = {}
    for c in all_courses:
        if c.status != CourseStatusEnum.ARCHIVED and c.teacher_id in admin_teacher_map:
            teacher_workload[c.teacher_id] = teacher_workload.get(c.teacher_id, 0) + 1

    # teacher_names: {teacher_id: full_name} — reuses admin_teacher_map (active teachers only)
    teacher_names: dict = dict(admin_teacher_map)

    alerts = []
    if draft_count > 0:
        alerts.append(DashboardAlert(
            type="info",
            message=f"{draft_count} course(s) are still in Draft — publish when ready.",
        ))

    # Real progress distribution across all enrolled students
    from app.models import PerformanceScore as PS
    all_scores = await PS.find().to_list()
    dist = {"excellent": 0, "good": 0, "average": 0, "needs_attention": 0}
    for ps in all_scores:
        key = ps.classification.value if hasattr(ps.classification, "value") else str(ps.classification)
        if key in dist:
            dist[key] += 1
    at_risk_count      = dist["needs_attention"]
    students_improving = dist["excellent"] + dist["good"]

    return DashboardResponse(
        role="admin",
        allowed_actions=[
            "manage_users", "manage_courses", "view_analytics",
            "create_course", "publish_course", "archive_course", "delete_course"
        ],
        courses=course_dtos,
        alerts=alerts,
        metrics={
            "total_users": total_users,
            "total_courses": len(all_courses),
            "total_enrollments": total_enrollments,
            "draft_courses": draft_count,
            "published_courses": active_courses,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "active_courses": active_courses,
            "archived_courses": archived_courses,
            "active_users": active_users,
            "avg_students_per_course": avg_students,
            "teacher_workload": teacher_workload,
            "teacher_names": teacher_names,
            "upcoming_lessons": upcoming_lessons,
            "registered_users": total_users,
            # Real progress distribution
            "progress_distribution": dist,
            "at_risk_count": at_risk_count,
            "students_improving": students_improving,
        },
    )


async def _teacher_dashboard(user: User) -> DashboardResponse:
    uid = str(user.id)
    my_courses = await Course.find(
        Course.teacher_id == uid,
        Course.deleted_at == None
    ).to_list()

    # Batch load all active enrollments for this teacher's courses in one query
    _my_course_ids = [str(c.id) for c in my_courses]
    _all_enr_counts = await Enrollment.find(
        {"course_id": {"$in": _my_course_ids}, "status": EnrollmentStatusEnum.ACTIVE}
    ).to_list()
    _count_map: dict = {}
    for _e in _all_enr_counts:
        _count_map[_e.course_id] = _count_map.get(_e.course_id, 0) + 1

    course_dtos = [_course_dto(c, _count_map.get(str(c.id), 0)) for c in my_courses]

    alerts = []
    my_course_ids = [str(c.id) for c in my_courses]
    if my_course_ids:
        insights = await LearningInsight.find(
            {"course_id": {"$in": my_course_ids}}
        ).sort(-LearningInsight.created_at).limit(5).to_list()
        for ins in insights:
            if abs(ins.change_percentage) >= 20:
                course_name = next((c.name for c in my_courses if str(c.id) == ins.course_id), None)
                alerts.append(DashboardAlert(
                    type="warning" if ins.change_percentage < 0 else "info",
                    message=ins.summary,
                    course_name=course_name,
                ))

    draft_count = sum(1 for c in my_courses if c.status == CourseStatusEnum.DRAFT)
    if draft_count:
        alerts.append(DashboardAlert(
            type="info",
            message=f"You have {draft_count} draft course(s) awaiting publication."
        ))

    total_enrolled = sum(dto.enrolled_count or 0 for dto in course_dtos)

    # Build student progress list — batch all queries to avoid N+1
    from app.models import PerformanceScore, ProgressPrediction as PP
    from app.repositories import UserRepository
    from beanie import PydanticObjectId

    course_ids_str = [str(c.id) for c in my_courses]

    # 1 query: all active enrollments for all teacher courses at once
    all_enrollments = await Enrollment.find(
        {"course_id": {"$in": course_ids_str}, "status": EnrollmentStatusEnum.ACTIVE}
    ).to_list()

    # Collect unique student IDs
    student_ids_set = {e.student_id for e in all_enrollments}
    student_ids = list(student_ids_set)

    # 1 query: batch load all student names
    user_map: dict = {}
    if student_ids:
        valid_oids = []
        for sid in student_ids:
            try:
                valid_oids.append(PydanticObjectId(sid))
            except Exception:
                pass
        if valid_oids:
            users_batch = await User.find({"_id": {"$in": valid_oids}}).to_list()
            user_map = {str(u.id): u for u in users_batch}

    # 1 query: batch load all performance scores for these students/courses
    score_map: dict = {}
    if student_ids and course_ids_str:
        scores_batch = await PerformanceScore.find(
            {"student_id": {"$in": student_ids}, "course_id": {"$in": course_ids_str}}
        ).to_list()
        score_map = {(ps.student_id, ps.course_id): ps for ps in scores_batch}

    # 1 query: batch load all progress predictions
    pred_map: dict = {}
    if student_ids and course_ids_str:
        preds_batch = await PP.find(
            {"student_id": {"$in": student_ids}, "course_id": {"$in": course_ids_str}}
        ).to_list()
        pred_map = {(p.student_id, p.course_id): p for p in preds_batch}

    # Build progress list using in-memory maps (no more per-student queries)
    student_progress: list = []
    for c in my_courses:
        cid = str(c.id)
        for enr in all_enrollments:
            if enr.course_id != cid:
                continue
            u = user_map.get(enr.student_id)
            student_name = u.full_name() if u else enr.student_id
            ps = score_map.get((enr.student_id, cid))
            pred = pred_map.get((enr.student_id, cid))
            student_progress.append({
                "student_id": enr.student_id,
                "student_name": student_name,
                "course_id": cid,
                "course_name": c.name,
                "score": ps.score if ps else None,
                "classification": ps.classification.value if ps and hasattr(ps.classification, "value") else (ps.classification if ps else None),
                "prediction_label": pred.prediction_label if pred else None,
                "risk_level": pred.risk_level if pred else None,
                "trend_score": ps.trend_score if ps else None,
            })

    return DashboardResponse(
        role="teacher",
        allowed_actions=[
            "create_course", "edit_own_course", "publish_course", "archive_course",
            "manage_enrollments", "record_grades", "record_attendance", "submit_feedback"
        ],
        courses=course_dtos,
        alerts=alerts,
        metrics={
            "my_courses": len(my_courses),
            "total_enrolled_students": total_enrolled,
            "draft_courses": draft_count,
            "student_progress": student_progress,
        },
    )


async def _student_dashboard(user: User) -> DashboardResponse:
    uid = str(user.id)
    enrollments = await Enrollment.find(
        Enrollment.student_id == uid,
        Enrollment.status == EnrollmentStatusEnum.ACTIVE
    ).to_list()

    # Batch-load all enrolled courses and their teachers in two queries instead of N+M
    from beanie import PydanticObjectId
    enr_course_ids = [e.course_id for e in enrollments]
    course_objects = []
    teacher_ids: set = set()
    if enr_course_ids:
        valid_oids = []
        for cid in enr_course_ids:
            try:
                valid_oids.append(PydanticObjectId(cid))
            except Exception:
                pass
        if valid_oids:
            courses_batch = await Course.find(
                {"_id": {"$in": valid_oids}, "deleted_at": None}
            ).to_list()
            for c in courses_batch:
                course_objects.append(c)
                if c.teacher_id:
                    teacher_ids.add(c.teacher_id)

    # Batch-fetch teacher names in one query
    teacher_map: dict = {}
    if teacher_ids:
        t_oids = []
        for tid in teacher_ids:
            try:
                t_oids.append(PydanticObjectId(tid))
            except Exception:
                pass
        if t_oids:
            teachers_batch = await User.find({"_id": {"$in": t_oids}}).to_list()
            teacher_map = {str(t.id): t.full_name() for t in teachers_batch}

    courses = [_course_dto(c, teacher_name=teacher_map.get(c.teacher_id)) for c in course_objects]

    insights = await LearningInsight.find(
        LearningInsight.student_id == uid
    ).sort(-LearningInsight.created_at).limit(5).to_list()

    alerts = []
    for ins in insights:
        alerts.append(DashboardAlert(
            type="warning" if ins.change_percentage < 0 else "success",
            message=ins.summary,
        ))

    return DashboardResponse(
        role="student",
        allowed_actions=["view_my_courses", "view_progress", "view_reports", "view_insights"],
        courses=courses,
        alerts=alerts,
        metrics={
            "enrolled_courses": len(courses),
            "recent_insights": len(insights),
        },
    )


async def _parent_dashboard(user: User) -> DashboardResponse:
    linked_ids = user.linked_student_ids or []
    raw_courses: list = []          # Active-enrollment course objects, deduplicated
    pending_raw_courses: list = []  # Pending-enrollment course objects, deduplicated
    alerts = []
    children_info = []
    seen_course_ids: set = set()
    seen_pending_ids: set = set()

    for student_id in linked_ids:
        try:
            student = await User.get(student_id)
        except Exception:
            continue
        if not student:
            continue

        enrollments = await Enrollment.find(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatusEnum.ACTIVE
        ).to_list()

        pending_enrollments = await Enrollment.find(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatusEnum.PENDING
        ).to_list()

        for enr in enrollments:
            if enr.course_id in seen_course_ids:
                continue
            try:
                c = await Course.get(enr.course_id)
                if c and c.deleted_at is None:
                    raw_courses.append(c)
                    seen_course_ids.add(enr.course_id)
            except Exception:
                pass

        pending_course_ids_for_child = [enr.course_id for enr in pending_enrollments]
        for enr in pending_enrollments:
            if enr.course_id in seen_pending_ids or enr.course_id in seen_course_ids:
                continue
            try:
                c = await Course.get(enr.course_id)
                if c and c.deleted_at is None:
                    pending_raw_courses.append(c)
                    seen_pending_ids.add(enr.course_id)
            except Exception:
                pass

        insights = await LearningInsight.find(
            LearningInsight.student_id == student_id
        ).sort(-LearningInsight.created_at).limit(3).to_list()

        for ins in insights:
            if abs(ins.change_percentage) >= 15:
                alerts.append(DashboardAlert(
                    type="warning" if ins.change_percentage < 0 else "success",
                    message=f"{student.full_name()}: {ins.summary}",
                ))

        # Batch-load all performance scores for this child at once
        from app.models import PerformanceScore, Feedback
        child_scores = []
        if enrollments:
            enr_cids = [e.course_id for e in enrollments]
            ps_batch = await PerformanceScore.find(
                {"student_id": student_id, "course_id": {"$in": enr_cids}}
            ).to_list()
            ps_map = {ps.course_id: ps for ps in ps_batch}
            for enr in enrollments:
                ps = ps_map.get(enr.course_id)
                if ps:
                    child_scores.append({
                        "course_id": enr.course_id,
                        "score": ps.score,
                        "classification": ps.classification.value if hasattr(ps.classification, "value") else ps.classification,
                    })

        # Latest published feedback visible to this parent
        latest_feedback = None
        recent_fbs = await Feedback.find(
            Feedback.student_id == student_id
        ).sort(-Feedback.submitted_at).limit(10).to_list()
        for fb in recent_fbs:
            vis = fb.visibility.value if hasattr(fb.visibility, "value") else getattr(fb, "visibility", "private")
            if vis == "published":
                latest_feedback = {
                    "content": fb.content,
                    "sentiment": fb.sentiment.value if hasattr(fb.sentiment, "value") else fb.sentiment,
                    "submitted_at": fb.submitted_at.isoformat() if fb.submitted_at else None,
                }
                break

        children_info.append({
            "id": student_id,
            "name": student.full_name(),
            "enrolled_count": len(enrollments),
            "performance_scores": child_scores,
            "course_ids": [enr.course_id for enr in enrollments],
            "pending_course_ids": pending_course_ids_for_child,
            "latest_feedback": latest_feedback,
        })

    # Batch-fetch teacher names for all parent-visible courses (active + pending)
    from beanie import PydanticObjectId
    all_raw = raw_courses + pending_raw_courses
    teacher_ids = list({c.teacher_id for c in all_raw if c.teacher_id})
    teacher_name_map: dict = {}
    if teacher_ids:
        valid_oids = []
        for tid in teacher_ids:
            try:
                valid_oids.append(PydanticObjectId(tid))
            except Exception:
                pass
        if valid_oids:
            teachers_batch = await User.find({"_id": {"$in": valid_oids}}).to_list()
            teacher_name_map = {str(t.id): t.full_name() for t in teachers_batch}

    all_courses: List[DashboardCourse] = [
        _course_dto(c, teacher_name=teacher_name_map.get(c.teacher_id))
        for c in raw_courses
    ]

    # Pending courses — lightweight dict (not DashboardCourse, so schedule stays clean)
    pending_courses_data = [
        {
            "id": str(c.id),
            "code": c.code,
            "name": c.name,
            "teacher_name": teacher_name_map.get(c.teacher_id),
            "schedule": c.schedule,
        }
        for c in pending_raw_courses
    ]

    return DashboardResponse(
        role="parent",
        allowed_actions=["view_child_courses", "view_child_progress", "view_child_reports"],
        courses=all_courses,
        alerts=alerts,
        metrics={
            "linked_children": len(linked_ids),
            "children": children_info,
            "pending_courses": pending_courses_data,
        },
    )


@router.get("/updates")
async def get_dashboard_updates(current_user: User = Depends(get_current_user)):
    """Return role-filtered recent activity for the dashboard Updates tab."""
    from app.models import LessonRecord, AIAlert
    from app.repositories import UserRepository
    from datetime import datetime as dt

    role = current_user.role
    uid  = str(current_user.id)
    items: list = []

    async def _cname(cid: str) -> str:
        try:
            c = await Course.get(cid)
            return c.name if c else cid
        except Exception:
            return cid

    async def _sname(sid: str) -> str:
        try:
            u = await UserRepository.get_by_id(sid)
            return u.full_name() if u else sid[-8:]
        except Exception:
            return sid[-8:]

    if role == RoleEnum.ADMIN:
        enrs = await Enrollment.find().sort(-Enrollment.created_at).limit(15).to_list()
        for e in enrs:
            e_status = e.status.value if hasattr(e.status, "value") else e.status
            items.append({"timestamp": e.created_at, "type": "enrollment",
                          "description": f"Student enrolled ({e_status})",
                          "course_name": await _cname(e.course_id),
                          "student_name": await _sname(e.student_id)})
        als = await AIAlert.find().sort(-AIAlert.created_at).limit(15).to_list()
        for a in als:
            items.append({"timestamp": a.created_at, "type": "ai_alert",
                          "description": a.message,
                          "course_name": await _cname(a.course_id),
                          "student_name": await _sname(a.student_id)})
        recs = await LessonRecord.find().sort(-LessonRecord.created_at).limit(10).to_list()
        for r in recs:
            att_val = r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
            parts = ([f"grade {r.grade_value:.0f}%"] if r.grade_value is not None else []) + [f"att: {att_val}"]
            items.append({"timestamp": r.created_at, "type": "lesson_record",
                          "description": ", ".join(parts),
                          "course_name": await _cname(r.course_id),
                          "student_name": await _sname(r.student_id)})

    elif role == RoleEnum.TEACHER:
        my_courses = await Course.find(Course.teacher_id == uid, Course.deleted_at == None).to_list()
        cmap = {str(c.id): c.name for c in my_courses}
        recs = await LessonRecord.find(
            LessonRecord.created_by_teacher_id == uid
        ).sort(-LessonRecord.created_at).limit(20).to_list()
        for r in recs:
            att_val = r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
            parts = ([f"grade {r.grade_value:.0f}%"] if r.grade_value is not None else []) + \
                    [f"att: {att_val}"] + \
                    (["feedback added"] if r.teacher_feedback else [])
            items.append({"timestamp": r.created_at, "type": "lesson_record",
                          "description": ", ".join(parts),
                          "course_name": cmap.get(r.course_id, r.course_id),
                          "student_name": await _sname(r.student_id)})
        if cmap:
            enrs = await Enrollment.find(
                {"course_id": {"$in": list(cmap.keys())}}
            ).sort(-Enrollment.created_at).limit(15).to_list()
            for e in enrs:
                e_status = e.status.value if hasattr(e.status, "value") else e.status
                items.append({"timestamp": e.created_at, "type": "enrollment",
                              "description": f"New enrollment ({e_status})",
                              "course_name": cmap.get(e.course_id, e.course_id),
                              "student_name": await _sname(e.student_id)})

    elif role == RoleEnum.STUDENT:
        recs = await LessonRecord.find(
            LessonRecord.student_id == uid
        ).sort(-LessonRecord.created_at).limit(20).to_list()
        for r in recs:
            att_val = r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
            parts = ([f"grade {r.grade_value:.0f}%"] if r.grade_value is not None else []) + \
                    [f"att: {att_val}"] + \
                    (["feedback received"] if r.teacher_feedback else [])
            items.append({"timestamp": r.created_at, "type": "lesson_record",
                          "description": ", ".join(parts),
                          "course_name": await _cname(r.course_id), "student_name": None})
        als = await AIAlert.find(
            AIAlert.student_id == uid
        ).sort(-AIAlert.created_at).limit(10).to_list()
        for a in als:
            items.append({"timestamp": a.created_at, "type": "ai_alert",
                          "description": a.message,
                          "course_name": await _cname(a.course_id), "student_name": None})

    else:  # PARENT
        linked_ids = current_user.linked_student_ids or []
        for student_id in linked_ids:
            sname = await _sname(student_id)
            recs = await LessonRecord.find(
                LessonRecord.student_id == student_id
            ).sort(-LessonRecord.created_at).limit(10).to_list()
            for r in recs:
                att_val = r.attendance_status.value if hasattr(r.attendance_status, "value") else r.attendance_status
                parts = ([f"grade {r.grade_value:.0f}%"] if r.grade_value is not None else []) + \
                        [f"att: {att_val}"] + \
                        (["feedback received"] if r.teacher_feedback else [])
                items.append({"timestamp": r.created_at, "type": "lesson_record",
                              "description": ", ".join(parts),
                              "course_name": await _cname(r.course_id), "student_name": sname})
            als = await AIAlert.find(
                AIAlert.student_id == student_id
            ).sort(-AIAlert.created_at).limit(5).to_list()
            for a in als:
                items.append({"timestamp": a.created_at, "type": "ai_alert",
                              "description": a.message,
                              "course_name": await _cname(a.course_id), "student_name": sname})

    items.sort(key=lambda x: x["timestamp"] or dt.min, reverse=True)
    for item in items:
        if item["timestamp"]:
            item["timestamp"] = item["timestamp"].isoformat()
    return {"updates": items[:25]}
