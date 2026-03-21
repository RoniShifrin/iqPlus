import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CircularProgress } from '../components/widgets/CircularProgress';
import { WeeklySchedule, coursesToSlots } from '../components/widgets/WeeklySchedule';
import { ProgressBar, labelColor } from '../components/widgets/ProgressBar';
import { EmptyState } from '../components/widgets/EmptyState';
import { ErrorState } from '../components/widgets/ErrorState';
import { QuickFeedbackModal } from '../components/QuickFeedbackModal';
import { QuickEmailModal } from '../components/QuickEmailModal';
import { SendMessageModal } from '../components/SendMessageModal';
import { AIInsightsCard } from '../components/AIInsightsCard';
import { apiService } from '../services/apiService';
import { useAuth } from '../contexts/AuthContext';
import { UserAvatar } from '../components/UserAvatar';
import { formatActivityDescription } from '../utils/enumLabels';

const VALID_TABS = new Set(['overview','students','courses','schedule','progress','records','updates','requests']);

const ALERT_COLOR: Record<string, string> = {
  critical: 'bg-red-50 border-red-300 text-red-800',
  warning:  'bg-yellow-50 border-yellow-300 text-yellow-800',
  info:     'bg-blue-50 border-blue-200 text-blue-800',
};
const ALERT_ICON: Record<string, string> = { critical: '🚨', warning: '⚠️', info: 'ℹ️' };

const SCORE_BADGE: Record<string, string> = {
  excellent:       'bg-green-100 text-green-700',
  good:            'bg-blue-100 text-blue-700',
  average:         'bg-yellow-100 text-yellow-700',
  needs_attention: 'bg-red-100 text-red-700',
};
const SCORE_LABEL: Record<string, string> = {
  excellent:       'Excellent',
  good:            'Good',
  average:         'Average',
  needs_attention: 'Needs Attention',
};

const UPDATE_BADGE: Record<string, string> = {
  ai_alert:     'bg-red-100 text-red-700',
  enrollment:   'bg-blue-100 text-blue-700',
  lesson_record:'bg-green-100 text-green-700',
};

export const TeacherDashboard: React.FC = () => {
  const { user } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'overview';
  const [tab, setTab] = useState(VALID_TABS.has(initialTab) ? initialTab : 'overview');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Lesson record form state
  const [recForm, setRecForm] = useState({
    student_id: '', course_id: '',
    lesson_date: new Date().toISOString().slice(0, 10),
    attendance_status: 'present',
    grade_value: '', teacher_feedback: '',
  });
  const [recLoading, setRecLoading] = useState(false);
  const [recMsg, setRecMsg] = useState<string | null>(null);

  // AI alerts
  const [aiAlerts, setAiAlerts] = useState<any[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

  // Enrollments + scores for the students tab
  const [enrollments, setEnrollments] = useState<any[]>([]);
  const [studentScores, setStudentScores] = useState<Record<string, any>>({});

  // Course-specific enrollments for Lesson Records student dropdown
  const [courseEnrollments, setCourseEnrollments] = useState<any[]>([]);
  const [courseEnrollmentsLoading, setCourseEnrollmentsLoading] = useState(false);

  // Updates
  const [updates, setUpdates] = useState<any[]>([]);
  const [updatesLoading, setUpdatesLoading] = useState(false);

  // Conversations
  const [convos, setConvos] = useState<any[]>([]);
  const [convosLoading, setConvosLoading] = useState(false);

  // Dashboard AI insights
  const [dashInsights, setDashInsights] = useState<string[]>([]);
  const [dashInsightsLoading, setDashInsightsLoading] = useState(false);

  // Pending enrollment requests (teacher-owned courses)
  const [pendingRequests, setPendingRequests] = useState<any[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingActing, setPendingActing] = useState<string | null>(null);

  // Quick action modals
  const [feedbackTarget, setFeedbackTarget] = useState<{ studentId: string; studentName: string; courseId?: string } | null>(null);
  const [emailTarget, setEmailTarget] = useState<{ recipientId: string; recipientName: string; recipientType: 'student' | 'parent' } | null>(null);
  const [messageTarget, setMessageTarget] = useState<{ studentId: string; studentName: string; courseId?: string } | null>(null);

  // Sync tab state when URL query param changes (sidebar navigation on same route)
  useEffect(() => {
    const urlTab = searchParams.get('tab') || 'overview';
    setTab(VALID_TABS.has(urlTab) ? urlTab : 'overview');
  }, [searchParams]);

  const load = () => {
    setLoading(true);
    setError(null);
    apiService.getDashboard()
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  };

  const loadPendingRequests = () => {
    setPendingLoading(true);
    apiService.getPendingTeacherRequests()
      .then(r => setPendingRequests(r.data ?? []))
      .catch(() => {})
      .finally(() => setPendingLoading(false));
  };

  const handleApproveRequest = async (enrollmentId: string) => {
    setPendingActing(enrollmentId);
    try {
      await apiService.approveEnrollment(enrollmentId);
      setPendingRequests(prev => prev.filter(r => r.enrollment_id !== enrollmentId));
    } catch { /* let user retry */ }
    finally { setPendingActing(null); }
  };

  const handleRejectRequest = async (enrollmentId: string) => {
    setPendingActing(enrollmentId);
    try {
      await apiService.rejectEnrollment(enrollmentId);
      setPendingRequests(prev => prev.filter(r => r.enrollment_id !== enrollmentId));
    } catch { /* let user retry */ }
    finally { setPendingActing(null); }
  };

  useEffect(() => { load(); loadAlerts(); loadEnrollmentsAndScores(); loadPendingRequests(); }, []);

  // When the selected course changes in Lesson Records, fetch that course's enrollments directly.
  // This is more reliable than filtering the preloaded all-enrollments array.
  useEffect(() => {
    if (!recForm.course_id) { setCourseEnrollments([]); return; }
    setCourseEnrollmentsLoading(true);
    apiService.getEnrollments({ course_id: recForm.course_id })
      .then(r => {
        const all: any[] = r.data ?? [];
        // Show active + pending; exclude withdrawn/rejected
        setCourseEnrollments(all.filter((e: any) => e.status !== 'withdrawn' && e.status !== 'rejected'));
      })
      .catch(() => setCourseEnrollments([]))
      .finally(() => setCourseEnrollmentsLoading(false));
  }, [recForm.course_id]);

  const loadDashInsights = () => {
    setDashInsightsLoading(true);
    apiService.getDashboardInsights()
      .then(r => setDashInsights(r.data?.insights ?? []))
      .catch(() => {})
      .finally(() => setDashInsightsLoading(false));
  };

  useEffect(() => {
    if (tab === 'requests') loadPendingRequests();
    if (tab === 'updates' || tab === 'overview') loadUpdates();
    if (tab === 'overview') {
      setConvosLoading(true);
      apiService.getConversations()
        .then(r => setConvos(r.data ?? []))
        .catch(() => {})
        .finally(() => setConvosLoading(false));
      loadDashInsights();
    }
  }, [tab]);

  const loadAlerts = () => {
    setAlertsLoading(true);
    apiService.getAIAlerts()
      .then(r => setAiAlerts(r.data))
      .catch(() => {})
      .finally(() => setAlertsLoading(false));
  };

  const loadEnrollmentsAndScores = () => {
    apiService.getEnrollments()
      .then(async r => {
        const enrs: any[] = r.data ?? [];
        setEnrollments(enrs);
        const uniqueStudents = [...new Set(enrs.map((e: any) => e.student_id))] as string[];
        const scoreMap: Record<string, any> = {};
        await Promise.all(
          uniqueStudents.map(sid =>
            apiService.getStudentScores(sid)
              .then(sr => {
                const list: any[] = sr.data ?? [];
                if (list.length > 0) {
                  const avg = list.reduce((a: number, s: any) => a + s.score, 0) / list.length;
                  const best = list.reduce((b: any, s: any) => s.score > (b?.score ?? -1) ? s : b, null);
                  scoreMap[sid] = { avg: Math.round(avg * 10) / 10, best };
                }
              })
              .catch(() => {})
          )
        );
        setStudentScores(scoreMap);
      })
      .catch(() => {});
  };

  const loadUpdates = () => {
    setUpdatesLoading(true);
    apiService.getDashboardUpdates()
      .then(r => setUpdates(r.data?.updates ?? []))
      .catch(() => {})
      .finally(() => setUpdatesLoading(false));
  };

  const submitRecord = async (e: React.FormEvent) => {
    e.preventDefault();

    // JS guard — HTML `required` attributes catch most cases but not programmatic state
    if (!recForm.course_id || !recForm.student_id) {
      setRecMsg('⚠ Please select a course and a student.');
      return;
    }

    setRecLoading(true);
    setRecMsg(null);
    const savedName = studentNameMap[recForm.student_id] ?? 'Student';
    try {
      await apiService.createLessonRecord({
        ...recForm,
        // Use explicit UTC noon to avoid timezone date-boundary issues
        lesson_date: `${recForm.lesson_date}T12:00:00.000Z`,
        grade_value: recForm.grade_value !== '' ? parseFloat(recForm.grade_value) : null,
      });
      // After save: keep course + date + attendance so teacher can quickly record
      // the next student in the same lesson — only reset the per-student fields.
      setRecForm(f => ({ ...f, student_id: '', grade_value: '', teacher_feedback: '' }));
      setRecMsg(`✓ Record saved for ${savedName}.`);
      loadAlerts();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => d?.msg ?? String(d)).join('; ')
        : 'Failed to save lesson record.';
      setRecMsg(msg);
    } finally {
      setRecLoading(false);
    }
  };

  const courses: any[] = data?.courses || [];
  const m = data?.metrics || {};
  const scheduleSlots = coursesToSlots(courses, user?.display_name || user?.first_name || 'Me');

  // Course filter for students tab
  const [selectedCourseFilter, setSelectedCourseFilter] = useState('');
  // Course filter for progress tab
  const [progressCourseFilter, setProgressCourseFilter] = useState('');

  // Build student name map from dashboard's student_progress (has real names)
  const studentNameMap: Record<string, string> = {};
  (m.student_progress || []).forEach((sp: any) => {
    studentNameMap[sp.student_id] = sp.student_name;
  });

  // Build unified student list: prefer student_progress (has names), fall back to enrollments
  const allStudentRows: any[] = m.student_progress?.length > 0
    ? m.student_progress
    : [...new Map(enrollments.map((e: any) => [e.student_id, e])).values()].map((e: any) => ({
        student_id: e.student_id,
        student_name: studentNameMap[e.student_id] ?? null,
        score: studentScores[e.student_id]?.avg ?? null,
        classification: studentScores[e.student_id]?.best?.classification ?? null,
      }));

  const studentRows = selectedCourseFilter
    ? allStudentRows.filter((s: any) => s.course_id === selectedCourseFilter)
    : allStudentRows;

  return (
    <DashboardLayout tabs={[
      { key: 'overview',  label: t('tab.overview')       },
      { key: 'students',  label: t('tab.myStudents')     },
      { key: 'courses',   label: t('tab.myCourses')      },
      { key: 'schedule',  label: t('tab.schedule')       },
      { key: 'progress',  label: t('tab.progress')       },
      { key: 'records',   label: t('tab.lessonRecords')  },
      { key: 'updates',   label: t('tab.updates')        },
      { key: 'requests',  label: pendingRequests.length > 0 ? `Requests (${pendingRequests.length})` : 'Requests' },
    ]} activeTab={tab} onTabChange={setTab}>
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {/* Stat row */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: t('nav.myCourses'),         value: m.my_courses ?? 0,              color: 'bg-blue-500' },
              { label: t('progress.totalStudents'), value: m.total_enrolled_students ?? 0, color: 'bg-orange-400' },
              { label: t('stat.draftCourses'),      value: m.draft_courses ?? 0,           color: 'bg-yellow-400' },
            ].map(s => (
              <div key={s.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl ${s.color} opacity-80`} />
                <div>
                  <p className="text-2xl font-black text-gray-900">{s.value}</p>
                  <p className="text-xs text-gray-500 font-medium">{s.label}</p>
                </div>
              </div>
            ))}
          </div>

          {tab === 'overview' && (
            <>
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Left: Students + Courses */}
              <div className="lg:col-span-2 space-y-6">
                {/* Students overview */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-bold text-gray-800 text-sm">{t('dash.studentsOverview')}</h2>
                    <button onClick={() => setTab('students')} className="text-blue-600 text-xs hover:underline">{t('dash.allStudents')}</button>
                  </div>
                  {studentRows.length === 0 ? (
                    <EmptyState icon="👥" title={t('record.noEnrollments')} description={t('courses.createFirst')} />
                  ) : (
                    <div className="space-y-2">
                      {studentRows.slice(0, 5).map((s: any) => {
                        const avg = s.score ?? null;
                        const cls = s.classification ?? null;
                        const displayName = s.student_name || studentNameMap[s.student_id] || s.student_id;
                        return (
                          <div key={s.student_id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                            <UserAvatar name={displayName} url={s.avatar_url} size={32} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-semibold text-gray-700 truncate">
                                <Link to={`/users/${s.student_id}/profile`} className="hover:underline">{displayName}</Link>
                              </p>
                              {avg !== null && (
                                <div className="mt-0.5 w-full max-w-[120px]">
                                  <ProgressBar percent={Math.round(avg)} showLabel={false} height={4} />
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              {avg !== null ? (
                                <>
                                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${labelColor(Math.round(avg))}`}>{avg}</span>
                                  {cls && <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${SCORE_BADGE[cls] ?? ''}`}>{t(`classification.${cls}`) || SCORE_LABEL[cls] || cls}</span>}
                                </>
                              ) : (
                                <span className="text-xs text-gray-400">{t('courseDetail.noScore')}</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {studentRows.length > 5 && (
                        <button onClick={() => setTab('students')} className="w-full text-center text-xs text-blue-600 hover:underline py-1">
                          +{studentRows.length - 5} {t('dash.moreStudents')}
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Courses preview */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-bold text-gray-800 text-sm">{t('nav.myCourses')}</h2>
                    <button onClick={() => setTab('courses')} className="text-blue-600 text-xs hover:underline">{t('dash.allCourses')}</button>
                  </div>
                  {courses.length === 0 ? (
                    <EmptyState icon="📚" title={t('courses.noCourses')} description={t('courseForm.draftNote')} />
                  ) : (
                    <div className="space-y-2">
                      {courses.slice(0, 3).map((c: any, idx: number) => (
                        <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-gray-50 hover:border-blue-100 hover:bg-blue-50/20 transition">
                          <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                            ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                          }`}>{c.code.slice(0,3)}</div>
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold text-gray-800 text-sm truncate">{c.name}</p>
                            <p className="text-xs text-gray-400">{c.enrolled_count ?? 0}/{c.capacity} {t('courseDetail.studentsCount')}</p>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              c.status === 'published' ? 'bg-green-100 text-green-700' :
                              c.status === 'draft' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                            }`}>{t(`status.${c.status}`) || c.status}</span>
                            <button onClick={() => navigate(`/courses/${c.id}`)} className="text-xs text-blue-600 hover:underline">{t('courses.view')}</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Right: Schedule + Chat + AI Alerts */}
              <div className="space-y-6">
                {/* Chat preview */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-bold text-gray-800 text-sm">{t('dash.recentChats')}</h2>
                    <Link to="/chat" className="text-blue-600 text-xs hover:underline">{t('dash.goToChat')}</Link>
                  </div>
                  {convosLoading ? (
                    <div className="flex justify-center py-6">
                      <div className="w-5 h-5 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : convos.length === 0 ? (
                    <p className="text-xs text-gray-400 text-center py-4">{t('dash.noConversations')}</p>
                  ) : (
                    <div className="space-y-1">
                      {convos.slice(0, 3).map((c: any) => (
                        <Link key={c.id} to={`/chat?conv=${c.id}`} className="flex items-center gap-2.5 p-2 rounded-xl hover:bg-gray-50 transition">
                          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-300 to-purple-400 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                            {(c.other_participant_name || c.course_name || '?').slice(0,2).toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <p className="text-xs font-semibold text-gray-700 truncate">{c.other_participant_name || c.course_name || 'Chat'}</p>
                              {c.unread_count > 0 && (
                                <span className="text-[10px] bg-blue-500 text-white rounded-full px-1.5 ml-1 flex-shrink-0">{c.unread_count}</span>
                              )}
                            </div>
                            {c.last_message_preview && <p className="text-[11px] text-gray-400 truncate">{c.last_message_preview}</p>}
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>

                {/* AI Alerts preview */}
                {aiAlerts.length > 0 && (
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="font-bold text-gray-800 text-sm">{t('dash.aiAlerts')}</h2>
                      <button onClick={() => setTab('records')} className="text-blue-600 text-xs hover:underline">{t('dash.viewRecords')}</button>
                    </div>
                    <div className="space-y-2">
                      {aiAlerts.slice(0, 3).map((a: any) => (
                        <div key={a.id} className={`p-2.5 rounded-lg border text-xs ${ALERT_COLOR[a.alert_level] ?? ALERT_COLOR.info}`}>
                          <div className="flex items-center gap-1 font-semibold mb-0.5">
                            <span>{ALERT_ICON[a.alert_level] ?? 'ℹ️'}</span>
                            <span className="uppercase tracking-wide text-[10px]">{a.alert_level}</span>
                          </div>
                          <p className="line-clamp-2">{a.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Dashboard Insights */}
                <AIInsightsCard
                  insights={dashInsights}
                  loading={dashInsightsLoading}
                  onRefresh={loadDashInsights}
                />
              </div>
            </div>

            {/* Full-width weekly timetable */}
            <div className="mt-6 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-gray-800 text-sm">{t('dash.weeklyTimetable')}</h2>
                  {scheduleSlots.length > 0 && (
                    <p className="text-[11px] text-gray-400 mt-0.5">{t('dash.clickToOpen')}</p>
                  )}
                </div>
                <button onClick={() => setTab('schedule')} className="text-blue-600 text-xs hover:underline">{t('dash.fullSchedule')}</button>
              </div>
              {scheduleSlots.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">{t('dash.noScheduleData')}</p>
              ) : (
                <WeeklySchedule
                  slots={scheduleSlots}
                  onSlotClick={slot => slot.id && navigate(`/courses/${slot.id}`)}
                />
              )}
            </div>
            </>
          )}

          {tab === 'students' && (
            <div className="space-y-4">
              {/* Header + filter */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                  <div>
                    <h2 className="font-bold text-gray-800 text-sm">{t('tab.myStudents')}</h2>
                    <p className="text-xs text-gray-400 mt-0.5">{t('dash.manageStudents')}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <select
                      className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      value={selectedCourseFilter}
                      onChange={e => setSelectedCourseFilter(e.target.value)}
                    >
                      <option value="">{t('dash.allCoursesOpt')}</option>
                      {courses.map((c: any) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <span className="text-xs text-gray-400">{studentRows.length} {t('courseDetail.studentsCount')}</span>
                  </div>
                </div>

                {studentRows.length === 0 ? (
                  <EmptyState icon="👥" title={t('record.noEnrollments')} description={t('courses.createFirst')} />
                ) : (
                  <div className="divide-y divide-gray-50">
                    {studentRows.map((s: any) => {
                      const displayName = s.student_name || studentNameMap[s.student_id] || s.student_id;
                      const courseId = s.course_id || selectedCourseFilter || undefined;
                      const courseName = s.course_name || courses.find((c: any) => c.id === selectedCourseFilter)?.name;
                      return (
                        <div key={`${s.student_id}-${s.course_id ?? ''}`} className="flex items-center gap-3 py-3">
                          {/* Avatar */}
                          <UserAvatar name={displayName} url={s.avatar_url} size={36} />

                          {/* Identity */}
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-gray-800 truncate">
                              <Link to={`/users/${s.student_id}/profile`} className="hover:underline">{displayName}</Link>
                            </p>
                            {courseName && (
                              <p className="text-[10px] text-gray-400 truncate">{courseName}</p>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap justify-end">
                            <Link
                              to={`/users/${s.student_id}/profile`}
                              className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                            >
                              View Profile
                            </Link>
                            {courseId && (
                              <button
                                onClick={() => navigate(`/courses/${courseId}`)}
                                className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                              >
                                {t('common.viewCourse')}
                              </button>
                            )}
                            <button
                              onClick={() => setFeedbackTarget({ studentId: s.student_id, studentName: displayName, courseId })}
                              className="bg-blue-50 hover:bg-blue-100 text-blue-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                            >
                              {t('courseDetail.feedbackBtn')}
                            </button>
                            <button
                              onClick={() => setMessageTarget({ studentId: s.student_id, studentName: displayName, courseId })}
                              className="bg-purple-50 hover:bg-purple-100 text-purple-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                            >
                              {t('courseDetail.msgBtn')}
                            </button>
                            <button
                              onClick={() => setEmailTarget({ recipientId: s.student_id, recipientName: displayName, recipientType: 'student' })}
                              className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                            >
                              {t('common.email')}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'courses' && (
            <div className="grid lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">{t('nav.myCourses')}</h2>
                  <Link to="/courses/new" className="bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-blue-700 transition">
                    {t('courses.newCourse')}
                  </Link>
                </div>

                {courses.length === 0 ? (
                  <EmptyState icon="📚" title={t('courses.noCourses')} description={t('courseForm.draftNote')} />
                ) : (
                  <div className="space-y-2">
                    {courses.map((c: any, idx: number) => (
                      <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 transition">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                          ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                        }`}>
                          {c.code.slice(0,3)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-800 text-sm truncate">{c.name}</p>
                          <p className="text-xs text-gray-400 font-mono">{c.code}</p>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <div className="text-right">
                            <p className="text-xs text-gray-500">{c.enrolled_count ?? 0}/{c.capacity}</p>
                            <p className="text-xs text-gray-400">{t('courseDetail.studentsCount')}</p>
                          </div>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            c.status === 'published' ? 'bg-green-100 text-green-700' :
                            c.status === 'draft' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                          }`}>{t(`status.${c.status}`) || c.status}</span>
                          <button onClick={() => navigate(`/courses/${c.id}`)} className="text-gray-600 hover:underline text-xs">{t('courses.view')}</button>
                          <button onClick={() => navigate(`/courses/${c.id}/edit`)} className="text-blue-600 hover:underline text-xs">{t('common.edit')}</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Schedule sidebar */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <h2 className="font-bold text-gray-800 text-sm mb-4">{t('dash.scheduleOverview')}</h2>
                {scheduleSlots.length > 0 ? (
                  <div className="space-y-2">
                    {scheduleSlots.slice(0, 8).map((s, i) => (
                      <div key={i} className="flex items-center gap-3 text-xs">
                        <span className="text-gray-400 w-14 flex-shrink-0">{s.time}</span>
                        <span className={`${s.color} text-white px-2 py-1 rounded-lg flex-1 truncate`}>{s.course}</span>
                        <span className="text-gray-400 truncate">{s.day.slice(0,3)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm">{t('schedule.noScheduleData')}</p>
                )}
              </div>
            </div>
          )}

          {tab === 'schedule' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-gray-800 text-sm">{t('dash.myTeachingSchedule')}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">{courses.length} {t('tab.myCourses')} · {m.total_enrolled_students ?? 0} {t('courseDetail.studentsCount')}</p>
                </div>
                <span className="text-xs text-gray-400">{t('dash.thisWeek')}</span>
              </div>
              {scheduleSlots.length > 0 ? (
                <WeeklySchedule slots={scheduleSlots} />
              ) : (
                <EmptyState icon="📅" title={t('schedule.noScheduleYet')} description={t('schedule.addScheduleDesc')} />
              )}
            </div>
          )}

          {tab === 'progress' && (() => {
            const allProgress: any[] = m.student_progress ?? [];
            const progressRows = progressCourseFilter
              ? allProgress.filter((sp: any) => sp.course_id === progressCourseFilter)
              : allProgress;
            const progressCourses = [...new Map(allProgress.map((sp: any) => [sp.course_id, sp.course_name])).entries()];

            // Class-level stats from filtered rows
            const classAvg = progressRows.length
              ? Math.round(progressRows.reduce((a: number, sp: any) => a + (sp.score ?? 0), 0) / progressRows.length)
              : 0;
            const distCounts: Record<string, number> = { excellent: 0, good: 0, average: 0, needs_attention: 0 };
            progressRows.forEach((sp: any) => {
              const cls = sp.classification ?? 'average';
              if (cls in distCounts) distCounts[cls]++;
            });
            const atRiskCount = distCounts.needs_attention;

            return (
              <div className="space-y-4">
                {/* Course filter */}
                {progressCourses.length > 1 && (
                  <div className="flex items-center gap-3">
                    <label className="text-xs text-gray-500">{t('progress.courseFilter')}</label>
                    <select
                      value={progressCourseFilter}
                      onChange={e => setProgressCourseFilter(e.target.value)}
                      className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                    >
                      <option value="">{t('progress.allCourses')}</option>
                      {progressCourses.map(([cid, cname]) => (
                        <option key={cid} value={cid}>{cname}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Class summary row */}
                {progressRows.length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-col items-center">
                      <CircularProgress percent={classAvg} size={80} />
                      <p className="text-[10px] text-gray-400 mt-2 text-center">{t('dash.classAverage')}</p>
                    </div>
                    {([
                      { key: 'excellent',       color: 'bg-green-100 text-green-700'  },
                      { key: 'good',            color: 'bg-blue-100 text-blue-700'   },
                      { key: 'average',         color: 'bg-yellow-100 text-yellow-700'},
                      { key: 'needs_attention', color: 'bg-red-100 text-red-700'     },
                    ] as const).map(({ key, color }) => (
                      <div key={key} className={`rounded-2xl border shadow-sm p-4 flex flex-col items-center justify-center ${color}`}>
                        <p className="text-2xl font-black">{distCounts[key]}</p>
                        <p className="text-[10px] font-semibold mt-0.5">{t(`classification.${key}`)}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* At-risk callout */}
                {atRiskCount > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-center gap-3 text-sm text-red-700">
                    <span className="text-lg">⚠️</span>
                    <span>
                      <strong>{atRiskCount} {t('courseDetail.studentsCount')}</strong> {t('progress.atRiskCallout')}
                    </span>
                  </div>
                )}

                {/* Per-student score breakdown */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">{t('dash.academicPerformance')}</h2>
                  {progressRows.length === 0 ? (
                    <p className="text-gray-400 text-xs text-center py-8">{t('dash.noScores')}</p>
                  ) : (
                    <div className="space-y-5">
                      {progressRows.map((sp: any, i: number) => {
                        const p = Math.round(sp.score ?? 0);
                        const cls = sp.classification ?? 'average';
                        const isAtRisk = cls === 'needs_attention';
                        // Look up full score breakdown from the separately loaded studentScores
                        const scoreDetail = studentScores[sp.student_id]?.best;
                        return (
                          <div
                            key={`${sp.student_id}-${sp.course_id ?? i}`}
                            className={`rounded-xl border p-3 ${isAtRisk ? 'border-red-200 bg-red-50/40' : 'border-gray-100'}`}
                          >
                            {/* Name + badge + score */}
                            <div className="flex items-center justify-between gap-2 mb-2">
                              <div className="min-w-0">
                                <p className="text-xs font-semibold text-gray-800 truncate">{sp.student_name ?? sp.student_id?.slice(-8)}</p>
                                {!progressCourseFilter && sp.course_name && (
                                  <p className="text-[10px] text-gray-400 truncate">{sp.course_name}</p>
                                )}
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                {isAtRisk && <span className="text-[10px]">⚠️</span>}
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${SCORE_BADGE[cls] ?? ''}`}>
                                  {t(`classification.${cls}`) || SCORE_LABEL[cls] || cls}
                                </span>
                                <span className="text-xs font-black text-gray-700">{p}</span>
                              </div>
                            </div>

                            {/* Composite bar */}
                            <ProgressBar percent={p} showLabel={false} height={5} />

                            {/* Sub-score breakdown (only when detail is available) */}
                            {scoreDetail && (
                              <div className="mt-2 grid grid-cols-4 gap-1 text-[10px] text-center">
                                {([
                                  { tKey: 'progress.grades',     key: 'grade_score'      },
                                  { tKey: 'progress.attendance', key: 'attendance_score' },
                                  { tKey: 'progress.feedback',   key: 'feedback_score'   },
                                  { tKey: 'progress.trend',      key: 'trend_score'      },
                                ] as const).map(({ tKey, key }) => {
                                  const val = Math.round(scoreDetail[key] ?? 0);
                                  return (
                                    <div key={key} className="bg-gray-50 rounded-lg py-1 px-0.5">
                                      <p className="font-bold text-gray-700">{val}</p>
                                      <p className="text-gray-400 leading-tight">{t(tKey)}</p>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* AI Alerts relevant to this view */}
                {aiAlerts.length > 0 && (
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="font-bold text-gray-800 text-sm">{t('dash.aiAlerts')}</h2>
                      <button onClick={loadAlerts} className="text-xs text-blue-600 hover:underline">{t('common.refresh')}</button>
                    </div>
                    <div className="space-y-2">
                      {aiAlerts.slice(0, 5).map((a: any) => (
                        <div key={a.id} className={`p-3 rounded-xl border text-xs ${ALERT_COLOR[a.alert_level] ?? ALERT_COLOR.info}`}>
                          <div className="flex items-center gap-1.5 font-semibold mb-0.5">
                            <span>{ALERT_ICON[a.alert_level] ?? 'ℹ️'}</span>
                            <span className="uppercase tracking-wide text-[10px]">{a.alert_level}</span>
                            <span className="ml-auto text-[10px] opacity-60">{new Date(a.created_at).toLocaleDateString()}</span>
                          </div>
                          <p>{a.message}</p>
                          {a.recommendation && <p className="mt-0.5 opacity-70 italic">{a.recommendation}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {tab === 'records' && (() => {
            // Deduplicate courseEnrollments (fetched live when course changes)
            const seen = new Set<string>();
            const courseStudents = courseEnrollments.filter((e: any) => {
              if (seen.has(e.student_id)) return false;
              seen.add(e.student_id);
              return true;
            });

            // Selected student's score info (from already-loaded studentScores)
            const selScore = recForm.student_id ? studentScores[recForm.student_id] : null;
            const selName  = recForm.student_id ? (studentNameMap[recForm.student_id] ?? null) : null;

            // Context-aware AI alerts: narrow to student → course → all
            const contextAlerts = recForm.student_id
              ? aiAlerts.filter((a: any) => a.student_id === recForm.student_id)
              : recForm.course_id
              ? aiAlerts.filter((a: any) => a.course_id === recForm.course_id)
              : aiAlerts;
            const alertTitle = recForm.student_id && selName
              ? `AI Alerts — ${selName}`
              : recForm.course_id
              ? `AI Alerts — ${courses.find((c: any) => c.id === recForm.course_id)?.name ?? 'Course'}`
              : 'AI Alerts';

            return (
              <div className="grid lg:grid-cols-2 gap-6">
                {/* ── Record form ─────────────────────────────────────────── */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-1">{t('dash.recordLesson')}</h2>
                  <p className="text-[11px] text-gray-400 mb-4">
                    {t('dash.recordLessonHint')}
                  </p>

                  {/* Inline status message — shown at the top so it's never missed */}
                  {recMsg && (
                    <p className={`text-xs mb-3 px-3 py-2 rounded-lg font-medium ${
                      recMsg.startsWith('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-500'
                    }`}>
                      {recMsg}
                    </p>
                  )}

                  <form onSubmit={submitRecord} className="space-y-3 text-sm">
                    {/* 1 — Course */}
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('history.course')} <span className="text-red-400">*</span></label>
                      <select
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        value={recForm.course_id}
                        onChange={e => setRecForm(f => ({ ...f, course_id: e.target.value, student_id: '' }))}
                        required
                      >
                        <option value="">{t('record.selectCourse')}</option>
                        {courses.map((c: any) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>

                    {/* 2 — Student (disabled until course chosen) */}
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('courseDetail.colStudent')} <span className="text-red-400">*</span></label>
                      <select
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50 disabled:bg-gray-50"
                        value={recForm.student_id}
                        onChange={e => setRecForm(f => ({ ...f, student_id: e.target.value }))}
                        disabled={!recForm.course_id || courseEnrollmentsLoading}
                        required
                      >
                        <option value="">
                          {!recForm.course_id
                            ? t('record.selectCourseFirst')
                            : courseEnrollmentsLoading
                            ? t('record.loadingStudents')
                            : courseStudents.length === 0
                            ? t('record.noEnrolledStudents')
                            : t('record.selectStudent')}
                        </option>
                        {courseStudents.map((e: any) => {
                          const name = studentNameMap[e.student_id];
                          // Show name + short ID suffix to disambiguate students with similar names
                          const label = name
                            ? `${name}  (#${e.student_id.slice(-4)})`
                            : `Student #${e.student_id.slice(-8)}`;
                          return (
                            <option key={e.student_id} value={e.student_id}>{label}</option>
                          );
                        })}
                      </select>

                      {/* Student context row — reuses already-loaded studentScores */}
                      {selScore && (
                        <div className="mt-1.5 flex items-center gap-3 text-[11px] text-gray-500 bg-gray-50 rounded-lg px-3 py-1.5">
                          <span>{t('record.currentScore')}</span>
                          <span className={`font-bold px-1.5 py-0.5 rounded-full ${SCORE_BADGE[selScore.best?.classification ?? 'average'] ?? ''}`}>
                            {selScore.avg} — {SCORE_LABEL[selScore.best?.classification ?? 'average'] ?? selScore.best?.classification}
                          </span>
                          {selScore.best?.classification === 'needs_attention' && (
                            <span className="text-red-500 font-semibold">{t('record.atRisk')}</span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 3 — Lesson Date + Attendance */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{t('record.lessonDate')} <span className="text-red-400">*</span></label>
                        <input
                          type="date"
                          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                          value={recForm.lesson_date}
                          onChange={e => setRecForm(f => ({ ...f, lesson_date: e.target.value }))}
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{t('common.attendance')} <span className="text-red-400">*</span></label>
                        <select
                          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                          value={recForm.attendance_status}
                          onChange={e => setRecForm(f => ({ ...f, attendance_status: e.target.value }))}
                        >
                          {['present', 'absent', 'late', 'excused'].map(s => (
                            <option key={s} value={s}>{t(`att.${s}`)}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* 4 — Grade */}
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('record.gradeLabel')}</label>
                      <input
                        type="number" min="0" max="100" step="0.1"
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        placeholder={t('record.gradePlaceholder')}
                        value={recForm.grade_value}
                        onChange={e => setRecForm(f => ({ ...f, grade_value: e.target.value }))}
                      />
                    </div>

                    {/* 5 — Feedback */}
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">{t('record.teacherFeedback')}</label>
                      <textarea
                        rows={3}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                        placeholder={t('record.feedbackPlaceholder')}
                        value={recForm.teacher_feedback}
                        onChange={e => setRecForm(f => ({ ...f, teacher_feedback: e.target.value }))}
                      />
                    </div>

                    {/* 6 — Submit */}
                    <button
                      type="submit"
                      disabled={recLoading || !recForm.course_id || !recForm.student_id}
                      className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg transition"
                    >
                      {recLoading
                        ? t('common.saving')
                        : selName
                        ? `${t('record.saveLesson')} — ${selName}`
                        : t('record.saveLesson')}
                    </button>
                  </form>
                </div>

                {/* ── AI Alerts (context-aware) ──────────────────────────── */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-1">
                    <h2 className="font-bold text-gray-800 text-sm truncate">{alertTitle}</h2>
                    <button onClick={loadAlerts} className="text-xs text-blue-600 hover:underline flex-shrink-0 ml-2">{t('common.refresh')}</button>
                  </div>
                  {(recForm.student_id || recForm.course_id) && aiAlerts.length > contextAlerts.length && (
                    <p className="text-[11px] text-gray-400 mb-3">
                      Showing {contextAlerts.length} of {aiAlerts.length} alerts for this context.{' '}
                      <button
                        type="button"
                        onClick={() => setRecForm(f => ({ ...f, student_id: '', course_id: '' }))}
                        className="text-blue-500 hover:underline"
                      >
                        Show all
                      </button>
                    </p>
                  )}
                  {!recForm.student_id && !recForm.course_id && (
                    <p className="text-[11px] text-gray-400 mb-3">Select a course or student to see relevant alerts.</p>
                  )}
                  {alertsLoading ? (
                    <div className="flex justify-center py-8">
                      <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : contextAlerts.length === 0 ? (
                    <p className="text-gray-400 text-xs text-center py-8">
                      {aiAlerts.length > 0 ? 'No alerts for this selection.' : 'No AI alerts at this time.'}
                    </p>
                  ) : (
                    <div className="space-y-3 max-h-[420px] overflow-y-auto">
                      {contextAlerts.map((a: any) => (
                        <div key={a.id} className={`p-3 rounded-xl border text-xs ${ALERT_COLOR[a.alert_level] ?? ALERT_COLOR.info}`}>
                          <div className="flex items-center gap-1.5 font-semibold mb-1">
                            <span>{ALERT_ICON[a.alert_level] ?? 'ℹ️'}</span>
                            <span className="uppercase tracking-wide">{a.alert_level}</span>
                            <span className="ml-auto text-[10px] opacity-60">
                              {new Date(a.created_at).toLocaleDateString()}
                            </span>
                          </div>
                          <p className="leading-relaxed">{a.message}</p>
                          {a.recommendation && <p className="mt-1 opacity-70 italic">{a.recommendation}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {tab === 'updates' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-gray-800 text-sm">{t('dash.recentActivity')}</h2>
                <button onClick={loadUpdates} className="text-xs text-blue-600 hover:underline">{t('common.refresh')}</button>
              </div>
              {updatesLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : updates.length === 0 ? (
                <EmptyState icon="🔔" title={t('dash.recentActivity')} />
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('updates.timestamp'), t('updates.type'), t('updates.description'), t('admin.colCourse'), t('courseDetail.colStudent')].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold py-2 px-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {updates.map((u: any, i: number) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="py-2 px-4 text-gray-500 whitespace-nowrap">
                            {u.timestamp ? new Date(u.timestamp).toLocaleString() : '—'}
                          </td>
                          <td className="py-2 px-4">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${UPDATE_BADGE[u.type] ?? 'bg-gray-100 text-gray-600'}`}>
                              {u.type?.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="py-2 px-4 text-gray-700 max-w-xs truncate">{formatActivityDescription(u.description, t)}</td>
                          <td className="py-2 px-4 text-gray-500 truncate max-w-[140px]">{u.course_name || '—'}</td>
                          <td className="py-2 px-4 text-gray-500 truncate max-w-[120px]">{u.student_name || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'requests' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-gray-800 text-sm">{t('teacher.pendingEnrollmentRequests')}</h2>
                <button onClick={loadPendingRequests} className="text-xs text-blue-600 hover:underline">{t('common.refresh')}</button>
              </div>
              {pendingLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : pendingRequests.length === 0 ? (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 text-center">
                  <p className="text-gray-400 text-sm">No pending enrollment requests.</p>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50">
                        {['Student', 'Email', 'Course', 'Requested', 'Actions'].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold py-2.5 px-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {pendingRequests.map((r: any) => {
                        const acting = pendingActing === r.enrollment_id;
                        return (
                          <tr key={r.enrollment_id} className="hover:bg-gray-50">
                            <td className="py-3 px-4 font-semibold text-gray-800">
                              <Link to={`/users/${r.student_id}/profile`} className="hover:underline">{r.student_name}</Link>
                            </td>
                            <td className="py-3 px-4 text-gray-500">{r.student_email ?? '—'}</td>
                            <td className="py-3 px-4 text-gray-700">{r.course_name}</td>
                            <td className="py-3 px-4 text-gray-400 whitespace-nowrap">
                              {r.requested_at ? new Date(r.requested_at).toLocaleDateString() : '—'}
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleApproveRequest(r.enrollment_id)}
                                  disabled={acting}
                                  className="px-2.5 py-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-[11px] font-semibold rounded-lg transition"
                                >
                                  {acting ? '…' : 'Approve'}
                                </button>
                                <button
                                  onClick={() => handleRejectRequest(r.enrollment_id)}
                                  disabled={acting}
                                  className="px-2.5 py-1 border border-red-300 hover:bg-red-50 disabled:opacity-50 text-red-600 text-[11px] font-semibold rounded-lg transition"
                                >
                                  {acting ? '…' : 'Reject'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Alerts */}
          {data?.alerts?.length > 0 && tab === 'students' && (
            <div className="mt-4 space-y-2">
              {data.alerts.map((a: any, i: number) => (
                <div key={i} className={`p-3 rounded-xl text-xs border ${
                  a.type === 'warning' ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-blue-50 border-blue-200 text-blue-800'
                }`}>
                  {a.course_name && <strong className="mr-1">[{a.course_name}]</strong>}
                  {a.message}
                </div>
              ))}
            </div>
          )}

          {/* Quick action modals */}
          {feedbackTarget && (
            <QuickFeedbackModal
              studentId={feedbackTarget.studentId}
              studentName={feedbackTarget.studentName}
              courseId={feedbackTarget.courseId}
              courses={courses.map((c: any) => ({ id: c.id, name: c.name }))}
              onClose={() => setFeedbackTarget(null)}
              onSaved={() => { setFeedbackTarget(null); loadEnrollmentsAndScores(); }}
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
          {messageTarget && (
            <SendMessageModal
              recipientId={messageTarget.studentId}
              recipientName={messageTarget.studentName}
              courseId={messageTarget.courseId}
              onClose={() => setMessageTarget(null)}
              onSent={() => setMessageTarget(null)}
            />
          )}
        </>
      )}
    </DashboardLayout>
  );
};
