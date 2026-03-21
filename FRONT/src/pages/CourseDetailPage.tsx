import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { ProgressBar } from '../components/widgets/ProgressBar';
import { EmptyState } from '../components/widgets/EmptyState';
import { ErrorState } from '../components/widgets/ErrorState';
import { QuickFeedbackModal } from '../components/QuickFeedbackModal';
import { QuickEmailModal } from '../components/QuickEmailModal';
import { FeedbackHistoryModal } from '../components/FeedbackHistoryModal';
import { StudentProgressModal } from '../components/StudentProgressModal';
import { GroupEmailModal } from '../components/GroupEmailModal';
import { QuickAttendanceModal } from '../components/QuickAttendanceModal';
import { SendMessageModal } from '../components/SendMessageModal';
import { apiService } from '../services/apiService';
import { RiskBadge } from '../components/RiskBadge';
import { UserAvatar } from '../components/UserAvatar';

const SCORE_BADGE: Record<string, string> = {
  excellent:       'bg-green-100 text-green-700',
  good:            'bg-blue-100 text-blue-700',
  average:         'bg-yellow-100 text-yellow-700',
  needs_attention: 'bg-red-100 text-red-700',
};

const SENTIMENT_BADGE: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral:  'bg-gray-100 text-gray-600',
  negative: 'bg-red-100 text-red-700',
};

const COURSE_COLORS = ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'];

export const CourseDetailPage: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const { user } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();

  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState('overview');

  // ── Quick action modal state ────────────────────────────────────────────
  const [feedbackTarget, setFeedbackTarget]     = useState<{ studentId: string; studentName: string } | null>(null);
  const [emailTarget, setEmailTarget]           = useState<{ recipientId: string; recipientName: string; recipientType: 'student' | 'parent' } | null>(null);
  const [historyTarget, setHistoryTarget]       = useState<{ studentId: string; studentName: string } | null>(null);
  const [attendanceTarget, setAttendanceTarget] = useState<{ studentId: string; studentName: string } | null>(null);
  const [messageTarget, setMessageTarget]       = useState<{ studentId: string; studentName: string } | null>(null);
  const [progressTarget, setProgressTarget]     = useState<{ studentId: string; studentName: string; score?: number; classification?: string } | null>(null);
  const [showGroupEmail, setShowGroupEmail]     = useState(false);
  const [gradeTarget, setGradeTarget]           = useState<{ studentId: string; studentName: string } | null>(null);
  const [gradeValue, setGradeValue]             = useState('');
  const [gradeSubject, setGradeSubject]         = useState('');
  const [gradeSaving, setGradeSaving]           = useState(false);
  const [gradeMsg, setGradeMsg]                 = useState<{ ok: boolean; text: string } | null>(null);

  // ── Roster search/filter ────────────────────────────────────────────────
  const [rosterSearch, setRosterSearch] = useState('');
  const [rosterFilter, setRosterFilter] = useState('all');

  // ── Material inline add ─────────────────────────────────────────────────
  const [matTitle, setMatTitle]       = useState('');
  const [matLink, setMatLink]         = useState('');
  const [matFile, setMatFile]         = useState<File | null>(null);
  const [matUploading, setMatUploading] = useState(false);
  const [matMsg, setMatMsg]           = useState<{ ok: boolean; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Announce tab ────────────────────────────────────────────────────────
  const [announceForm, setAnnounceForm] = useState({ subject: '', content: '', include_parents: false });
  const [announcing, setAnnouncing]     = useState(false);
  const [announceResult, setAnnounceResult] = useState<string | null>(null);
  const [announceError, setAnnounceError]   = useState<string | null>(null);

  // ── Archive course (admin only) ──────────────────────────────────────────
  const [archiving, setArchiving] = useState(false);
  const handleArchive = async () => {
    if (!courseId || !window.confirm('Archive this course? Teachers will no longer be able to edit it.')) return;
    setArchiving(true);
    try {
      await apiService.archiveCourse(courseId);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to archive course.');
    } finally {
      setArchiving(false);
    }
  };

  // ── Restore archived course (owner-teacher or admin) ─────────────────────
  const [restoring, setRestoring] = useState(false);
  const handleRestore = async () => {
    if (!courseId || !window.confirm('Restore this course to published? You will be able to edit it again.')) return;
    setRestoring(true);
    try {
      await apiService.restoreCourse(courseId);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to restore course.');
    } finally {
      setRestoring(false);
    }
  };

  // ── Change Teacher (admin only) ──────────────────────────────────────────
  const [showChangeTeacher, setShowChangeTeacher] = useState(false);
  const [teacherSearchQ, setTeacherSearchQ]       = useState('');
  const [teacherResults, setTeacherResults]       = useState<any[]>([]);
  const [searchingTeachers, setSearchingTeachers] = useState(false);
  const [changingTeacherId, setChangingTeacherId] = useState<string | null>(null);
  const [teacherMsg, setTeacherMsg]               = useState<{ ok: boolean; text: string } | null>(null);

  // ── AI Intelligence Layer ───────────────────────────────────────────────────
  const [courseRiskMap, setCourseRiskMap]         = useState<Record<string, any>>({});
  const [riskLoading, setRiskLoading]             = useState(false);
  const [aiAssistant, setAiAssistant]             = useState<any>(null);
  const [aiAssistantLoading, setAiAssistantLoading] = useState(false);
  const [showAiAssistant, setShowAiAssistant]     = useState(false);
  const [feedbackTrend, setFeedbackTrend]         = useState<any>(null);
  const [feedbackTrendLoading, setFeedbackTrendLoading] = useState(false);

  // ── Grade Suggestions ───────────────────────────────────────────────────────
  const [gradeSuggestions, setGradeSuggestions]     = useState<any[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionMsg, setSuggestionMsg]           = useState<{ ok: boolean; text: string } | null>(null);

  // ── Add Student panel ───────────────────────────────────────────────────────
  const [showAddStudent, setShowAddStudent]       = useState(false);
  const [studentSearch, setStudentSearch]         = useState('');
  const [studentResults, setStudentResults]       = useState<any[]>([]);
  const [searchingStudents, setSearchingStudents] = useState(false);
  const [enrollingId, setEnrollingId]             = useState<string | null>(null);
  const [rosterMsg, setRosterMsg]                 = useState<{ ok: boolean; text: string } | null>(null);
  const [requestingEnrollment, setRequestingEnrollment] = useState(false);
  const [enrollRequestMsg, setEnrollRequestMsg]   = useState<string | null>(null);
  const [approvingId, setApprovingId]             = useState<string | null>(null);

  // ── Parent: request enrollment for child ────────────────────────────────────
  const [parentEnrollingId, setParentEnrollingId] = useState<string | null>(null);
  const [parentEnrollMsg, setParentEnrollMsg]     = useState<{ studentId: string; ok: boolean; text: string } | null>(null);

  const role = user?.role || 'student';
  const isTeacherOrAdmin = role === 'teacher' || role === 'admin';
  const isOwner = isTeacherOrAdmin && (role === 'admin' || detail?.course?.teacher_id === user?.id);

  const load = () => {
    if (!courseId) return;
    setLoading(true);
    setError(null);
    apiService.getCourseDetail(courseId)
      .then(r => setDetail(r.data))
      .catch(() => setError('Failed to load course details.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [courseId]);

  // Load AI risk summary for the roster (lazy — called when entering roster tab)
  const loadCourseRisk = () => {
    if (!courseId || riskLoading || Object.keys(courseRiskMap).length > 0) return;
    setRiskLoading(true);
    apiService.getCourseRiskSummary(courseId)
      .then(r => {
        const map: Record<string, any> = {};
        (r.data?.students ?? []).forEach((s: any) => { map[s.student_id] = s; });
        setCourseRiskMap(map);
      })
      .catch(() => {})
      .finally(() => setRiskLoading(false));
  };

  // Load Teacher AI Assistant (on-demand)
  const loadAiAssistant = (force = false) => {
    if (!courseId || aiAssistantLoading) return;
    setAiAssistantLoading(true);
    apiService.getTeacherAssistant(courseId)
      .then(r => setAiAssistant(r.data))
      .catch(() => {})
      .finally(() => setAiAssistantLoading(false));
    // Also load feedback trend
    if (force || (!feedbackTrend && !feedbackTrendLoading)) {
      setFeedbackTrendLoading(true);
      apiService.getFeedbackTrend(courseId)
        .then(r => setFeedbackTrend(r.data))
        .catch(() => {})
        .finally(() => setFeedbackTrendLoading(false));
    }
  };

  const loadGradeSuggestions = () => {
    if (!courseId || !isTeacherOrAdmin) return;
    setSuggestionsLoading(true);
    apiService.getGradeSuggestions(courseId)
      .then(r => setGradeSuggestions(r.data ?? []))
      .catch(() => {})
      .finally(() => setSuggestionsLoading(false));
  };

  const handleApproveSuggestion = async (id: string) => {
    try {
      await apiService.approveGradeSuggestion(id);
      setSuggestionMsg({ ok: true, text: 'Grade suggestion approved and grade recorded.' });
      setGradeSuggestions(prev => prev.filter(s => s.id !== id));
      setTimeout(() => setSuggestionMsg(null), 3000);
    } catch (err: any) {
      setSuggestionMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to approve.' });
    }
  };

  const handleRejectSuggestion = async (id: string) => {
    try {
      await apiService.rejectGradeSuggestion(id);
      setGradeSuggestions(prev => prev.filter(s => s.id !== id));
    } catch (err: any) {
      setSuggestionMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to reject.' });
    }
  };

  const course = detail?.course;
  const courseList = course ? [{ id: course.id, name: course.name }] : [];

  // student_id → student_name map built from roster
  const rosterNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    (detail?.roster ?? []).forEach((s: any) => { if (s.student_id) map[s.student_id] = s.student_name ?? s.student_email ?? s.student_id; });
    return map;
  }, [detail?.roster]);

  // Quick stats derived from roster — memoized to avoid recalculating on every render
  const quickStats = useMemo(() => {
    if (!isTeacherOrAdmin || !detail?.roster?.length) return null;
    const roster = detail.roster as any[];
    const scored = roster.filter(s => s.score != null);
    const avg = scored.length > 0
      ? scored.reduce((sum: number, s: any) => sum + s.score, 0) / scored.length
      : null;
    return {
      avg,
      needsAttn: roster.filter(s => s.classification === 'needs_attention').length,
      excellent:  roster.filter(s => s.classification === 'excellent').length,
    };
  }, [detail?.roster, isTeacherOrAdmin]);

  // Filtered roster — memoized so filter only reruns when roster/search/filter actually change
  const filteredRoster = useMemo(() => {
    const roster: any[] = detail?.roster ?? [];
    const q = rosterSearch.toLowerCase();
    return roster.filter(s => {
      const matchSearch = !q ||
        s.student_name?.toLowerCase().includes(q) ||
        s.student_email?.toLowerCase().includes(q);
      const matchFilter = rosterFilter === 'all' || s.classification === rosterFilter;
      return matchSearch && matchFilter;
    });
  }, [detail?.roster, rosterSearch, rosterFilter]);

  // Material add handler
  const submitMaterial = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!matTitle.trim()) return;
    if (!matLink && !matFile) { setMatMsg({ ok: false, text: t('courseDetail.matRequired') }); return; }
    setMatUploading(true);
    setMatMsg(null);
    try {
      const fd = new FormData();
      fd.append('title', matTitle.trim());
      if (matLink) fd.append('link_url', matLink.trim());
      if (matFile) fd.append('file', matFile);
      await apiService.addMaterial(courseId!, fd);
      setMatTitle('');
      setMatLink('');
      setMatFile(null);
      if (fileRef.current) fileRef.current.value = '';
      setMatMsg({ ok: true, text: 'Material added!' });
      load();
    } catch (err: any) {
      setMatMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to add material.' });
    } finally {
      setMatUploading(false);
    }
  };

  // Announce handler
  const submitAnnounce = async (e: React.FormEvent) => {
    e.preventDefault();
    setAnnouncing(true);
    setAnnounceError(null);
    setAnnounceResult(null);
    try {
      const r = await apiService.announceCourse(courseId!, announceForm);
      setAnnounceResult(`Sent to ${r.data.sent_count} recipient(s).`);
      setAnnounceForm({ subject: '', content: '', include_parents: false });
    } catch (err: any) {
      setAnnounceError(err?.response?.data?.detail || 'Failed to send announcement.');
    } finally {
      setAnnouncing(false);
    }
  };

  // ── Add-student helpers ──────────────────────────────────────────────────
  const studentSearchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchStudents = useCallback((q: string) => {
    setStudentSearch(q);
    if (studentSearchTimerRef.current) clearTimeout(studentSearchTimerRef.current);
    if (q.trim().length < 2) { setStudentResults([]); return; }
    studentSearchTimerRef.current = setTimeout(async () => {
      setSearchingStudents(true);
      try {
        const r = await apiService.search(q, 'students');
        const enrolledIds = new Set((detail?.roster ?? []).map((s: any) => s.student_id));
        setStudentResults((r.data.results ?? []).filter((u: any) => !enrolledIds.has(u.id)));
      } catch { setStudentResults([]); }
      finally { setSearchingStudents(false); }
    }, 350);
  }, [detail?.roster]);

  const addStudentToCourse = async (studentId: string, studentName: string) => {
    setEnrollingId(studentId);
    setRosterMsg(null);
    try {
      await apiService.enrollCourse({ student_id: studentId, course_id: courseId });
      setRosterMsg({ ok: true, text: `${studentName} enrolled successfully.` });
      setStudentSearch('');
      setStudentResults([]);
      setShowAddStudent(false);
      load();
    } catch (err: any) {
      setRosterMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to enroll student.' });
    } finally {
      setEnrollingId(null);
    }
  };

  const removeStudentFromCourse = async (enrollmentId: string, studentName: string) => {
    if (!window.confirm(`Remove ${studentName} from this course?\n\nGrades and feedback will be preserved.`)) return;
    setRosterMsg(null);
    try {
      await apiService.withdrawCourse(enrollmentId);
      setRosterMsg({ ok: true, text: `${studentName} removed from course.` });
      load();
    } catch (err: any) {
      setRosterMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to remove student.' });
    }
  };

  // Format a schedule-conflict detail (structured dict from backend) into a readable message
  const fmtConflict = (detail: any): string => {
    if (detail?.code !== 'schedule_conflict') return typeof detail === 'string' ? detail : 'Request failed';
    return t('enrollment.scheduleConflict')
      .replace('{course}', detail.course_name || '')
      .replace('{day}',    detail.day         || '')
      .replace('{start}',  detail.start_time  || '')
      .replace('{end}',    detail.end_time    || '');
  };

  // ── Enrollment request (student) ─────────────────────────────────────────
  const handleRequestEnrollment = async () => {
    if (!courseId) return;
    setRequestingEnrollment(true);
    setEnrollRequestMsg(null);
    try {
      await apiService.requestEnrollment(courseId);
      setDetail((prev: any) => ({ ...prev, my_enrollment_status: 'pending' }));
    } catch (err: any) {
      setEnrollRequestMsg(fmtConflict(err?.response?.data?.detail));
    } finally {
      setRequestingEnrollment(false);
    }
  };

  // ── Approve / reject pending requests (teacher/admin) ────────────────────
  const handleApproveRequest = async (enrollmentId: string) => {
    setApprovingId(enrollmentId);
    try {
      await apiService.approveEnrollment(enrollmentId);
      setDetail((prev: any) => {
        const req = (prev.pending_requests ?? []).find((r: any) => r.enrollment_id === enrollmentId);
        const newPending = (prev.pending_requests ?? []).filter((r: any) => r.enrollment_id !== enrollmentId);
        const newRoster = req
          ? [...(prev.roster ?? []), { ...req, enrollment_status: 'active' }]
          : (prev.roster ?? []);
        return {
          ...prev,
          pending_requests: newPending,
          roster: newRoster,
          course: { ...prev.course, enrolled_count: prev.course.enrolled_count + 1 },
        };
      });
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to approve request.');
    } finally {
      setApprovingId(null);
    }
  };

  const handleRejectRequest = async (enrollmentId: string) => {
    setApprovingId(enrollmentId);
    try {
      await apiService.rejectEnrollment(enrollmentId);
      setDetail((prev: any) => ({
        ...prev,
        pending_requests: (prev.pending_requests ?? []).filter((r: any) => r.enrollment_id !== enrollmentId),
      }));
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Failed to reject request.');
    } finally {
      setApprovingId(null);
    }
  };

  // ── Change Teacher helpers (admin only) ──────────────────────────────────
  const teacherSearchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchTeachers = useCallback((q: string) => {
    setTeacherSearchQ(q);
    if (teacherSearchTimerRef.current) clearTimeout(teacherSearchTimerRef.current);
    if (q.trim().length < 2) { setTeacherResults([]); return; }
    teacherSearchTimerRef.current = setTimeout(async () => {
      setSearchingTeachers(true);
      try {
        const r = await apiService.search(q, 'teachers');
        setTeacherResults(r.data.results ?? []);
      } catch { setTeacherResults([]); }
      finally { setSearchingTeachers(false); }
    }, 350);
  }, []);

  const changeTeacher = async (newTeacherId: string, newTeacherName: string) => {
    if (!window.confirm(`Reassign this course to ${newTeacherName}?`)) return;
    setChangingTeacherId(newTeacherId);
    setTeacherMsg(null);
    try {
      await apiService.changeCourseTeacher(courseId!, newTeacherId);
      setTeacherMsg({ ok: true, text: `Course reassigned to ${newTeacherName}.` });
      setShowChangeTeacher(false);
      setTeacherSearchQ('');
      setTeacherResults([]);
      load();
    } catch (err: any) {
      setTeacherMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to change teacher.' });
    } finally {
      setChangingTeacherId(null);
    }
  };

  const tabs = !detail ? [] : [
    { key: 'overview',  label: t('courseDetail.tabOverview')  },
    ...(detail.syllabus ? [{ key: 'syllabus',  label: t('courseDetail.tabSyllabus')  }] : []),
    { key: 'materials', label: t('courseDetail.tabMaterials') },
    ...(isTeacherOrAdmin ? [{ key: 'roster',   label: t('courseDetail.tabRoster')    }] : []),
    ...(detail.feedback?.length > 0 || isTeacherOrAdmin
      ? [{ key: 'feedback', label: t('courseDetail.tabFeedback') }] : []),
    ...(isTeacherOrAdmin ? [{ key: 'announce', label: t('courseDetail.tabAnnounce')  }] : []),
  ];

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : !detail ? null : (
          <>
            {/* ── Course header ─────────────────────────────────────────────── */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white font-black text-lg flex-shrink-0 ${
                    COURSE_COLORS[course.code.charCodeAt(0) % COURSE_COLORS.length]
                  }`}>
                    {course.code.slice(0, 3)}
                  </div>
                  <div className="min-w-0">
                    <h1 className="text-lg font-black text-gray-900 truncate">{course.name}</h1>
                    <p className="text-xs text-gray-400 font-mono mt-0.5">{course.code}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        course.status === 'published' ? 'bg-green-100 text-green-700' :
                        course.status === 'draft'     ? 'bg-yellow-100 text-yellow-700' :
                                                        'bg-gray-100 text-gray-500'
                      }`}>{t(`status.${course.status}`) || course.status}</span>
                      <span className="text-xs text-gray-500">{t('courseDetail.teacher')}: <strong>{course.teacher_name}</strong></span>
                      {role === 'admin' && (
                        <button
                          onClick={() => { setShowChangeTeacher(s => !s); setTeacherSearchQ(''); setTeacherResults([]); setTeacherMsg(null); }}
                          className="text-[10px] text-blue-600 hover:underline"
                        >
                          {t('courseDetail.change')}
                        </button>
                      )}
                      <span className="text-xs text-gray-400">{course.enrolled_count} / {course.capacity} {t('courseDetail.studentsCount')}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => navigate(-1)}
                    className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 transition"
                  >
                    {t('courseDetail.back')}
                  </button>
                  {role === 'student' && (() => {
                    const st = detail.my_enrollment_status;
                    if (st === 'active' || st === 'completed') return null;
                    if (st === 'pending') return (
                      <span className="text-xs bg-yellow-50 text-yellow-700 border border-yellow-200 rounded-lg px-3 py-1.5 font-medium">
                        {t('courseDetail.pendingApproval')}
                      </span>
                    );
                    if (st === 'rejected') return (
                      <span className="text-xs bg-red-50 text-red-600 border border-red-200 rounded-lg px-3 py-1.5 font-medium">
                        {t('courseDetail.requestRejected')}
                      </span>
                    );
                    return (
                      <div className="flex flex-col items-end gap-1">
                        <button
                          onClick={handleRequestEnrollment}
                          disabled={requestingEnrollment}
                          className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 transition disabled:opacity-50"
                        >
                          {requestingEnrollment ? t('courseDetail.sending') : t('courseDetail.requestEnrollment')}
                        </button>
                        {enrollRequestMsg && (
                          <span className="text-[10px] text-red-600">{enrollRequestMsg}</span>
                        )}
                      </div>
                    );
                  })()}
                  {(isTeacherOrAdmin || role === 'student') && (
                    <button
                      onClick={() => navigate(`/chat?course_id=${courseId}`)}
                      className="text-xs bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-1.5 hover:bg-green-100 transition"
                    >
                      {t('courseDetail.courseChat')}
                    </button>
                  )}
                  {isOwner && course.status !== 'archived' && (
                    <Link
                      to={`/courses/${course.id}/edit`}
                      className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 transition"
                    >
                      {t('courseDetail.editCourse')}
                    </Link>
                  )}
                  {isOwner && course.status === 'archived' && (
                    <button
                      disabled={restoring}
                      onClick={handleRestore}
                      className="text-xs bg-amber-500 text-white rounded-lg px-3 py-1.5 hover:bg-amber-600 transition disabled:opacity-50"
                    >
                      {restoring ? t('courseDetail.restoring') : t('courses.restore')}
                    </button>
                  )}
                  {role === 'admin' && course.status !== 'archived' && (
                    <button
                      disabled={archiving}
                      onClick={handleArchive}
                      className="text-xs bg-gray-100 text-gray-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-200 transition disabled:opacity-50"
                    >
                      {archiving ? t('courseDetail.archiving') : t('courses.archive')}
                    </button>
                  )}
                </div>
              </div>

              {course.description && (
                <p className="text-sm text-gray-600 mt-4 leading-relaxed">{course.description}</p>
              )}

              {course.schedule && (course.schedule.days?.length > 0 || course.schedule.start_time) && (
                <div className="mt-3 flex flex-wrap gap-2 items-center">
                  {(course.schedule.days ?? []).map((day: string) => (
                    <span key={day} className="text-xs bg-indigo-50 text-indigo-700 font-semibold px-2.5 py-0.5 rounded-full">
                      {t(`courseForm.day.${day.toLowerCase()}`) || day}
                    </span>
                  ))}
                  {course.schedule.start_time && course.schedule.end_time && (
                    <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-0.5 rounded-full">
                      {course.schedule.start_time} – {course.schedule.end_time}
                    </span>
                  )}
                </div>
              )}

              {/* ── Change Teacher panel (admin only) ── */}
              {role === 'admin' && showChangeTeacher && (
                <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                  <p className="text-xs font-semibold text-gray-600 mb-2">{t('courseDetail.searchTeachersHint')}</p>
                  <div className="relative">
                    <input
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      placeholder={t('courseDetail.searchNameEmail')}
                      value={teacherSearchQ}
                      onChange={e => searchTeachers(e.target.value)}
                      autoFocus
                    />
                    {searchingTeachers && (
                      <span className="absolute right-3 top-2 text-gray-400 text-xs">{t('courseDetail.searching')}</span>
                    )}
                  </div>
                  {teacherResults.length > 0 && (
                    <div className="mt-2 border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                      {teacherResults.map((t: any) => (
                        <div key={t.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                          <div>
                            <p className="text-xs font-semibold text-gray-700">{t.title || t.display_name}</p>
                            <p className="text-[10px] text-gray-400">{t.subtitle || t.email}</p>
                          </div>
                          <button
                            onClick={() => changeTeacher(t.id, t.title || t.display_name)}
                            disabled={changingTeacherId === t.id}
                            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-[10px] font-semibold px-2.5 py-1 rounded-lg transition"
                          >
                            {changingTeacherId === t.id ? t('courseDetail.assigning') : t('courseDetail.assign')}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {teacherSearchQ.length >= 2 && !searchingTeachers && teacherResults.length === 0 && (
                    <p className="text-xs text-gray-400 mt-2">{t('courseDetail.noTeachersFound')}</p>
                  )}
                  {teacherMsg && (
                    <div className={`mt-2 px-3 py-2 rounded-lg text-xs font-medium ${teacherMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                      {teacherMsg.ok ? '✅' : '❌'} {teacherMsg.text}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── Tabs ─────────────────────────────────────────────────────── */}
            <div className="flex gap-0.5 bg-gray-100 rounded-xl p-1 mb-5 overflow-x-auto w-fit max-w-full">
              {tabs.map(t => (
                <button
                  key={t.key}
                  onClick={() => { setTab(t.key); if (t.key === 'roster') loadCourseRisk(); if (t.key === 'feedback') loadGradeSuggestions(); }}
                  className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition whitespace-nowrap ${
                    tab === t.key ? 'bg-white text-blue-700 shadow' : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* ── Overview ─────────────────────────────────────────────────── */}
            {tab === 'overview' && (
              <div className="space-y-5">
                {/* Quick stats for teacher/admin */}
                {quickStats && (
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center">
                      <p className="text-2xl font-black text-gray-900">
                        {quickStats.avg != null ? quickStats.avg.toFixed(1) : '—'}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">{t('courseDetail.avgScore')}</p>
                    </div>
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center">
                      <p className="text-2xl font-black text-red-600">{quickStats.needsAttn}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{t('courseDetail.needsAttention')}</p>
                    </div>
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 text-center">
                      <p className="text-2xl font-black text-green-600">{quickStats.excellent}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{t('classification.excellent')}</p>
                    </div>
                  </div>
                )}

                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {[
                    { label: t('courseDetail.enrolledStudents'), value: course.enrolled_count,            icon: '👥' },
                    { label: t('courses.capacity'),              value: course.capacity,                 icon: '🏫' },
                    { label: t('tab.materials'),                 value: detail.materials.length,         icon: '📎' },
                    { label: t('courseDetail.syllabusTopics'),   value: detail.syllabus?.topics?.length ?? 0, icon: '📋' },
                    { label: t('courseDetail.statusLabel'),      value: t(`status.${course.status}`) || course.status, icon: '📌' },
                    { label: t('courseDetail.visibility'),       value: (course.visibility_scope || '').replace('_', ' '), icon: '🔒' },
                  ].map(s => (
                    <div key={s.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-3">
                      <span className="text-2xl">{s.icon}</span>
                      <div>
                        <p className="text-lg font-black text-gray-900">{s.value}</p>
                        <p className="text-xs text-gray-500">{s.label}</p>
                      </div>
                    </div>
                  ))}

                  {detail.my_progress && (
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                      <p className="text-xs text-gray-500 mb-1">{t('courseDetail.myPerformanceScore')}</p>
                      <p className="text-2xl font-black text-gray-900">
                        {detail.my_progress.score != null ? detail.my_progress.score.toFixed(1) : '—'}
                      </p>
                      {detail.my_progress.classification && (
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full mt-1 inline-block ${
                          SCORE_BADGE[detail.my_progress.classification] ?? 'bg-gray-100 text-gray-600'
                        }`}>
                          {t(`classification.${detail.my_progress.classification}`) || detail.my_progress.classification.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Parent's children — enrolled/completed */}
                {role === 'parent' && detail.roster?.length > 0 && (
                  <div>
                    <h3 className="font-bold text-gray-700 text-xs uppercase tracking-wide mb-3">{t('courseDetail.childrenEnrolled')}</h3>
                    <div className="space-y-3">
                      {detail.roster.map((r: any) => (
                        <div key={r.student_id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-4">
                          <UserAvatar name={r.student_name} url={r.avatar_url} size={40} />
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-gray-800 text-sm">{r.student_name}</p>
                            {r.score != null && (
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-xs text-gray-500">{t('courseDetail.score')}: <strong>{r.score.toFixed(1)}</strong></span>
                                {r.classification && (
                                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${SCORE_BADGE[r.classification] ?? ''}`}>
                                    {t(`classification.${r.classification}`) || r.classification.replace('_', ' ')}
                                  </span>
                                )}
                              </div>
                            )}
                            {r.score != null && (
                              <div className="mt-1 w-40">
                                <ProgressBar percent={Math.round(r.score)} showLabel={false} height={4} />
                              </div>
                            )}
                          </div>
                          <span className="flex-shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full bg-green-100 text-green-700">
                            {t('courseDetail.childEnrolled')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Parent: request enrollment for unenrolled children */}
                {role === 'parent' && detail.unenrolled_children?.length > 0 && (
                  <div>
                    <h3 className="font-bold text-gray-700 text-xs uppercase tracking-wide mb-3">{t('courseDetail.enrollAChild')}</h3>
                    <div className="space-y-2">
                      {detail.unenrolled_children.map((child: any) => {
                        const status: string | null = child.enrollment_status;
                        const isPending  = status === 'pending';
                        const isRejected = status === 'rejected';
                        const isRetry    = status === 'rejected' || status === 'withdrawn';
                        const msg = parentEnrollMsg?.studentId === child.student_id ? parentEnrollMsg : null;
                        return (
                          <div key={child.student_id} className="bg-orange-50 border border-orange-100 rounded-xl p-3 flex items-center gap-3">
                            <UserAvatar name={child.student_name} size={36} />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-semibold text-gray-800">{child.student_name}</p>
                              {isRejected && !msg && (
                                <p className="text-xs text-red-500 mt-0.5">{t('courseDetail.requestRejected')}</p>
                              )}
                              {msg && (
                                <p className={`text-xs mt-0.5 ${msg.ok ? 'text-green-600' : 'text-red-500'}`}>{msg.text}</p>
                              )}
                            </div>
                            {isPending ? (
                              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-yellow-100 text-yellow-700">
                                {t('courseDetail.pendingApproval')}
                              </span>
                            ) : (
                              <button
                                disabled={parentEnrollingId === child.student_id}
                                onClick={async () => {
                                  if (!courseId) return;
                                  setParentEnrollingId(child.student_id);
                                  setParentEnrollMsg(null);
                                  try {
                                    await apiService.requestEnrollment(courseId, child.student_id);
                                    setParentEnrollMsg({ studentId: child.student_id, ok: true, text: t('courseDetail.enrollRequestSent') });
                                    load();
                                  } catch (err: any) {
                                    const errMsg = fmtConflict(err?.response?.data?.detail);
                                    setParentEnrollMsg({ studentId: child.student_id, ok: false, text: errMsg });
                                  } finally {
                                    setParentEnrollingId(null);
                                  }
                                }}
                                className="flex-shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:opacity-60 text-white transition"
                              >
                                {parentEnrollingId === child.student_id
                                  ? t('courseDetail.sending')
                                  : isRetry
                                    ? t('courseDetail.requestAgain')
                                    : t('courseDetail.requestCourseForChild')}
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ── Syllabus ─────────────────────────────────────────────────── */}
            {tab === 'syllabus' && detail.syllabus && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">{t('courseDetail.courseSyllabus')}</h2>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">v{detail.syllabus.version}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                      detail.syllabus.status === 'published' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                    }`}>{t(`status.${detail.syllabus.status}`) || detail.syllabus.status}</span>
                  </div>
                </div>

                {detail.syllabus.topics.length === 0 ? (
                  <EmptyState icon="📋" title={t('courseDetail.noTopics')} />
                ) : (
                  <div className="space-y-3">
                    {detail.syllabus.topics.map((topic: any) => {
                      const isDone = detail.syllabus.completed_weeks.includes(topic.week_number);
                      return (
                        <div key={topic.week_number} className={`border rounded-xl p-4 ${
                          isDone ? 'border-green-200 bg-green-50/30' : 'border-gray-100'
                        }`}>
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="text-xs font-bold text-gray-400 uppercase tracking-wide">{t('courseDetail.week')} {topic.week_number}</span>
                            {isDone && (
                              <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-semibold">
                                {t('courseDetail.completed')}
                              </span>
                            )}
                          </div>
                          <h3 className="font-semibold text-gray-800 text-sm">{topic.title}</h3>
                          {topic.description && <p className="text-xs text-gray-500 mt-1">{topic.description}</p>}

                          {topic.objectives?.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-semibold text-gray-600 mb-1">{t('courseDetail.learningObjectives')}</p>
                              <ul className="list-disc list-inside space-y-0.5">
                                {topic.objectives.map((o: string, i: number) => (
                                  <li key={i} className="text-xs text-gray-500">{o}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {topic.assignments?.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-semibold text-gray-600 mb-1">{t('courseDetail.assignments')}</p>
                              <ul className="list-disc list-inside space-y-0.5">
                                {topic.assignments.map((a: string, i: number) => (
                                  <li key={i} className="text-xs text-gray-500">{a}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {topic.materials?.length > 0 && (
                            <div className="mt-2">
                              <p className="text-xs font-semibold text-gray-600 mb-1">{t('tab.materials')}</p>
                              <ul className="list-disc list-inside space-y-0.5">
                                {topic.materials.map((m: string, i: number) => (
                                  <li key={i} className="text-xs text-gray-500">{m}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {isTeacherOrAdmin && topic.teacher_notes && (
                            <div className="mt-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5">
                              <p className="text-xs font-semibold text-amber-700 mb-0.5">{t('courseDetail.privateTeacherNotes')}</p>
                              <p className="text-xs text-amber-800">{topic.teacher_notes}</p>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ── Materials ────────────────────────────────────────────────── */}
            {tab === 'materials' && (
              <div className="space-y-4">
                {/* Inline add form for teacher/owner */}
                {isOwner && (
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <h3 className="font-bold text-gray-800 text-sm mb-3">{t('courseDetail.addMaterial')}</h3>
                    <form onSubmit={submitMaterial} className="space-y-2">
                      <input
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder={t('courseDetail.titlePlaceholder')}
                        value={matTitle}
                        onChange={e => setMatTitle(e.target.value)}
                        required
                      />
                      <input
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder={t('courseDetail.linkPlaceholder')}
                        value={matLink}
                        onChange={e => setMatLink(e.target.value)}
                      />
                      <div className="flex items-center gap-2">
                        <input
                          ref={fileRef}
                          type="file"
                          className="text-xs text-gray-500 flex-1"
                          onChange={e => setMatFile(e.target.files?.[0] ?? null)}
                        />
                      </div>
                      {matMsg && (
                        <p className={`text-xs px-3 py-2 rounded-lg ${
                          matMsg.ok ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-500'
                        }`}>{matMsg.text}</p>
                      )}
                      <button
                        type="submit"
                        disabled={matUploading}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg transition"
                      >
                        {matUploading ? t('courseDetail.adding') : t('courseDetail.addMaterialBtn')}
                      </button>
                    </form>
                  </div>
                )}

                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">{t('courseDetail.courseMaterials')}</h2>
                  {detail.materials.length === 0 ? (
                    <EmptyState icon="📎" title={t('courseDetail.noMaterialsYet')} />
                  ) : (
                    <div className="space-y-2">
                      {detail.materials.map((m: any) => (
                        <div key={m.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:bg-gray-50 transition">
                          <span className="text-xl flex-shrink-0">{m.file_url ? '📄' : '🔗'}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-gray-700 truncate">{m.title}</p>
                            {m.created_at && (
                              <p className="text-xs text-gray-400">{new Date(m.created_at).toLocaleDateString()}</p>
                            )}
                          </div>
                          {(m.file_url || m.link_url) && (() => {
                            const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';
                            const raw = m.link_url ?? m.file_url;
                            const href = raw?.startsWith('/') ? `${API_URL}${raw}` : raw;
                            return (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-600 hover:underline flex-shrink-0"
                              >
                                {t('courseDetail.openLink')}
                              </a>
                            );
                          })()}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Roster (teacher / admin only) ────────────────────────────── */}
            {tab === 'roster' && isTeacherOrAdmin && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                {/* Header with search, filter, and actions */}
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">
                    {t('courseDetail.studentRoster')}
                    <span className="ml-2 text-xs font-normal text-gray-400">({filteredRoster.length} / {detail.roster.length})</span>
                  </h2>
                  <div className="flex items-center gap-2 ml-auto flex-wrap">
                    <input
                      className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 w-36"
                      placeholder={t('courseDetail.searchStudents')}
                      value={rosterSearch}
                      onChange={e => setRosterSearch(e.target.value)}
                    />
                    <select
                      className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      value={rosterFilter}
                      onChange={e => setRosterFilter(e.target.value)}
                    >
                      <option value="all">{t('courseDetail.allStatuses')}</option>
                      <option value="excellent">{t('classification.excellent')}</option>
                      <option value="good">{t('classification.good')}</option>
                      <option value="average">{t('classification.average')}</option>
                      <option value="needs_attention">{t('classification.needs_attention')}</option>
                    </select>
                    {detail.roster.length > 0 && (
                      <button
                        onClick={() => setShowGroupEmail(true)}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-semibold px-3 py-1.5 rounded-lg transition"
                      >
                        {t('courseDetail.groupEmail')}
                      </button>
                    )}
                    {isOwner && (
                      <button
                        onClick={() => { setShowAddStudent(s => !s); setStudentSearch(''); setStudentResults([]); setRosterMsg(null); }}
                        className="bg-green-600 hover:bg-green-700 text-white text-[10px] font-semibold px-3 py-1.5 rounded-lg transition"
                      >
                        {t('courseDetail.addStudent')}
                      </button>
                    )}
                    <button
                      onClick={() => { setShowAiAssistant(v => !v); if (!aiAssistant) loadAiAssistant(); }}
                      className="bg-purple-50 hover:bg-purple-100 text-purple-700 text-[10px] font-semibold px-3 py-1.5 rounded-lg transition border border-purple-200"
                    >
                      {t('courseDetail.aiAssistant')} {showAiAssistant ? '▲' : '▼'}
                    </button>
                  </div>
                </div>

                {/* ── Teacher AI Assistant panel ── */}
                {showAiAssistant && (
                  <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-xl">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs font-bold text-purple-800 uppercase tracking-wide">{t('courseDetail.aiClassSummary')}</span>
                      <button onClick={() => loadAiAssistant(true)} className="text-[10px] text-purple-500 hover:underline ml-auto">{t('courseDetail.refresh')}</button>
                    </div>
                    {aiAssistantLoading ? (
                      <div className="flex items-center gap-2 text-xs text-purple-500">
                        <div className="w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                        {t('courseDetail.analyzingClass')}
                      </div>
                    ) : aiAssistant ? (
                      <div className="space-y-3">
                        <p className="text-xs text-purple-900 font-medium">{aiAssistant.summary}</p>
                        {aiAssistant.class_stats && (
                          <div className="flex flex-wrap gap-2">
                            {[
                              { label: t('courseDetail.avgScore'), val: aiAssistant.class_stats.avg_score != null ? `${aiAssistant.class_stats.avg_score}/100` : '—', color: 'bg-blue-100 text-blue-700' },
                              { label: t('courseDetail.highRisk'), val: aiAssistant.class_stats.high_risk,   color: 'bg-red-100 text-red-700' },
                              { label: t('classification.excellent'), val: aiAssistant.class_stats.excellent, color: 'bg-green-100 text-green-700' },
                            ].map(s => (
                              <div key={s.label} className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold ${s.color}`}>
                                {s.label}: {s.val}
                              </div>
                            ))}
                          </div>
                        )}
                        {aiAssistant.insights?.length > 0 && (
                          <ul className="space-y-1 text-[10px] text-purple-800">
                            {aiAssistant.insights.map((ins: string, i: number) => (
                              <li key={i} className="flex items-start gap-1.5">
                                <span className="text-purple-400 flex-shrink-0">•</span>
                                <span>{ins}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                        {aiAssistant.attention_list?.length > 0 && (
                          <div>
                            <p className="text-[10px] font-bold text-red-700 mb-1.5">{t('courseDetail.studentsNeedingAttention')}</p>
                            <div className="flex flex-wrap gap-1.5">
                              {aiAssistant.attention_list.map((s: any) => (
                                <span key={s.student_id} className="text-[10px] bg-red-100 text-red-800 px-2 py-0.5 rounded-full font-medium">
                                  {s.student_name}
                                  {s.risk_level === 'high' && ' 🔴'}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-purple-500">{t('courseDetail.noAiData')}</p>
                    )}

                    {/* ── Feedback Trend card ── */}
                    {(feedbackTrend || feedbackTrendLoading) && (
                      <div className="mt-3 pt-3 border-t border-purple-200">
                        <p className="text-[10px] font-bold text-purple-800 uppercase tracking-wide mb-2">{t('courseDetail.feedbackSentimentTrend')}</p>
                        {feedbackTrendLoading && !feedbackTrend ? (
                          <div className="flex items-center gap-2 text-[10px] text-purple-400">
                            <div className="w-3 h-3 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
                            {t('courseDetail.loadingTrend')}
                          </div>
                        ) : feedbackTrend?.total_feedback > 0 ? (
                          <div className="space-y-2">
                            {/* Trend badge */}
                            <div className="flex items-center gap-2">
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                feedbackTrend.trend === 'worsening'  ? 'bg-red-100 text-red-700'    :
                                feedbackTrend.trend === 'improving'  ? 'bg-green-100 text-green-700' :
                                                                       'bg-gray-100 text-gray-600'
                              }`}>
                                {feedbackTrend.trend === 'worsening' ? t('courseDetail.worsening') :
                                 feedbackTrend.trend === 'improving' ? t('courseDetail.improving') : t('courseDetail.stable')}
                              </span>
                              <span className="text-[10px] text-purple-500">{feedbackTrend.total_feedback} {t('courseDetail.feedbackItems')} · {feedbackTrend.period_days}d</span>
                            </div>
                            {/* Sentiment bars */}
                            {feedbackTrend.sentiment_distribution && (
                              <div className="flex gap-1 h-2 rounded-full overflow-hidden w-full">
                                {[
                                  { key: 'positive', color: 'bg-green-400' },
                                  { key: 'neutral',  color: 'bg-gray-300'  },
                                  { key: 'negative', color: 'bg-red-400'   },
                                ].map(({ key, color }) => {
                                  const pct = feedbackTrend.sentiment_distribution[key] ?? 0;
                                  return pct > 0 ? (
                                    <div key={key} className={`${color} h-full`} style={{ width: `${pct}%` }} title={`${key}: ${pct}%`} />
                                  ) : null;
                                })}
                              </div>
                            )}
                            <div className="flex gap-3 text-[10px] text-purple-700">
                              {['positive','neutral','negative'].map(k => {
                                const pct = feedbackTrend.sentiment_distribution?.[k] ?? 0;
                                return <span key={k} className="capitalize">{k}: {pct}%</span>;
                              })}
                            </div>
                            {/* Top tags */}
                            {feedbackTrend.top_tags?.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {feedbackTrend.top_tags.slice(0, 6).map((t: any) => (
                                  <span key={t.tag} className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-medium capitalize">
                                    {t.tag.replace(/_/g, ' ')} {t.count > 1 ? `×${t.count}` : ''}
                                  </span>
                                ))}
                              </div>
                            )}
                            {/* Concern summary */}
                            {feedbackTrend.concern_summary && (
                              <p className="text-[10px] text-red-700 bg-red-50 rounded px-2 py-1">{feedbackTrend.concern_summary}</p>
                            )}
                          </div>
                        ) : (
                          <p className="text-[10px] text-purple-400">{t('courseDetail.noFeedbackPanel')}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* ── Pending Enrollment Requests ── */}
                {isOwner && detail.pending_requests?.length > 0 && (
                  <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                    <p className="text-xs font-bold text-yellow-800 mb-3">
                      {t('courseDetail.pendingRequests')} ({detail.pending_requests.length})
                    </p>
                    <div className="space-y-2">
                      {detail.pending_requests.map((req: any) => (
                        <div key={req.enrollment_id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-yellow-100">
                          <div>
                            <p className="text-xs font-semibold text-gray-800">{req.student_name}</p>
                            {req.student_email && (
                              <p className="text-[10px] text-gray-400">{req.student_email}</p>
                            )}
                            {req.requested_at && (
                              <p className="text-[10px] text-gray-400">
                                {t('courseDetail.requested')} {new Date(req.requested_at).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                          <div className="flex gap-2 flex-shrink-0">
                            <button
                              onClick={() => handleApproveRequest(req.enrollment_id)}
                              disabled={approvingId === req.enrollment_id}
                              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-[10px] font-semibold px-2.5 py-1 rounded-lg transition"
                            >
                              {approvingId === req.enrollment_id ? '…' : t('courseDetail.approve')}
                            </button>
                            <button
                              onClick={() => handleRejectRequest(req.enrollment_id)}
                              disabled={approvingId === req.enrollment_id}
                              className="bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-semibold px-2.5 py-1 rounded-lg border border-red-200 transition"
                            >
                              {t('courseDetail.reject')}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── Add-student inline panel ── */}
                {isOwner && showAddStudent && (
                  <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                    <p className="text-xs font-semibold text-gray-600 mb-2">{t('courseDetail.searchStudentsHint')}</p>
                    <div className="relative">
                      <input
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-green-300"
                        placeholder={t('courseDetail.searchNameEmail')}
                        value={studentSearch}
                        onChange={e => searchStudents(e.target.value)}
                        autoFocus
                      />
                      {searchingStudents && (
                        <span className="absolute right-3 top-2 text-gray-400 text-xs">{t('courseDetail.searching')}</span>
                      )}
                    </div>
                    {studentResults.length > 0 && (
                      <div className="mt-2 border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm">
                        {studentResults.map((s: any) => (
                          <div key={s.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 border-b border-gray-50 last:border-0">
                            <div className="flex items-center gap-2 min-w-0">
                              <UserAvatar name={s.title || '?'} size={28} />
                              <div className="min-w-0">
                                <p className="text-xs font-semibold text-gray-700 truncate">{s.title || 'Unknown student'}</p>
                                <p className="text-[10px] text-gray-400 truncate">{s.subtitle}</p>
                              </div>
                            </div>
                            <button
                              onClick={() => addStudentToCourse(s.id, s.title || 'Unknown student')}
                              disabled={enrollingId === s.id}
                              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-[10px] font-semibold px-2.5 py-1 rounded-lg transition"
                            >
                              {enrollingId === s.id ? t('courseDetail.enrolling') : t('courseDetail.enroll')}
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    {studentSearch.length >= 2 && !searchingStudents && studentResults.length === 0 && (
                      <p className="text-xs text-gray-400 mt-2">{t('courseDetail.noStudentsFound')}</p>
                    )}
                  </div>
                )}

                {/* Roster action feedback */}
                {rosterMsg && (
                  <div className={`mb-3 px-3 py-2 rounded-lg text-xs font-medium ${
                    rosterMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
                  }`}>
                    {rosterMsg.ok ? '✅' : '❌'} {rosterMsg.text}
                  </div>
                )}

                {filteredRoster.length === 0 ? (
                  <EmptyState
                    icon="👥"
                    title={detail.roster.length === 0 ? t('courseDetail.noStudentsEnrolled') : t('courseDetail.noStudentsMatch')}
                    description={detail.roster.length === 0 && isOwner ? t('courseDetail.addStudentHint') : undefined}
                  />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100">
                          {[t('courseDetail.colStudent'), t('courseDetail.colScore'), t('courseDetail.colStatus'), t('courseDetail.colActions')].map(h => (
                            <th key={h} className="text-left text-gray-400 font-semibold pb-3 pr-3">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {filteredRoster.map((s: any) => (
                          <tr key={s.student_id} className="hover:bg-gray-50 transition">
                            <td className="py-3 pr-3">
                              <div className="flex items-center gap-2.5">
                                <UserAvatar name={s.student_name} url={s.avatar_url} size={32} />
                                <div>
                                  <Link to={`/users/${s.student_id}/profile`} className="font-semibold text-gray-700 hover:underline">{s.student_name}</Link>
                                  <p className="text-gray-400">{s.student_email}</p>
                                </div>
                              </div>
                            </td>
                            <td className="py-3 pr-3">
                              {s.score != null ? (
                                <div>
                                  <span className="font-bold text-gray-800">{s.score.toFixed(1)}</span>
                                  {s.classification && (
                                    <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold ${
                                      SCORE_BADGE[s.classification] ?? 'bg-gray-100 text-gray-600'
                                    }`}>
                                      {t(`classification.${s.classification}`) || s.classification.replace('_', ' ')}
                                    </span>
                                  )}
                                  <div className="mt-1 w-20">
                                    <ProgressBar percent={Math.round(s.score)} showLabel={false} height={3} />
                                  </div>
                                  {courseRiskMap[s.student_id] && (
                                    <div className="mt-1">
                                      <RiskBadge
                                        riskLevel={courseRiskMap[s.student_id].risk_level}
                                        predictionLabel={courseRiskMap[s.student_id].prediction_label}
                                      />
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <span className="text-gray-400">{t('courseDetail.noScore')}</span>
                              )}
                            </td>
                            <td className="py-3 pr-3">
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700">
                                {s.enrollment_status}
                              </span>
                            </td>
                            <td className="py-3">
                              <div className="flex flex-wrap gap-1">
                                <Link
                                  to={`/users/${s.student_id}/profile`}
                                  className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  View Profile
                                </Link>
                                <button
                                  onClick={() => setProgressTarget({ studentId: s.student_id, studentName: s.student_name, score: s.score, classification: s.classification })}
                                  className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  {t('courseDetail.progressBtn')}
                                </button>
                                <button
                                  onClick={() => setFeedbackTarget({ studentId: s.student_id, studentName: s.student_name })}
                                  className="bg-blue-50 hover:bg-blue-100 text-blue-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  {t('courseDetail.feedbackBtn')}
                                </button>
                                <button
                                  onClick={() => setHistoryTarget({ studentId: s.student_id, studentName: s.student_name })}
                                  className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  {t('courseDetail.historyBtn')}
                                </button>
                                <button
                                  onClick={() => setAttendanceTarget({ studentId: s.student_id, studentName: s.student_name })}
                                  className="bg-green-50 hover:bg-green-100 text-green-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  {t('courseDetail.attendBtn')}
                                </button>
                                {isOwner && (
                                  <button
                                    onClick={() => { setGradeTarget({ studentId: s.student_id, studentName: s.student_name }); setGradeValue(''); setGradeSubject(''); setGradeMsg(null); }}
                                    className="bg-yellow-50 hover:bg-yellow-100 text-yellow-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    {t('courseDetail.gradeBtn') || 'Grade'}
                                  </button>
                                )}
                                <button
                                  onClick={() => setEmailTarget({ recipientId: s.student_id, recipientName: s.student_name, recipientType: 'student' })}
                                  className="bg-gray-50 hover:bg-gray-100 text-gray-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  {t('courseDetail.emailBtn')}
                                </button>
                                {isOwner && (
                                  <button
                                    onClick={() => setMessageTarget({ studentId: s.student_id, studentName: s.student_name })}
                                    className="bg-purple-50 hover:bg-purple-100 text-purple-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    {t('courseDetail.msgBtn')}
                                  </button>
                                )}
                                {isOwner && (
                                  <button
                                    onClick={() => navigate(`/chat?user_id=${s.student_id}`)}
                                    className="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    {t('courseDetail.chatBtn')}
                                  </button>
                                )}
                                {s.parent_id ? (
                                  <button
                                    onClick={() => setEmailTarget({ recipientId: s.parent_id, recipientName: s.student_name, recipientType: 'parent' })}
                                    className="bg-purple-50 hover:bg-purple-100 text-purple-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    {t('courseDetail.parentBtn')}
                                  </button>
                                ) : (
                                  <span className="text-[10px] text-gray-300 px-1 py-1">{t('courseDetail.noParent')}</span>
                                )}
                                {isOwner && s.enrollment_id && (
                                  <button
                                    onClick={() => removeStudentFromCourse(s.enrollment_id, s.student_name)}
                                    className="bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition ml-auto"
                                    title={t('courseDetail.removeFromCourse')}
                                  >
                                    {t('courseDetail.removeBtn')}
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* ── Feedback ─────────────────────────────────────────────────── */}
            {tab === 'feedback' && (
              <div className="space-y-4">

              {/* AI Grade Suggestions panel — teacher/admin only */}
              {isTeacherOrAdmin && (
                <div className="bg-white rounded-2xl shadow-sm border border-amber-100 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-bold text-gray-800 text-sm">
                      AI Grade Suggestions
                      {gradeSuggestions.length > 0 && (
                        <span className="ml-2 bg-amber-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                          {gradeSuggestions.length}
                        </span>
                      )}
                    </h2>
                    <button
                      onClick={loadGradeSuggestions}
                      className="text-xs text-gray-400 hover:text-gray-600 transition"
                      title="Refresh"
                    >↻ Refresh</button>
                  </div>
                  <p className="text-xs text-gray-400 mb-3">
                    These suggestions are generated by AI from feedback analysis. You must approve or reject each one. No grade is recorded until you approve.
                  </p>
                  {suggestionMsg && (
                    <p className={`text-xs rounded-lg px-3 py-2 mb-3 ${suggestionMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                      {suggestionMsg.text}
                    </p>
                  )}
                  {suggestionsLoading ? (
                    <p className="text-xs text-gray-400">Loading…</p>
                  ) : gradeSuggestions.length === 0 ? (
                    <p className="text-xs text-gray-400 italic">No pending grade suggestions.</p>
                  ) : (
                    <div className="space-y-3">
                      {gradeSuggestions.map((s: any) => (
                        <div key={s.id} className="flex items-start gap-3 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-gray-700 truncate">
                              {rosterNameMap[s.student_id] ?? `…${s.student_id.slice(-6)}`}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">{s.reason}</p>
                            <p className="text-xs text-amber-700 font-bold mt-1">
                              Suggested score: {s.suggested_score}/100
                            </p>
                          </div>
                          <div className="flex gap-2 flex-shrink-0">
                            <button
                              onClick={() => handleApproveSuggestion(s.id)}
                              className="bg-green-600 hover:bg-green-700 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleRejectSuggestion(s.id)}
                              className="border border-red-300 text-red-600 hover:bg-red-50 text-[10px] font-bold px-3 py-1.5 rounded-lg transition"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <h2 className="font-bold text-gray-800 text-sm mb-4">{t('courseDetail.feedbackRecords')}</h2>

                {detail.feedback.length === 0 ? (
                  <EmptyState icon="💬" title={t('courseDetail.noFeedbackRecorded')} />
                ) : (
                  <div className="space-y-3">
                    {detail.feedback.map((f: any) => (
                      <div key={f.id} className="border border-gray-100 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            SENTIMENT_BADGE[f.sentiment] ?? 'bg-gray-100 text-gray-600'
                          }`}>
                            {f.sentiment}
                          </span>
                          {f.visibility && (
                            <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
                              {f.visibility}
                            </span>
                          )}
                          {isTeacherOrAdmin && f.student_id && (
                            <span className="text-[10px] text-gray-500 font-medium ml-auto">
                              {rosterNameMap[f.student_id] ?? `…${f.student_id.slice(-6)}`}
                            </span>
                          )}
                          {f.submitted_at && (
                            <span className={`text-[10px] text-gray-400 ${isTeacherOrAdmin && f.student_id ? '' : 'ml-auto'}`}>
                              {new Date(f.submitted_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-700 leading-relaxed">{f.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </div>
            )}

            {/* ── Announce (teacher / admin only) ──────────────────────────── */}
            {tab === 'announce' && isTeacherOrAdmin && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 max-w-xl">
                <h2 className="font-bold text-gray-800 text-sm mb-1">{t('courseDetail.sendAnnouncement')}</h2>
                <p className="text-xs text-gray-400 mb-4">
                  {t('courseDetail.announcementHint')}
                </p>

                <form onSubmit={submitAnnounce} className="space-y-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">{t('courseDetail.subjectLabel')}</label>
                    <input
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      placeholder={t('courseDetail.subjectPlaceholder')}
                      value={announceForm.subject}
                      onChange={e => setAnnounceForm(f => ({ ...f, subject: e.target.value }))}
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">{t('courseDetail.messageLabel')}</label>
                    <textarea
                      rows={5}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                      placeholder={t('courseDetail.messagePlaceholder')}
                      value={announceForm.content}
                      onChange={e => setAnnounceForm(f => ({ ...f, content: e.target.value }))}
                      required
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      className="rounded"
                      checked={announceForm.include_parents}
                      onChange={e => setAnnounceForm(f => ({ ...f, include_parents: e.target.checked }))}
                    />
                    <span className="text-xs text-gray-600">{t('courseDetail.notifyParents')}</span>
                  </label>

                  {announceResult && (
                    <p className="text-xs bg-green-50 text-green-600 px-3 py-2 rounded-lg">{announceResult}</p>
                  )}
                  {announceError && (
                    <p className="text-xs bg-red-50 text-red-500 px-3 py-2 rounded-lg">{announceError}</p>
                  )}

                  <button
                    type="submit"
                    disabled={announcing}
                    className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold px-5 py-2 rounded-lg transition"
                  >
                    {announcing ? t('courseDetail.sending') : t('courseDetail.sendAnnouncementBtn')}
                  </button>
                </form>
              </div>
            )}

            {/* ── Modals ───────────────────────────────────────────────────── */}
            {feedbackTarget && (
              <QuickFeedbackModal
                studentId={feedbackTarget.studentId}
                studentName={feedbackTarget.studentName}
                courseId={course.id}
                courses={courseList}
                onClose={() => setFeedbackTarget(null)}
                onSaved={() => { setFeedbackTarget(null); load(); }}
              />
            )}
            {emailTarget && (
              <QuickEmailModal
                recipientId={emailTarget.recipientId}
                recipientName={emailTarget.recipientName}
                recipientType={emailTarget.recipientType}
                onClose={() => setEmailTarget(null)}
              />
            )}
            {historyTarget && (
              <FeedbackHistoryModal
                studentId={historyTarget.studentId}
                studentName={historyTarget.studentName}
                feedback={detail.feedback ?? []}
                onClose={() => setHistoryTarget(null)}
              />
            )}
            {attendanceTarget && (
              <QuickAttendanceModal
                studentId={attendanceTarget.studentId}
                studentName={attendanceTarget.studentName}
                courseId={course.id}
                onClose={() => setAttendanceTarget(null)}
                onSaved={() => { setAttendanceTarget(null); load(); }}
              />
            )}
            {progressTarget && (
              <StudentProgressModal
                studentId={progressTarget.studentId}
                studentName={progressTarget.studentName}
                courseId={course.id}
                currentScore={progressTarget.score}
                currentClassification={progressTarget.classification}
                onClose={() => setProgressTarget(null)}
              />
            )}
            {showGroupEmail && (
              <GroupEmailModal
                courseId={course.id}
                courseName={course.name}
                studentCount={detail.roster.length}
                onClose={() => setShowGroupEmail(false)}
              />
            )}
            {messageTarget && (
              <SendMessageModal
                recipientId={messageTarget.studentId}
                recipientName={messageTarget.studentName}
                courseId={course.id}
                courseName={course.name}
                onClose={() => setMessageTarget(null)}
                onSent={() => setMessageTarget(null)}
              />
            )}
            {gradeTarget && (
              <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="font-bold text-gray-800 text-sm">{t('courseDetail.gradeBtn') || 'Record Grade'}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">{gradeTarget.studentName}</p>
                    </div>
                    <button onClick={() => setGradeTarget(null)} className="text-gray-400 hover:text-gray-600 text-xl w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100">&times;</button>
                  </div>
                  <form onSubmit={async (e) => {
                    e.preventDefault();
                    setGradeSaving(true);
                    setGradeMsg(null);
                    try {
                      await apiService.recordGrade({
                        student_id: gradeTarget.studentId,
                        course_id: course.id,
                        score: parseFloat(gradeValue),
                        subject: gradeSubject || course.name,
                      });
                      setGradeMsg({ ok: true, text: t('courseDetail.gradeSaved') || 'Grade saved.' });
                      setTimeout(() => { setGradeTarget(null); load(); }, 1200);
                    } catch (err: any) {
                      setGradeMsg({ ok: false, text: err?.response?.data?.detail || 'Failed to save grade.' });
                    } finally {
                      setGradeSaving(false);
                    }
                  }} className="space-y-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('courseDetail.gradeScore') || 'Score (0–100)'}</label>
                      <input
                        type="number" min={0} max={100} step={0.1}
                        value={gradeValue}
                        onChange={e => setGradeValue(e.target.value)}
                        required
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-yellow-300"
                        placeholder="e.g. 87"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('courseDetail.gradeSubject') || 'Subject / Test name (optional)'}</label>
                      <input
                        value={gradeSubject}
                        onChange={e => setGradeSubject(e.target.value)}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-yellow-300"
                        placeholder={course.name}
                      />
                    </div>
                    {gradeMsg && (
                      <p className={`text-xs rounded-lg px-3 py-2 ${gradeMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>{gradeMsg.text}</p>
                    )}
                    <div className="flex gap-2 pt-1">
                      <button type="button" onClick={() => setGradeTarget(null)}
                        className="flex-1 border border-gray-200 text-gray-600 text-xs py-2 rounded-lg hover:bg-gray-50 transition">
                        {t('common.cancel')}
                      </button>
                      <button type="submit" disabled={gradeSaving}
                        className="flex-1 bg-yellow-500 hover:bg-yellow-600 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition">
                        {gradeSaving ? t('common.saving') : t('common.save')}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};
