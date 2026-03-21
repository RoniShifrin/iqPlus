import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';
import { ConflictModal, ConflictDetail } from '../components/ConflictModal';

const Toast: React.FC<{ msg: string; ok: boolean; onDismiss: () => void }> = ({ msg, ok, onDismiss }) => (
  <div className={`fixed bottom-4 right-4 z-50 px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-3 ${
    ok ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700'
  }`}>
    <span>{ok ? '✅' : '❌'}</span>
    <span>{msg}</span>
    <button onClick={onDismiss} className="ml-2 text-current opacity-60 hover:opacity-100 font-bold">×</button>
  </div>
);

interface Course {
  id: string; code: string; name: string; description?: string;
  teacher_id: string; created_by_role: string; capacity: number;
  status: 'draft' | 'published' | 'archived';
  visibility_scope: string; schedule?: any; created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  draft:     'bg-yellow-100 text-yellow-800',
  published: 'bg-green-100  text-green-800',
  archived:  'bg-gray-100   text-gray-600',
};

export const CoursesPage: React.FC = () => {
  const { user } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();
  const [courses, setCourses] = useState<Course[]>([]);
  const [enrollmentMap, setEnrollmentMap] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  // ── Parent-specific state ──────────────────────────────────────────────────
  const [parentChildren, setParentChildren] = useState<{ id: string; name: string }[]>([]);
  const [parentActiveIds, setParentActiveIds]   = useState<Set<string>>(new Set());
  const [parentPendingIds, setParentPendingIds] = useState<Set<string>>(new Set());
  const [selectedChildForCourse, setSelectedChildForCourse] = useState<Record<string, string>>({});
  const [parentEnrollMsg, setParentEnrollMsg]     = useState<Record<string, { ok: boolean; text: string }>>({});
  const [parentEnrollingKey, setParentEnrollingKey] = useState<string | null>(null);
  const [conflictModal, setConflictModal] = useState<ConflictDetail | null>(null);
  const [conflictIsParent, setConflictIsParent] = useState(false);

  const isParent  = user?.role === 'parent';
  const canManage = user?.role === 'admin' || user?.role === 'teacher';
  const isOwner   = (c: Course) => user?.role === 'admin' || c.teacher_id === (user as any)?.id;

  useEffect(() => {
    load();
    if (user?.role === 'student' || user?.role === 'parent') {
      const onVisible = () => { if (document.visibilityState === 'visible') load(); };
      document.addEventListener('visibilitychange', onVisible);
      return () => document.removeEventListener('visibilitychange', onVisible);
    }
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [cr, er, dr] = await Promise.all([
        apiService.getCourses(),
        user?.role === 'student' ? apiService.getEnrollments().catch(() => ({ data: [] }))    : Promise.resolve({ data: [] }),
        user?.role === 'parent'  ? apiService.getDashboard().catch(() => ({ data: null }))    : Promise.resolve({ data: null }),
      ]);
      setCourses(cr.data ?? []);

      if (user?.role === 'student') {
        const map: Record<string, string> = {};
        (er.data ?? []).forEach((e: any) => { map[e.course_id] = e.status?.toLowerCase() ?? ''; });
        setEnrollmentMap(map);
      }

      if (user?.role === 'parent') {
        const kids: any[] = dr.data?.metrics?.children ?? [];
        setParentChildren(kids.map((ch: any) => ({ id: ch.id, name: ch.name })));
        setParentActiveIds(new Set<string>(kids.flatMap((ch: any) => ch.course_ids ?? [])));
        setParentPendingIds(new Set<string>(kids.flatMap((ch: any) => ch.pending_course_ids ?? [])));
      }
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to load courses');
    } finally { setLoading(false); }
  };

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const act = async (fn: () => Promise<any>, successMsg?: string) => {
    try {
      await fn();
      await load();
      if (successMsg) showToast(successMsg, true);
    } catch (e: any) {
      const detail = e.response?.data?.detail || 'Action failed';
      setErr(detail);
      showToast(detail, false);
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

  const handleEnrollRequest = async (courseId: string) => {
    try {
      await apiService.requestEnrollment(courseId);
      setEnrollmentMap(prev => ({ ...prev, [courseId]: 'pending' }));
      showToast(t('courses.enrollSent'), true);
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      if (detail?.code === 'schedule_conflict') {
        setConflictIsParent(false);
        setConflictModal(detail);
      } else {
        showToast(fmtConflict(detail), false);
      }
    }
  };

  // ── Parent: request enrollment for a linked child ──────────────────────────
  const handleParentEnrollRequest = async (courseId: string) => {
    if (user?.is_approved === false) {
      showToast('Your account is pending approval by an administrator.', false);
      return;
    }
    const childId = parentChildren.length === 1
      ? parentChildren[0].id
      : (selectedChildForCourse[courseId] || '');
    if (!childId) return;
    const key = `${courseId}:${childId}`;
    setParentEnrollingKey(key);
    try {
      await apiService.requestEnrollment(courseId, childId);
      setParentEnrollMsg(prev => ({ ...prev, [key]: { ok: true, text: t('courseDetail.enrollRequestSent') } }));
      // Optimistically mark as pending so the card moves to enrolled section
      setParentPendingIds(prev => new Set([...prev, courseId]));
      showToast(t('courses.enrollSent'), true);
    } catch (e: any) {
      const detail = (e as any)?.response?.data?.detail;
      if (detail?.code === 'schedule_conflict') {
        setConflictIsParent(true);
        setConflictModal(detail);
      } else {
        const msg = fmtConflict(detail);
        setParentEnrollMsg(prev => ({ ...prev, [key]: { ok: false, text: msg } }));
        showToast(msg, false);
      }
    } finally {
      setParentEnrollingKey(null);
    }
  };

  if (loading) return <div className="flex items-center justify-center min-h-screen text-gray-500">Loading...</div>;

  // ── Shared course card renderer ────────────────────────────────────────────
  const renderCard = (course: Course) => (
    <div key={course.id} className="bg-white rounded-xl shadow hover:shadow-md transition flex flex-col">
      <div className="p-5 flex-1">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h3 className="text-lg font-bold text-gray-900 leading-snug">{course.name}</h3>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_BADGE[course.status]}`}>
            {t(`status.${course.status}`) || course.status}
          </span>
        </div>
        <p className="text-xs text-indigo-600 font-mono mb-2">{course.code}</p>
        {course.description && <p className="text-sm text-gray-600 line-clamp-2">{course.description}</p>}
        <div className="mt-3 flex gap-4 text-xs text-gray-400">
          <span>{t('courses.capacity')}: {course.capacity}</span>
          <span className="capitalize">{course.visibility_scope.replace('_', ' ')}</span>
        </div>
      </div>

      <div className="px-5 pb-4 border-t border-gray-100 pt-3 flex flex-wrap gap-2">
        {/* View detail — all roles */}
        <button
          onClick={() => navigate(`/courses/${course.id}`)}
          className="border border-gray-200 text-gray-600 hover:bg-gray-50 text-sm px-3 py-1.5 rounded-lg transition"
        >
          {t('courses.view')}
        </button>

        {/* Student: enroll / status */}
        {user?.role === 'student' && course.status === 'published' && (() => {
          const status = enrollmentMap[course.id];
          if (status === 'active' || status === 'completed') {
            return (
              <button onClick={() => navigate(`/courses/${course.id}`)}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-1.5 rounded-lg transition font-semibold">
                {t('courses.openCourse')}
              </button>
            );
          }
          if (status === 'pending') {
            return (
              <span className="flex-1 text-center text-xs font-semibold text-yellow-700 bg-yellow-50 border border-yellow-200 py-1.5 rounded-lg">
                {t('courses.pendingApproval')}
              </span>
            );
          }
          if (status === 'rejected') {
            return (
              <span className="flex-1 text-center text-xs font-semibold text-red-600 bg-red-50 border border-red-200 py-1.5 rounded-lg">
                {t('courses.requestRejected')}
              </span>
            );
          }
          return (
            <button onClick={() => handleEnrollRequest(course.id)}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm py-1.5 rounded-lg transition">
              {t('courses.requestEnrollment')}
            </button>
          );
        })()}

        {/* Parent: child enrolled → Open Course, pending → badge, not enrolled → Request */}
        {isParent && course.status === 'published' && (() => {
          // Active enrollment for any child
          if (parentActiveIds.has(course.id)) {
            return (
              <button onClick={() => navigate(`/courses/${course.id}`)}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-1.5 rounded-lg transition font-semibold">
                {t('courses.openCourse')}
              </button>
            );
          }
          // Pending enrollment for any child
          if (parentPendingIds.has(course.id)) {
            return (
              <span className="flex-1 text-center text-xs font-semibold text-yellow-700 bg-yellow-50 border border-yellow-200 py-1.5 rounded-lg">
                {t('courses.pendingApproval')}
              </span>
            );
          }
          // Not enrolled — show request button (+ child selector for multi-child parents)
          const effectiveChildId = parentChildren.length === 1
            ? parentChildren[0].id
            : (selectedChildForCourse[course.id] || '');
          const key = `${course.id}:${effectiveChildId}`;
          const msg = parentEnrollMsg[key];
          if (msg) {
            return (
              <span className={`flex-1 text-center text-xs font-semibold py-1.5 rounded-lg border ${
                msg.ok ? 'text-green-700 bg-green-50 border-green-200' : 'text-red-600 bg-red-50 border-red-200'
              }`}>
                {msg.ok ? '✓ ' : '✗ '}{msg.text}
              </span>
            );
          }
          return (
            <>
              {parentChildren.length > 1 && (
                <select
                  value={selectedChildForCourse[course.id] || ''}
                  onChange={e => setSelectedChildForCourse(prev => ({ ...prev, [course.id]: e.target.value }))}
                  className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                >
                  <option value="">Select child…</option>
                  {parentChildren.map(ch => (
                    <option key={ch.id} value={ch.id}>{ch.name}</option>
                  ))}
                </select>
              )}
              <button
                onClick={() => handleParentEnrollRequest(course.id)}
                disabled={parentEnrollingKey === key || (parentChildren.length > 1 && !effectiveChildId)}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm py-1.5 rounded-lg transition"
              >
                {parentEnrollingKey === key ? t('courseDetail.sending') : t('courses.requestEnrollment')}
              </button>
            </>
          );
        })()}

        {/* Owner / Admin management */}
        {isOwner(course) && (
          <>
            <button onClick={() => navigate(`/courses/${course.id}/edit`)}
              className="flex-1 border border-indigo-300 text-indigo-700 hover:bg-indigo-50 text-sm py-1.5 rounded-lg transition">
              {t('common.edit')}
            </button>
            {course.status === 'draft' && (
              <button onClick={() => act(() => apiService.publishCourse(course.id))}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm py-1.5 rounded-lg transition">
                {t('courses.publish')}
              </button>
            )}
            {course.status === 'published' && (
              <button onClick={() => act(() => apiService.archiveCourse(course.id))}
                className="flex-1 bg-yellow-500 hover:bg-yellow-600 text-white text-sm py-1.5 rounded-lg transition">
                {t('courses.archive')}
              </button>
            )}
            <button
              onClick={() => {
                if (window.confirm(`Delete "${course.name}"?\n\nEnrollment records will be preserved. This cannot be undone.`))
                  act(() => apiService.deleteCourse(course.id), 'Course deleted.');
              }}
              className="border border-red-300 text-red-600 hover:bg-red-50 text-sm px-3 py-1.5 rounded-lg transition"
              title={t('courses.deleteCourse')}>
              🗑
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{t('courses.title')}</h1>
          <p className="text-gray-500 mt-1">{courses.length} {t('courses.title').toLowerCase()}</p>
        </div>
        {canManage && (
          <Link to="/courses/new"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg font-semibold transition">
            {t('courses.newCourse')}
          </Link>
        )}
      </div>

      {err && (
        <div className="mb-4 p-3 bg-red-50 border border-red-300 text-red-700 rounded-lg text-sm flex justify-between">
          <span>{err}</span>
          <button onClick={() => setErr('')} className="font-bold ml-2">×</button>
        </div>
      )}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDismiss={() => setToast(null)} />}
      {conflictModal && (
        <ConflictModal
          conflict={conflictModal}
          isParent={conflictIsParent}
          onClose={() => setConflictModal(null)}
          onChooseChild={() => setConflictModal(null)}
        />
      )}

      {courses.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <div className="text-5xl mb-4">📚</div>
          <p className="text-xl">{t('courses.noCourses')}</p>
          {canManage && <Link to="/courses/new" className="mt-4 inline-block text-indigo-600 font-semibold hover:underline">{t('courses.createFirst')}</Link>}
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.map(renderCard)}
        </div>
      )}
    </div>
  );
};
