import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CircularProgress } from '../components/widgets/CircularProgress';
import { WeeklySchedule, coursesToSlots } from '../components/widgets/WeeklySchedule';
import { ProgressBar, labelColor } from '../components/widgets/ProgressBar';
import { EmptyState } from '../components/widgets/EmptyState';
import { ErrorState } from '../components/widgets/ErrorState';
import { apiService } from '../services/apiService';
import { formatActivityDescription } from '../utils/enumLabels';

const PARENT_TAB_KEYS = ['schedule', 'courses', 'materials', 'progress', 'updates', 'insights'];

const VALID_TABS = new Set(PARENT_TAB_KEYS);

const UPDATE_BADGE: Record<string, string> = {
  ai_alert:      'bg-red-100 text-red-700',
  lesson_record: 'bg-green-100 text-green-700',
  enrollment:    'bg-blue-100 text-blue-700',
};

const SCORE_BADGE: Record<string, string> = {
  excellent:       'text-emerald-600',
  good:            'text-blue-600',
  average:         'text-orange-500',
  needs_attention: 'text-red-600',
};

const SENTIMENT_COLOR: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral:  'bg-gray-100 text-gray-600',
  negative: 'bg-red-100 text-red-700',
};

export const ParentDashboard: React.FC = () => {
  const { t } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initTab = searchParams.get('tab') ?? 'schedule';
  const [tab, setTab] = useState(VALID_TABS.has(initTab) ? initTab : 'schedule');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // -1 = "All Children" view; ≥0 = index into children[]
  const [selectedChild, setSelectedChild] = useState<number>(-1);
  const selectionInitialized = useRef(false);
  // Tracks loaded children count so the tab-sync effect can reset to overview
  const childrenCountRef = useRef(0);

  const [updates, setUpdates] = useState<any[]>([]);
  const [updatesLoading, setUpdatesLoading] = useState(false);
  const [aiInsights, setAiInsights] = useState<any>(null);
  const [predictions, setPredictions] = useState<any[]>([]);
  const [aiAlerts, setAiAlerts] = useState<any[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const [materials, setMaterials]             = useState<any[]>([]);
  const [materialsLoading, setMaterialsLoading] = useState(false);

  // Enriched per-child courses from /api/parent/courses
  const [parentCourses, setParentCourses] = useState<any[]>([]);

  // Available courses (for enrollment request UI)
  const [availableCourses, setAvailableCourses]   = useState<any[]>([]);
  const [enrollChildSel, setEnrollChildSel]       = useState<Record<string, string>>({});
  const [enrollingCourseId, setEnrollingCourseId] = useState<string | null>(null);
  const [enrollMsg, setEnrollMsg]                 = useState<Record<string, { ok: boolean; text: string }>>({});

  // Sync tab state when URL query param changes (sidebar navigation on same route).
  // When no ?tab= in URL (parent clicked "Dashboard"), reset to all-children overview.
  useEffect(() => {
    const urlTab = searchParams.get('tab') ?? '';
    setTab(VALID_TABS.has(urlTab) ? urlTab : 'schedule');
    if (!urlTab && childrenCountRef.current > 1) {
      // "Dashboard" clicked — return multi-child parent to all-children overview
      setSelectedChild(-1);
    }
  }, [searchParams]);

  const load = () => {
    setLoading(true);
    setError(null);
    apiService.getDashboard()
      .then(r => {
        setData(r.data);
        childrenCountRef.current = (r.data?.metrics?.children ?? []).length;
      })
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // Load available (public) courses once for enrollment request UI
  useEffect(() => {
    apiService.getCourses()
      .then(r => setAvailableCourses(r.data ?? []))
      .catch(() => {});
  }, []);

  // Load enriched parent courses (child_name + teacher_name per enrollment)
  useEffect(() => {
    apiService.getParentCourses()
      .then(r => setParentCourses(r.data ?? []))
      .catch(() => {});
  }, []);

  // Auto-select single child on first data load; default to "All Children" for multi-child
  useEffect(() => {
    if (!data || selectionInitialized.current) return;
    const kids: any[] = data?.metrics?.children ?? [];
    if (kids.length === 1) setSelectedChild(0);
    // If kids.length > 1, keep -1 (All Children)
    selectionInitialized.current = true;
  }, [data]);

  useEffect(() => {
    if (tab === 'updates') {
      setUpdatesLoading(true);
      apiService.getDashboardUpdates()
        .then(r => setUpdates(r.data.updates ?? []))
        .catch(() => {})
        .finally(() => setUpdatesLoading(false));
    }
  }, [tab]);

  useEffect(() => {
    const childId = selectedChild >= 0 ? children[selectedChild]?.id : undefined;
    if (tab === 'insights' && childId) {
      setInsightsLoading(true);
      setAiInsights(null);
      setPredictions([]);
      setAiAlerts([]);
      Promise.all([
        apiService.getStudentAIInsights(childId).then(r => setAiInsights(r.data ?? null)).catch(() => {}),
        apiService.getAllPredictions(childId).then(r => setPredictions(r.data ?? [])).catch(() => {}),
        apiService.getAIAlerts({ student_id: childId }).then(r => setAiAlerts(r.data ?? [])).catch(() => {}),
      ]).finally(() => setInsightsLoading(false));
    }
  }, [tab, selectedChild]);

  // Load materials — for specific child (materials tab) or all children (all-children view)
  useEffect(() => {
    if (!data) return;
    const kids: any[] = data?.metrics?.children ?? [];

    // Specific child: only load when materials tab is active
    if (selectedChild >= 0 && tab !== 'materials') return;

    const courseIds: string[] = selectedChild >= 0
      ? (kids[selectedChild]?.course_ids ?? [])
      : [...new Set(kids.flatMap((ch: any) => ch.course_ids ?? []))];

    if (courseIds.length === 0) { setMaterials([]); return; }

    const nameMap: Record<string, string> = Object.fromEntries(
      (data?.courses ?? []).map((c: any) => [c.id, c.name])
    );
    // Map course → child name (for all-children view)
    const childOfCourse: Record<string, string> = {};
    kids.forEach((ch: any) => {
      (ch.course_ids ?? []).forEach((cid: string) => {
        if (!childOfCourse[cid]) childOfCourse[cid] = ch.name;
      });
    });

    setMaterialsLoading(true);
    Promise.all(
      courseIds.map((cid: string) =>
        apiService.getMaterials(cid)
          .then((r: any) => (r.data ?? []).map((m: any) => ({
            ...m,
            _course_name: nameMap[cid] ?? cid,
            _child_name:  childOfCourse[cid] ?? (selectedChild >= 0 ? kids[selectedChild]?.name : ''),
          })))
          .catch(() => [])
      )
    )
      .then(results => setMaterials((results as any[][]).flat()))
      .finally(() => setMaterialsLoading(false));
  }, [tab, selectedChild, data]);

  const m = data?.metrics || {};
  const children: any[] = m.children || [];

  // All courses from active enrollments (used for schedule, materials)
  const allCourses: any[] = data?.courses || [];

  // Pending enrollment courses (from backend metrics)
  const pendingCourses: any[] = m.pending_courses ?? [];

  // All enrolled course IDs (active + pending) — used to exclude from browsableCourses
  const enrolledCourseIds = new Set([
    ...allCourses.map((c: any) => c.id),
    ...pendingCourses.map((c: any) => c.id),
    // Also pick up pending_course_ids from each child (cross-check)
    ...children.flatMap((ch: any) => ch.pending_course_ids ?? []),
  ]);
  const browsableCourses = availableCourses.filter((c: any) => !enrolledCourseIds.has(c.id));

  const handleAvailableEnroll = async (courseId: string) => {
    const childId = children.length === 1
      ? children[0].id
      : (enrollChildSel[courseId] || '');
    if (!childId) return;
    setEnrollingCourseId(courseId);
    try {
      await apiService.requestEnrollment(courseId, childId);
      setEnrollMsg(prev => ({ ...prev, [courseId]: { ok: true, text: t('courseDetail.enrollRequestSent') } }));
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to send request.';
      setEnrollMsg(prev => ({ ...prev, [courseId]: { ok: false, text: msg } }));
    } finally {
      setEnrollingCourseId(null);
    }
  };

  // When a specific child is selected, filter to that child's active courses only
  const selectedChildData = selectedChild >= 0 ? children[selectedChild] : null;
  const childCourseIds: Set<string> = selectedChild >= 0
    ? new Set<string>(children[selectedChild]?.course_ids ?? [])
    : new Set<string>();
  // For schedule / materials: keep using allCourses (from dashboard)
  const courses = selectedChild >= 0
    ? allCourses.filter((c: any) => childCourseIds.has(c.id))
    : allCourses;

  // For the Courses tab: use the enriched endpoint (child_name + teacher_name guaranteed)
  const selectedChildId: string | undefined = selectedChildData?.id;
  const tabCourses: any[] = selectedChild >= 0
    ? parentCourses.filter(
        (c: any) => c.child_id === selectedChildId && c.enrollment_status === 'active'
      )
    : parentCourses.filter((c: any) => c.enrollment_status === 'active');

  const tabPendingCourses: any[] = selectedChild >= 0
    ? parentCourses.filter(
        (c: any) => c.child_id === selectedChildId && c.enrollment_status === 'pending'
      )
    : parentCourses.filter((c: any) => c.enrollment_status === 'pending');

  const scheduleSlots = coursesToSlots(courses);

  // Overall progress = average of real performance scores for selected child
  const childScores: any[] = selectedChildData?.performance_scores ?? [];
  const overallProgress = childScores.length
    ? Math.round(childScores.reduce((a: number, s: any) => a + (s.score ?? 0), 0) / childScores.length)
    : 0;
  const scoreMap = Object.fromEntries(childScores.map((s: any) => [s.course_id, s]));

  // Build a course name map from allCourses for the All Children summary cards
  const courseNameMap: Record<string, string> = Object.fromEntries(
    allCourses.map((c: any) => [c.id, c.name])
  );

  // Build course → child name(s) map for multi-child context in the All Children view
  const courseChildMap: Record<string, string[]> = {};
  children.forEach((child: any) => {
    (child.course_ids ?? []).forEach((cid: string) => {
      if (!courseChildMap[cid]) courseChildMap[cid] = [];
      courseChildMap[cid].push(child.name);
    });
  });

  const showAllChildren = selectedChild === -1 && children.length > 0;
  const showTabs        = selectedChild >= 0;

  return (
    <DashboardLayout
      tabs={showTabs ? [
        { key: 'schedule',  label: t('tab.schedule')        },
        { key: 'courses',   label: t('tab.childrenCourses') },
        { key: 'materials', label: t('tab.materials')       },
        { key: 'progress',  label: t('tab.progress')        },
        { key: 'updates',   label: t('tab.recentUpdates')   },
        { key: 'insights',  label: t('tab.aiInsights')      },
      ] : []}
      activeTab={tab}
      onTabChange={setTab}
    >
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {/* ── Child selector ─────────────────────────────────────────── */}
          {children.length > 0 && (
            <div className="mb-5 flex items-center gap-3 flex-wrap">
              <span className="text-sm font-semibold text-gray-600">{t('parent.viewing')}</span>
              <div className="relative">
                <select
                  value={selectedChild}
                  onChange={e => setSelectedChild(Number(e.target.value))}
                  className="bg-white border border-gray-200 rounded-xl px-4 py-2 text-sm font-semibold text-gray-800 shadow-sm appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  {children.length > 1 && (
                    <option value={-1}>{t('parent.allChildren')}</option>
                  )}
                  {children.map((c: any, i: number) => (
                    <option key={c.id} value={i}>{c.name}</option>
                  ))}
                </select>
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">▼</span>
              </div>
              {selectedChild === -1 ? (
                <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1.5 rounded-full">
                  {children.length} {t('parent.allChildren').toLowerCase()}
                </span>
              ) : children[selectedChild] && (
                <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1.5 rounded-full">
                  {children[selectedChild].enrolled_count} {t('student.enrolledCourses').toLowerCase()}
                </span>
              )}
            </div>
          )}

          {children.length === 0 && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center text-gray-400 mb-6">
              <div className="text-5xl mb-3">👨‍👩‍👧</div>
              <p className="font-semibold text-gray-600">{t('parent.noChildrenLinked')}</p>
              <p className="text-sm mt-1">{t('parent.contactAdmin')}</p>
            </div>
          )}

          {/* ── ALL CHILDREN overview ───────────────────────────────────── */}
          {showAllChildren && (
            <div className="space-y-5">
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {children.map((child: any, idx: number) => {
                  const scores: any[] = child.performance_scores ?? [];
                  const avg = scores.length
                    ? Math.round(scores.reduce((a: number, s: any) => a + (s.score ?? 0), 0) / scores.length)
                    : 0;
                  return (
                    <div key={child.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                      {/* Header */}
                      <div className="flex items-start justify-between mb-4">
                        <div>
                          <Link to={`/users/${child.id}/profile`} className="font-bold text-gray-800 text-sm hover:underline">{child.name}</Link>
                          <p className="text-xs text-gray-400">{child.enrolled_count} {t('student.enrolledCourses').toLowerCase()}</p>
                        </div>
                        <button
                          onClick={() => setSelectedChild(idx)}
                          className="text-[10px] font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-lg transition"
                        >
                          {t('parent.viewDetails')}
                        </button>
                      </div>

                      {/* Average score ring */}
                      <div className="flex items-center gap-4 mb-4">
                        <CircularProgress percent={avg} size={70} />
                        <div>
                          <p className="text-xs text-gray-500">{t('parent.avgPerformance')}</p>
                          <p className="text-lg font-black text-gray-900">{avg > 0 ? `${avg}%` : '—'}</p>
                        </div>
                      </div>

                      {/* Per-course scores */}
                      {scores.length > 0 ? (
                        <div className="space-y-2">
                          {scores.slice(0, 3).map((ps: any) => (
                            <div key={ps.course_id}>
                              <div className="flex justify-between text-[11px] mb-0.5">
                                <span className="text-gray-600 truncate pr-2 flex-1">
                                  {courseNameMap[ps.course_id] ?? ps.course_id}
                                </span>
                                <span className={`font-semibold flex-shrink-0 ${SCORE_BADGE[ps.classification] ?? 'text-gray-500'}`}>
                                  {ps.score != null ? `${ps.score.toFixed(0)}/100` : '—'}
                                </span>
                              </div>
                              {ps.score != null && (
                                <ProgressBar percent={Math.round(ps.score)} showLabel={false} height={4} />
                              )}
                            </div>
                          ))}
                          {scores.length > 3 && (
                            <p className="text-[10px] text-gray-400 text-center pt-1">
                              +{scores.length - 3} more course(s)
                            </p>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-gray-400">{t('progress.noPerformance')}</p>
                      )}

                      {/* Latest feedback */}
                      {child.latest_feedback && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <p className="text-[10px] font-semibold text-gray-500 mb-1">{t('parent.latestFeedback')}</p>
                          <div className="flex items-start gap-2">
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${SENTIMENT_COLOR[child.latest_feedback.sentiment] ?? 'bg-gray-100 text-gray-600'}`}>
                              {child.latest_feedback.sentiment}
                            </span>
                            <p className="text-[10px] text-gray-600 line-clamp-2">{child.latest_feedback.content}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* All courses across all children */}
              {(allCourses.length > 0 || pendingCourses.length > 0) && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-bold text-gray-800 text-sm">{t('tab.childrenCourses')}</h2>
                    <span className="text-xs text-gray-400">
                      {allCourses.length} {t('student.enrolledCourses').toLowerCase()}
                      {pendingCourses.length > 0 && ` · ${pendingCourses.length} pending`}
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100">
                          {[t('admin.colCourse'), t('courseDetail.colStudent'), t('courseDetail.teacher'), t('parent.colActions')].map(h => (
                            <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-6">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {allCourses.map((c: any, idx: number) => {
                          const childNames = courseChildMap[c.id] ?? [];
                          return (
                            <tr key={c.id} className="hover:bg-gray-50">
                              <td className="py-3 pr-6">
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 ${
                                    ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                                  }`}>{c.code.slice(0, 3)}</div>
                                  <div>
                                    <p className="font-semibold text-gray-800">{c.name}</p>
                                    <p className="text-xs text-gray-400 font-mono">{c.code}</p>
                                  </div>
                                </div>
                              </td>
                              <td className="py-3 pr-6">
                                <div className="flex flex-wrap gap-1">
                                  {childNames.map((n: string) => (
                                    <span key={n} className="text-[10px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">{n}</span>
                                  ))}
                                </div>
                              </td>
                              <td className="py-3 pr-6 text-xs text-gray-500">
                                {c.teacher_name ?? <span className="text-gray-300">—</span>}
                              </td>
                              <td className="py-3 pr-6">
                                <button
                                  onClick={() => navigate(`/courses/${c.id}`)}
                                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs px-3 py-1.5 rounded-lg transition"
                                >
                                  {t('parent.viewDetailBtn')}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                        {/* Pending enrollment courses */}
                        {pendingCourses.map((c: any, idx: number) => {
                          const pendingChildNames = children
                            .filter((ch: any) => (ch.pending_course_ids ?? []).includes(c.id))
                            .map((ch: any) => ch.name);
                          return (
                            <tr key={`pending-${c.id}`} className="hover:bg-yellow-50/40 bg-yellow-50/20">
                              <td className="py-3 pr-6">
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 opacity-70 ${
                                    ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][(allCourses.length + idx) % 4]
                                  }`}>{(c.code || '?').slice(0, 3)}</div>
                                  <div>
                                    <p className="font-semibold text-gray-700">{c.name}</p>
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">
                                      ⏳ Pending Approval
                                    </span>
                                  </div>
                                </div>
                              </td>
                              <td className="py-3 pr-6">
                                <div className="flex flex-wrap gap-1">
                                  {pendingChildNames.map((n: string) => (
                                    <span key={n} className="text-[10px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">{n}</span>
                                  ))}
                                </div>
                              </td>
                              <td className="py-3 pr-6 text-xs text-gray-500">
                                {c.teacher_name ?? <span className="text-gray-300">—</span>}
                              </td>
                              <td className="py-3 pr-6">
                                <button
                                  onClick={() => navigate(`/courses/${c.id}`)}
                                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs px-3 py-1.5 rounded-lg transition"
                                >
                                  {t('parent.viewDetailBtn')}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Available courses for enrollment requests (all-children view) */}
              {browsableCourses.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-bold text-gray-800 text-sm">{t('parent.availableCourses')}</h2>
                    <span className="text-xs text-gray-400">{browsableCourses.length} {t('parent.availableCoursesCount')}</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100">
                          {[t('admin.colCourse'), t('courseDetail.teacher'), t('parent.requestFor')].map(h => (
                            <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-6">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {browsableCourses.map((c: any, idx: number) => {
                          const msg = enrollMsg[c.id];
                          return (
                            <tr key={c.id} className="hover:bg-gray-50">
                              <td className="py-3 pr-6">
                                <div className="flex items-center gap-3">
                                  <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 ${
                                    ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                                  }`}>{(c.code || '?').slice(0, 3)}</div>
                                  <div>
                                    <p className="font-semibold text-gray-800">{c.name}</p>
                                    <p className="text-xs text-gray-400 font-mono">{c.code}</p>
                                    {c.schedule?.days?.length > 0 && (
                                      <p className="text-[10px] text-gray-400 mt-0.5">
                                        {c.schedule.days.map((d: string) => d.slice(0, 3)).join(', ')}
                                        {c.schedule.start_time ? ` · ${c.schedule.start_time}` : ''}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </td>
                              <td className="py-3 pr-6 text-xs text-gray-500">{c.teacher_name ?? <span className="text-gray-300">—</span>}</td>
                              <td className="py-3 pr-6">
                                {msg ? (
                                  <span className={`text-xs font-semibold ${msg.ok ? 'text-green-600' : 'text-red-500'}`}>
                                    {msg.ok ? '✓ ' : '✗ '}{msg.text}
                                  </span>
                                ) : (
                                  <div className="flex items-center gap-2 flex-wrap">
                                    {children.length > 1 && (
                                      <select
                                        value={enrollChildSel[c.id] || ''}
                                        onChange={e => setEnrollChildSel(prev => ({ ...prev, [c.id]: e.target.value }))}
                                        className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                                      >
                                        <option value="">{t('parent.selectChild')}</option>
                                        {children.map((ch: any) => (
                                          <option key={ch.id} value={ch.id}>{ch.name}</option>
                                        ))}
                                      </select>
                                    )}
                                    <button
                                      disabled={enrollingCourseId === c.id || (children.length > 1 && !enrollChildSel[c.id])}
                                      onClick={() => handleAvailableEnroll(c.id)}
                                      className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition whitespace-nowrap"
                                    >
                                      {enrollingCourseId === c.id
                                        ? t('courseDetail.sending')
                                        : children.length === 1
                                          ? `${t('parent.requestFor')} ${children[0].name}`
                                          : t('courseDetail.requestCourseForChild')}
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* All Materials across all children */}
              {materials.length > 0 && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">{t('parent.allMaterials')}</h2>
                  {materialsLoading ? (
                    <div className="flex justify-center py-6">
                      <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-100">
                            {[t('materials.colMaterial'), t('parent.child'), t('materials.colCourse'), t('materials.colDate'), t('materials.colAction')].map(h => (
                              <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-4">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {materials.map((mat: any) => {
                            const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';
                            const raw  = mat.link_url ?? mat.file_url;
                            const href = raw?.startsWith('/') ? `${API_URL}${raw}` : raw;
                            return (
                              <tr key={mat.id} className="hover:bg-gray-50">
                                <td className="py-3 pr-4">
                                  <div className="flex items-center gap-2">
                                    <span className="text-base flex-shrink-0">{mat.file_url ? '📄' : '🔗'}</span>
                                    <span className="font-semibold text-gray-800 truncate max-w-[160px] text-sm">{mat.title}</span>
                                  </div>
                                </td>
                                <td className="py-3 pr-4">
                                  <span className="text-[10px] font-semibold px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">{mat._child_name || '—'}</span>
                                </td>
                                <td className="py-3 pr-4 text-xs text-gray-500">{mat._course_name}</td>
                                <td className="py-3 pr-4 text-xs text-gray-400 whitespace-nowrap">
                                  {mat.created_at ? new Date(mat.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}
                                </td>
                                <td className="py-3 pr-4">
                                  {href ? (
                                    <a href={href} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">
                                      {t('materials.open')}
                                    </a>
                                  ) : <span className="text-xs text-gray-300">—</span>}
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

              {/* Shared alerts for all children */}
              {data?.alerts?.length > 0 && (
                <div className="space-y-2">
                  {data.alerts.map((a: any, i: number) => (
                    <div key={i} className={`p-3 rounded-xl text-xs border flex items-start gap-2 ${
                      a.type === 'warning' ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-green-50 border-green-200 text-green-800'
                    }`}>
                      <span>{a.type === 'warning' ? '⚠️' : '✅'}</span>
                      <span>{a.message}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Recent Updates preview (always available in All Children) */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="font-bold text-gray-800 text-sm">{t('parent.recentUpdates')}</h2>
                  <button
                    onClick={() => { setSelectedChild(0); setTab('updates'); }}
                    className="text-[10px] text-blue-600 hover:underline"
                  >
                    {t('parent.viewAll')}
                  </button>
                </div>
                {updatesLoading ? (
                  <div className="flex justify-center py-6">
                    <div className="w-6 h-6 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : updates.length === 0 ? (
                  <p className="text-xs text-gray-400 text-center py-4">{t('parent.noUpdates')}</p>
                ) : (
                  <div className="space-y-2">
                    {updates.slice(0, 5).map((u: any, i: number) => (
                      <div key={i} className="flex items-start gap-3 text-xs">
                        <span className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold ${UPDATE_BADGE[u.type] ?? 'bg-gray-100 text-gray-600'}`}>
                          {u.type?.replace('_', ' ') ?? '—'}
                        </span>
                        <span className="text-gray-700 truncate flex-1">{formatActivityDescription(u.description, t)}</span>
                        {u.student && <span className="text-gray-400 flex-shrink-0">{u.student}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── SPECIFIC CHILD tabbed view ─────────────────────────────── */}
          {showTabs && (
            <>
              {tab === 'schedule' && (
                <div className="grid lg:grid-cols-3 gap-6">
                  {/* Schedule */}
                  <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-bold text-gray-800 text-sm">
                        {selectedChildData ? `${selectedChildData.name}'s Schedule` : 'Schedule'}
                      </h2>
                      <span className="text-xs text-gray-400">{t('dash.thisWeek')}</span>
                    </div>
                    {scheduleSlots.length > 0 ? (
                      <>
                        <WeeklySchedule
                          slots={scheduleSlots}
                          onSlotClick={slot => slot.id && navigate(`/courses/${slot.id}`)}
                        />
                        <p className="text-[11px] text-gray-400 mt-2">{t('dash.clickToOpen')}</p>
                      </>
                    ) : (
                      <EmptyState icon="📅" title={t('parent.noSchedule')} />
                    )}
                    {scheduleSlots.length > 0 && (
                      <button onClick={() => navigate('/courses')} className="text-blue-600 text-xs hover:underline mt-2">{t('parent.viewFullSchedule')}</button>
                    )}
                  </div>

                  {/* Progress chart */}
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col items-center">
                    <h2 className="font-bold text-gray-800 text-sm mb-4 self-start">{t('dash.myProgress')}</h2>
                    <CircularProgress percent={overallProgress} size={150} />

                    {/* Course progress mini bars */}
                    {courses.length > 0 && (
                      <div className="mt-4 w-full space-y-2">
                        {courses.slice(0, 3).map((c: any) => {
                          const ps = scoreMap[c.id];
                          const score = ps?.score ?? null;
                          const cls = ps?.classification ?? '';
                          return (
                            <div key={c.id} className="flex items-center gap-2 text-xs">
                              <div className={`w-2 h-2 rounded-full ${
                                cls === 'excellent' ? 'bg-emerald-400'
                                : cls === 'good' ? 'bg-blue-400'
                                : cls === 'needs_attention' ? 'bg-red-400'
                                : 'bg-orange-400'
                              }`} />
                              <span className="flex-1 truncate text-gray-600">{c.name.split(' ')[0]}</span>
                              <span className={`font-semibold ${SCORE_BADGE[cls] ?? 'text-gray-500'}`}>
                                {score != null ? `${score.toFixed(0)}/100` : '—'}
                              </span>
                              <span className="text-gray-400">›</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Alerts */}
                  {data?.alerts?.length > 0 && (
                    <div className="lg:col-span-3 space-y-2">
                      {data.alerts.map((a: any, i: number) => (
                        <div key={i} className={`p-3 rounded-xl text-xs border flex items-start gap-2 ${
                          a.type === 'warning' ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-green-50 border-green-200 text-green-800'
                        }`}>
                          <span>{a.type === 'warning' ? '⚠️' : '✅'}</span>
                          <span>{a.message}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'courses' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-bold text-gray-800 text-sm">
                      {selectedChildData ? `${selectedChildData.name}'s Courses` : 'Courses'}
                    </h2>
                    <span className="text-xs text-gray-400">{tabCourses.length} {t('student.enrolledCourses').toLowerCase()}</span>
                  </div>

                  {tabCourses.length === 0 ? (
                    <p className="text-gray-400 text-center py-12">{t('parent.noCoursesDisplay')}</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100">
                          {[t('admin.colCourse'), t('courseDetail.teacher'), t('student.colProgress'), t('parent.colActions')].map(h => (
                            <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-6">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {tabCourses.map((c: any, idx: number) => {
                          const ps = scoreMap[c.id];
                          const score = ps?.score ?? null;
                          const cls   = ps?.classification ?? '';
                          const scheduleDays: string[] = c.schedule?.days ?? [];
                          return (
                            <tr key={c.id} className="hover:bg-gray-50">
                              <td className="py-3 pr-6">
                                <div className="flex items-center gap-3">
                                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                                    ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                                  }`}>{c.code.slice(0, 3)}</div>
                                  <div>
                                    <p className="font-semibold text-gray-800">{c.name}</p>
                                    <p className="text-xs text-gray-400 font-mono">{c.code}</p>
                                    {scheduleDays.length > 0 && (
                                      <p className="text-[10px] text-gray-400 mt-0.5">
                                        {scheduleDays.map((d: string) => d.slice(0, 3)).join(', ')}
                                        {c.schedule?.start_time ? ` · ${c.schedule.start_time}` : ''}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </td>
                              <td className="py-3 pr-6 text-gray-600 text-xs">
                                {c.teacher_name ?? <span className="text-gray-300">—</span>}
                              </td>
                              <td className="py-3 pr-6 w-44">
                                {score != null ? (
                                  <>
                                    <span className={`text-xs font-semibold mb-1 inline-block ${SCORE_BADGE[cls] ?? 'text-gray-500'}`}>
                                      {score.toFixed(0)}/100 · {cls.replace('_', ' ')}
                                    </span>
                                    <ProgressBar percent={Math.round(score)} showLabel={false} height={5} />
                                  </>
                                ) : (
                                  <span className="text-xs text-gray-400">{t('parent.noCourseData')}</span>
                                )}
                              </td>
                              <td className="py-3 pr-6">
                                <button
                                  onClick={() => navigate(`/courses/${c.id}`)}
                                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs px-3 py-1.5 rounded-lg transition flex items-center gap-1"
                                >
                                  {t('parent.viewDetailBtn')}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}

                  {/* Pending courses for this child */}
                  {tabPendingCourses.length > 0 && (
                    <div className="mt-6 pt-5 border-t border-gray-100">
                      <h3 className="font-bold text-gray-700 text-xs uppercase tracking-wide mb-3">⏳ Pending Approval</h3>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-100">
                            {[t('admin.colCourse'), t('courseDetail.teacher'), t('parent.colActions')].map(h => (
                              <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-6">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {tabPendingCourses.map((c: any, idx: number) => (
                            <tr key={c.id} className="hover:bg-yellow-50/40">
                              <td className="py-3 pr-6">
                                <div className="flex items-center gap-3">
                                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                                    ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                                  }`}>{(c.code || '?').slice(0, 3)}</div>
                                  <div>
                                    <p className="font-semibold text-gray-800">{c.name}</p>
                                    <p className="text-xs text-gray-400 font-mono">{c.code}</p>
                                  </div>
                                  <span className="ml-2 text-[10px] font-semibold bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full whitespace-nowrap">⏳ Pending</span>
                                </div>
                              </td>
                              <td className="py-3 pr-6 text-gray-600 text-xs">
                                {c.teacher_name ?? <span className="text-gray-300">—</span>}
                              </td>
                              <td className="py-3 pr-6">
                                <button
                                  onClick={() => navigate(`/courses/${c.id}`)}
                                  className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs px-3 py-1.5 rounded-lg transition flex items-center gap-1"
                                >
                                  {t('parent.viewDetailBtn')}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Available courses for this child */}
                  {browsableCourses.length > 0 && (
                    <div className="mt-6 pt-5 border-t border-gray-100">
                      <h3 className="font-bold text-gray-700 text-xs uppercase tracking-wide mb-3">{t('parent.availableCourses')}</h3>
                      <div className="space-y-2">
                        {browsableCourses.map((c: any, idx: number) => {
                          const msg = enrollMsg[c.id];
                          return (
                            <div key={c.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl hover:bg-gray-50">
                              <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0 ${
                                ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                              }`}>{(c.code || '?').slice(0, 3)}</div>
                              <div className="flex-1 min-w-0">
                                <p className="font-semibold text-gray-800 text-sm truncate">{c.name}</p>
                                <p className="text-xs text-gray-400">{c.teacher_name ?? ''}{c.code ? ` · ${c.code}` : ''}</p>
                              </div>
                              {msg ? (
                                <span className={`text-xs font-semibold flex-shrink-0 ${msg.ok ? 'text-green-600' : 'text-red-500'}`}>
                                  {msg.ok ? '✓ ' : '✗ '}{msg.text}
                                </span>
                              ) : (
                                <button
                                  disabled={enrollingCourseId === c.id}
                                  onClick={() => {
                                    setEnrollChildSel(prev => ({ ...prev, [c.id]: selectedChildData?.id || '' }));
                                    handleAvailableEnroll(c.id);
                                  }}
                                  className="flex-shrink-0 text-xs font-semibold px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition whitespace-nowrap"
                                >
                                  {enrollingCourseId === c.id
                                    ? t('courseDetail.sending')
                                    : `${t('courseDetail.requestCourseForChild')} ${selectedChildData?.name ?? ''}`}
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

              {tab === 'progress' && (
                <div className="grid lg:grid-cols-2 gap-6">
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col items-center">
                    <h2 className="font-bold text-gray-800 text-sm mb-4 self-start">
                      {selectedChildData ? `${selectedChildData.name} — ${t('tab.progress')}` : t('parent.overallProgress')}
                    </h2>
                    <CircularProgress percent={overallProgress} size={160} />
                  </div>
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <h2 className="font-bold text-gray-800 text-sm mb-4">{t('parent.courseBreakdown')}</h2>
                    {courses.length === 0 ? (
                      <p className="text-gray-400 text-sm text-center py-8">{t('parent.noCoursesEnrolled')}</p>
                    ) : (
                      <div className="space-y-4">
                        {courses.map((c: any) => {
                          const ps = scoreMap[c.id];
                          const score = ps?.score ?? null;
                          const p = score != null ? Math.round(score) : 0;
                          return (
                            <div key={c.id}>
                              <div className="flex justify-between text-xs mb-1.5">
                                <span className="font-semibold text-gray-700 truncate pr-2">{c.name}</span>
                                {score != null ? (
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${labelColor(p)}`}>{p}%</span>
                                ) : (
                                  <span className="text-gray-400 text-[10px]">No data</span>
                                )}
                              </div>
                              {score != null && <ProgressBar percent={p} showLabel={false} height={6} />}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {tab === 'insights' && (
                <div className="space-y-5">
                  {insightsLoading ? (
                    <div className="flex justify-center py-16">
                      <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : !selectedChildData ? (
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center text-gray-400">
                      {t('parent.selectChildInsights')}
                    </div>
                  ) : (
                    <>
                      {/* AI Student Insight */}
                      {aiInsights ? (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                          <h2 className="font-bold text-gray-800 text-sm mb-3">
                            🤖 AI Summary — {selectedChildData?.name}
                          </h2>
                          {aiInsights.summary && (
                            <p className="text-sm text-gray-700 bg-blue-50 rounded-xl px-4 py-3 border border-blue-100 mb-3">
                              {aiInsights.summary}
                            </p>
                          )}
                          {aiInsights.insights && aiInsights.insights.length > 0 && (
                            <ul className="space-y-1.5">
                              {aiInsights.insights.map((insight: string, i: number) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-gray-600">
                                  <span className="text-blue-400 mt-0.5">•</span>
                                  <span>{insight}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ) : (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 text-center text-gray-400 text-sm">
                          {t('parent.noAiSummary')}
                        </div>
                      )}

                      {/* Predictions per course */}
                      {predictions.length > 0 && (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                          <h2 className="font-bold text-gray-800 text-sm mb-3">📈 {t('parent.performancePredictions')}</h2>
                          <div className="space-y-2">
                            {predictions.map((p: any) => {
                              const riskColor: Record<string, string> = {
                                low:    'bg-green-100 text-green-700',
                                medium: 'bg-yellow-100 text-yellow-700',
                                high:   'bg-red-100 text-red-700',
                              };
                              const predColor: Record<string, string> = {
                                likely_improving:    'text-emerald-600',
                                likely_stable:       'text-blue-600',
                                at_risk:             'text-orange-600',
                                needs_intervention:  'text-red-600',
                              };
                              return (
                                <div key={p.course_id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                                  <div className="flex-1 min-w-0">
                                    <p className="text-xs font-semibold text-gray-800 truncate">{p.course_name ?? p.course_id}</p>
                                    <p className={`text-[11px] font-medium capitalize ${predColor[p.prediction_label] ?? 'text-gray-500'}`}>
                                      {p.prediction_label?.replace(/_/g, ' ') ?? '—'}
                                    </p>
                                  </div>
                                  {p.risk_level && (
                                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${riskColor[p.risk_level] ?? 'bg-gray-100 text-gray-600'}`}>
                                      {p.risk_level} {t('parent.risk')}
                                    </span>
                                  )}
                                  {p.reason_summary && (
                                    <p className="text-[10px] text-gray-400 max-w-xs hidden sm:block truncate">{p.reason_summary}</p>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* AI Alerts */}
                      {aiAlerts.length > 0 && (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                          <h2 className="font-bold text-gray-800 text-sm mb-3">⚠️ AI Alerts</h2>
                          <div className="space-y-2">
                            {aiAlerts.map((alert: any) => (
                              <div key={alert.id} className={`flex items-start gap-3 p-3 rounded-xl border text-xs ${
                                alert.severity === 'high'   ? 'bg-red-50 border-red-200'    :
                                alert.severity === 'medium' ? 'bg-yellow-50 border-yellow-200' :
                                                              'bg-gray-50 border-gray-200'
                              }`}>
                                <span className="text-base mt-0.5">
                                  {alert.severity === 'high' ? '🔴' : alert.severity === 'medium' ? '🟡' : '🔵'}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="font-semibold text-gray-800">{alert.title ?? alert.alert_type?.replace(/_/g, ' ')}</p>
                                  {alert.message && <p className="text-gray-600 mt-0.5">{alert.message}</p>}
                                  {alert.course_name && (
                                    <p className="text-gray-400 mt-0.5 text-[10px]">Course: {alert.course_name}</p>
                                  )}
                                </div>
                                {!alert.acknowledged_at && (
                                  <button
                                    disabled={acknowledgingId === alert.id}
                                    onClick={async () => {
                                      setAcknowledgingId(alert.id);
                                      try {
                                        await apiService.acknowledgeAlert(alert.id);
                                        setAiAlerts(prev => prev.map(a =>
                                          a.id === alert.id ? { ...a, acknowledged_at: new Date().toISOString() } : a
                                        ));
                                      } catch {}
                                      setAcknowledgingId(null);
                                    }}
                                    className="text-[10px] font-semibold px-2.5 py-1 rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50 flex-shrink-0 transition"
                                  >
                                    {acknowledgingId === alert.id ? '…' : t('parent.acknowledge')}
                                  </button>
                                )}
                                {alert.acknowledged_at && (
                                  <span className="text-[10px] text-gray-400 flex-shrink-0">{t('parent.acknowledged')}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {!aiInsights && predictions.length === 0 && aiAlerts.length === 0 && (
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center text-gray-400">
                          <div className="text-4xl mb-3">🤖</div>
                          <p className="font-semibold text-gray-600 text-sm">{t('parent.noAiInsights')}</p>
                          <p className="text-xs mt-1">{t('parent.noAiInsightsDesc')}</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {tab === 'materials' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">
                    {selectedChildData ? `${selectedChildData.name} — ${t('tab.materials')}` : t('tab.materials')}
                  </h2>
                  {materialsLoading ? (
                    <div className="flex justify-center py-12">
                      <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : materials.length === 0 ? (
                    <EmptyState icon="📎" title={t('materials.noMaterials')} description={t('materials.hint')} />
                  ) : (
                    /* Group by course for clarity */
                    <div className="space-y-5">
                      {Object.entries(
                        materials.reduce((acc: Record<string, any[]>, m: any) => {
                          const key = m._course_name || '—';
                          if (!acc[key]) acc[key] = [];
                          acc[key].push(m);
                          return acc;
                        }, {})
                      ).map(([courseName, mats]) => (
                        <div key={courseName}>
                          <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
                            <span className="text-base">📚</span>{courseName}
                          </p>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b border-gray-100">
                                  {[t('materials.colMaterial'), t('materials.colDate'), t('materials.colAction')].map(h => (
                                    <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-2 pr-6">{h}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-50">
                                {(mats as any[]).map((mat: any) => {
                                  const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://127.0.0.1:8000';
                                  const raw  = mat.link_url ?? mat.file_url;
                                  const href = raw?.startsWith('/') ? `${API_URL}${raw}` : raw;
                                  return (
                                    <tr key={mat.id} className="hover:bg-gray-50">
                                      <td className="py-2.5 pr-6">
                                        <div className="flex items-center gap-2">
                                          <span className="text-base flex-shrink-0">{mat.file_url ? '📄' : '🔗'}</span>
                                          <span className="font-semibold text-gray-800 truncate max-w-[200px] text-sm">{mat.title}</span>
                                        </div>
                                      </td>
                                      <td className="py-2.5 pr-6 text-xs text-gray-400 whitespace-nowrap">
                                        {mat.created_at ? new Date(mat.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}
                                      </td>
                                      <td className="py-2.5 pr-6">
                                        {href ? (
                                          <a href={href} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">
                                            {t('materials.open')}
                                          </a>
                                        ) : <span className="text-xs text-gray-300">—</span>}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'updates' && (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">{t('parent.recentUpdates')}</h2>
                  {updatesLoading ? (
                    <div className="flex justify-center py-12">
                      <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                  ) : updates.length === 0 ? (
                    <EmptyState icon="🔔" title={t('parent.noUpdates')} />
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-gray-100">
                            {[t('updates.timestamp'), t('updates.type'), t('updates.description'), t('admin.colCourse'), t('courseDetail.colStudent')].map(h => (
                              <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                          {updates.map((u: any, i: number) => (
                            <tr key={i} className="hover:bg-gray-50 transition">
                              <td className="py-2.5 pr-4 text-gray-500 whitespace-nowrap">
                                {u.timestamp ? new Date(u.timestamp).toLocaleString() : '—'}
                              </td>
                              <td className="py-2.5 pr-4">
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${UPDATE_BADGE[u.type] ?? 'bg-gray-100 text-gray-600'}`}>
                                  {u.type?.replace('_', ' ') ?? '—'}
                                </span>
                              </td>
                              <td className="py-2.5 pr-4 text-gray-700 max-w-xs truncate">{formatActivityDescription(u.description, t)}</td>
                              <td className="py-2.5 pr-4 text-gray-500 truncate">{u.course ?? '—'}</td>
                              <td className="py-2.5 pr-4 text-gray-500 truncate">{u.student ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </DashboardLayout>
  );
};
