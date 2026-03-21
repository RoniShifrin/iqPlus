import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CircularProgress } from '../components/widgets/CircularProgress';
import { WeeklySchedule, coursesToSlots } from '../components/widgets/WeeklySchedule';
import { ProgressBar, labelColor } from '../components/widgets/ProgressBar';
import { EmptyState } from '../components/widgets/EmptyState';
import { ErrorState } from '../components/widgets/ErrorState';
import { apiService } from '../services/apiService';
import { formatActivityDescription } from '../utils/enumLabels';
import { AIInsightsCard } from '../components/AIInsightsCard';

const VALID_TABS = new Set(['overview', 'schedule', 'courses', 'progress', 'history', 'updates']);

const UPDATE_BADGE: Record<string, string> = {
  ai_alert:      'bg-red-100 text-red-700',
  lesson_record: 'bg-green-100 text-green-700',
  enrollment:    'bg-blue-100 text-blue-700',
};

const ATT_COLOR: Record<string, string> = {
  present: 'bg-green-100 text-green-700',
  absent:  'bg-red-100 text-red-700',
  late:    'bg-yellow-100 text-yellow-700',
  excused: 'bg-gray-100 text-gray-600',
};

const SCORE_COLOR: Record<string, string> = {
  excellent:      'bg-green-100 text-green-700 border-green-200',
  good:           'bg-blue-100 text-blue-700 border-blue-200',
  average:        'bg-yellow-100 text-yellow-700 border-yellow-200',
  needs_attention: 'bg-red-100 text-red-700 border-red-200',
};
const SCORE_LABEL: Record<string, string> = {
  excellent:      'Excellent',
  good:           'Good',
  average:        'Average',
  needs_attention: 'Needs Attention',
};


export const StudentDashboard: React.FC = () => {
  const { user } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const initTab = searchParams.get('tab') ?? 'overview';
  const [tab, setTab] = useState(VALID_TABS.has(initTab) ? initTab : 'overview');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [histLoading, setHistLoading] = useState(false);
  const [scores, setScores] = useState<any[]>([]);
  const [scoresLoading, setScoresLoading] = useState(false);
  const [updates, setUpdates] = useState<any[]>([]);
  const [updatesLoading, setUpdatesLoading] = useState(false);
  const [convos, setConvos] = useState<any[]>([]);
  const [convosLoading, setConvosLoading] = useState(false);
  const [scheduleView, setScheduleView] = useState<'weekly' | 'monthly' | 'yearly'>('weekly');

  // Dashboard AI insights
  const [dashInsights, setDashInsights] = useState<string[]>([]);
  const [dashInsightsLoading, setDashInsightsLoading] = useState(false);

  const loadDashInsights = () => {
    setDashInsightsLoading(true);
    apiService.getDashboardInsights()
      .then(r => setDashInsights(r.data?.insights ?? []))
      .catch(() => {})
      .finally(() => setDashInsightsLoading(false));
  };

  // Sync tab state when URL query param changes (sidebar navigation on same route)
  useEffect(() => {
    const urlTab = searchParams.get('tab') ?? 'overview';
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

  useEffect(() => {
    load();
    const onVisible = () => { if (document.visibilityState === 'visible') load(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, []);

  useEffect(() => {
    if (tab === 'progress' && user?.id) {
      let mounted = true;
      setScoresLoading(true);
      apiService.getStudentScores(user.id)
        .then(r => { if (mounted) setScores(r.data); })
        .catch(() => {})
        .finally(() => { if (mounted) setScoresLoading(false); });
      return () => { mounted = false; };
    }
  }, [tab, user?.id]);

  useEffect(() => {
    let mounted = true;
    if (tab === 'history') {
      setHistLoading(true);
      apiService.getLessonRecords()
        .then(r => { if (mounted) setHistory(r.data); })
        .catch(() => {})
        .finally(() => { if (mounted) setHistLoading(false); });
    }
    if (tab === 'overview') {
      loadDashInsights();
    }
    if (tab === 'updates' || tab === 'overview') {
      setUpdatesLoading(true);
      apiService.getDashboardUpdates()
        .then(r => { if (mounted) setUpdates(r.data.updates ?? []); })
        .catch(() => {})
        .finally(() => { if (mounted) setUpdatesLoading(false); });
    }
    if (tab === 'overview') {
      setConvosLoading(true);
      apiService.getConversations()
        .then(r => { if (mounted) setConvos(r.data ?? []); })
        .catch(() => {})
        .finally(() => { if (mounted) setConvosLoading(false); });
    }
    return () => { mounted = false; };
  }, [tab]);

  const courses: any[] = data?.courses || [];

  const scheduleSlots = coursesToSlots(courses);

  // Pre-build id→course map so score cards don't do O(n) .find() per score
  const courseMap = useMemo(() =>
    Object.fromEntries(courses.map((c: any) => [c.id, c])),
  [courses]);

  const overallProgress = scores.length
    ? Math.round(scores.reduce((a: number, s: any) => a + (s.score ?? 0), 0) / scores.length)
    : 0;

  

  return (
    <DashboardLayout tabs={[
      { key: 'overview', label: t('tab.overview')        },
      { key: 'schedule', label: t('tab.mySchedule')      },
      { key: 'courses',  label: t('tab.myCourses')       },
      { key: 'progress', label: t('tab.progress')        },
      { key: 'history',  label: t('tab.learningHistory') },
      { key: 'updates',  label: t('tab.recentUpdates')   },
    ]} activeTab={tab} onTabChange={setTab}>
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {tab === 'overview' && (
            <>
              {/* Stat row */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                  { label: t('student.enrolledCourses'), value: courses.length,              color: 'bg-blue-500',   icon: '📚' },
                  { label: t('student.overallScore'),    value: `${overallProgress}%`,       color: 'bg-green-500',  icon: '📊' },
                  { label: t('student.aiInsights'),      value: data?.alerts?.length ?? 0,   color: 'bg-purple-500', icon: '🤖' },
                ].map(s => (
                  <div key={s.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl ${s.color} opacity-80 flex items-center justify-center text-lg`}>{s.icon}</div>
                    <div>
                      <p className="text-2xl font-black text-gray-900">{s.value}</p>
                      <p className="text-xs text-gray-500 font-medium">{s.label}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid lg:grid-cols-3 gap-6">
                {/* Left: Courses + Schedule */}
                <div className="lg:col-span-2 space-y-6">
                  {/* Courses preview */}
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-bold text-gray-800 text-sm">{t('nav.myCourses')}</h2>
                      <button onClick={() => setTab('courses')} className="text-blue-600 text-xs hover:underline">{t('student.seeAll')}</button>
                    </div>
                    {courses.length === 0 ? (
                      <div className="text-center py-8 text-gray-400 text-sm">
                        {t('student.notEnrolled')} <Link to="/courses" className="text-blue-600 hover:underline">{t('student.browseAllCourses')}</Link>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {courses.slice(0, 3).map((c: any, idx: number) => (
                          <div key={c.id} className="flex items-center gap-3 p-3 rounded-xl border border-gray-50 hover:border-blue-100 hover:bg-blue-50/20 transition">
                            <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                              ['bg-orange-400','bg-green-500','bg-blue-500','bg-purple-500'][idx % 4]
                            }`}>{c.code.slice(0,3)}</div>
                            <div className="flex-1 min-w-0">
                              <p className="font-semibold text-gray-800 text-sm truncate">{c.name}</p>
                              <p className="text-xs text-gray-400">{c.teacher_name || '—'}</p>
                            </div>
                            <button
                              onClick={() => navigate(`/courses/${c.id}`)}
                              className="text-xs bg-blue-500 hover:bg-blue-600 text-white px-3 py-1.5 rounded-lg transition flex-shrink-0"
                            >{t('student.openArrow')}</button>
                          </div>
                        ))}
                        {courses.length > 3 && (
                          <button onClick={() => setTab('courses')} className="w-full text-center text-xs text-blue-600 hover:underline py-1">
                            +{courses.length - 3} {t('dash.moreCourses')}
                          </button>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Weekly timetable preview */}
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
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
                      <p className="text-sm text-gray-400 text-center py-6">{t('student.noScheduleData')}</p>
                    ) : (
                      <WeeklySchedule
                        slots={scheduleSlots}
                        onSlotClick={slot => slot.id && navigate(`/courses/${slot.id}`)}
                      />
                    )}
                  </div>
                </div>

                {/* Right: Chat + Updates */}
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
                      <p className="text-xs text-gray-400 text-center py-6">{t('dash.noConversations')}</p>
                    ) : (
                      <div className="space-y-1">
                        {convos.slice(0, 3).map((c: any) => (
                          <Link key={c.id} to={`/chat?conv=${c.id}`} className="flex items-center gap-2.5 p-2 rounded-xl hover:bg-gray-50 transition">
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-300 to-purple-400 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                              {(c.other_participant_name || c.course_name || '?').slice(0,2).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between">
                                <p className="text-xs font-semibold text-gray-700 truncate">{c.other_participant_name || c.course_name || 'Chat'}</p>
                                {c.unread_count > 0 && (
                                  <span className="text-[10px] bg-blue-500 text-white rounded-full px-1.5 py-0.5 ml-1 flex-shrink-0">{c.unread_count}</span>
                                )}
                              </div>
                              {c.last_message_preview && (
                                <p className="text-[11px] text-gray-400 truncate mt-0.5">{c.last_message_preview}</p>
                              )}
                            </div>
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Updates preview */}
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="font-bold text-gray-800 text-sm">{t('student.recentUpdates')}</h2>
                      <button onClick={() => setTab('updates')} className="text-blue-600 text-xs hover:underline">{t('student.allUpdates')}</button>
                    </div>
                    {updatesLoading ? (
                      <div className="flex justify-center py-6">
                        <div className="w-5 h-5 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      </div>
                    ) : updates.length === 0 && (data?.alerts?.length ?? 0) === 0 ? (
                      <p className="text-xs text-gray-400 text-center py-6">{t('student.noUpdates')}</p>
                    ) : (
                      <div className="space-y-2">
                        {(data?.alerts ?? []).slice(0, 2).map((a: any, i: number) => (
                          <div key={`alert-${i}`} className={`p-2.5 rounded-lg text-xs border flex items-start gap-2 ${
                            a.type === 'warning' ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-green-50 border-green-200 text-green-800'
                          }`}>
                            <span>{a.type === 'warning' ? '⚠️' : '✅'}</span>
                            <span className="line-clamp-2">{a.message}</span>
                          </div>
                        ))}
                        {updates.slice(0, 3).map((u: any, i: number) => (
                          <div key={`upd-${i}`} className="flex items-center gap-2 text-xs py-1.5 border-b border-gray-50 last:border-0">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex-shrink-0 ${UPDATE_BADGE[u.type] ?? 'bg-gray-100 text-gray-600'}`}>
                              {u.type?.replace('_', ' ')}
                            </span>
                            <span className="text-gray-600 truncate">{formatActivityDescription(u.description, t)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* AI Dashboard Insights */}
                  <AIInsightsCard
                    insights={dashInsights}
                    loading={dashInsightsLoading}
                    onRefresh={loadDashInsights}
                  />
                </div>
              </div>
            </>
          )}

          {tab === 'schedule' && (
            <div className="grid lg:grid-cols-3 gap-6">
              {/* Schedule */}
              <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                  <div>
                    <h2 className="font-bold text-gray-800 text-sm">{t('student.myClassSchedule')}</h2>
                    <p className="text-xs text-gray-400 mt-0.5">{courses.length} {t('student.enrolledCourses')}</p>
                  </div>
                  <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
                    {(['weekly', 'monthly', 'yearly'] as const).map(v => (
                      <button
                        key={v}
                        onClick={() => setScheduleView(v)}
                        className={`px-3 py-1 text-xs rounded-md font-semibold transition ${scheduleView === v ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
                      >
                        {t(`schedule.${v}`) || v.charAt(0).toUpperCase() + v.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {scheduleView === 'weekly' && (
                  scheduleSlots.length > 0 ? (
                    <WeeklySchedule slots={scheduleSlots} />
                  ) : (
                    <EmptyState
                      icon="📅"
                      title={t('student.noScheduledCourses')}
                      action={<Link to="/courses" className="text-blue-600 text-sm hover:underline">{t('student.browseAllCourses')}</Link>}
                    />
                  )
                )}

                {scheduleView === 'monthly' && (
                  courses.length === 0 ? (
                    <EmptyState icon="📅" title={t('student.noScheduledCourses')} />
                  ) : (
                    <div className="space-y-3">
                      {(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'] as const).map(day => {
                        const dayCourses = courses.filter((c: any) => c.schedule?.days?.includes(day));
                        if (dayCourses.length === 0) return null;
                        return (
                          <div key={day}>
                            <p className="text-xs font-semibold text-gray-500 mb-1.5">{t(`courseForm.day.${day.toLowerCase()}`) || day}</p>
                            <div className="flex flex-wrap gap-2">
                              {dayCourses.map((c: any) => (
                                <span key={c.id} className="text-xs bg-indigo-50 text-indigo-700 px-3 py-1.5 rounded-lg font-medium">
                                  {c.name}
                                  {c.schedule?.start_time && <span className="ml-1 text-indigo-400">{c.schedule.start_time}–{c.schedule.end_time}</span>}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )
                )}

                {scheduleView === 'yearly' && (
                  courses.length === 0 ? (
                    <EmptyState icon="📅" title={t('student.noEnrolledCourses')} />
                  ) : (
                    <div className="space-y-2">
                      {courses.map((c: any) => (
                        <div key={c.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-xl">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-gray-700 truncate">{c.name}</p>
                            <p className="text-xs text-gray-400">{c.code}</p>
                          </div>
                          {c.schedule?.days?.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {c.schedule.days.map((d: string) => (
                                <span key={d} className="text-[10px] bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full font-semibold">
                                  {t(`courseForm.day.${d.toLowerCase()}`) || d}
                                </span>
                              ))}
                            </div>
                          )}
                          {c.schedule?.start_time && (
                            <span className="text-xs text-gray-400 whitespace-nowrap">{c.schedule.start_time}–{c.schedule.end_time}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )
                )}
              </div>

              {/* Progress chart */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col items-center">
                <h2 className="font-bold text-gray-800 text-sm mb-4 self-start">{t('dash.myProgress')}</h2>
                <CircularProgress percent={overallProgress} size={150} />
                <p className="text-xs text-gray-400 mt-4 text-center">{t('student.semesterCourses')} ({courses.length})</p>
              </div>
            </div>
          )}

          {tab === 'courses' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-800 text-sm">{t('nav.myCourses')}</h2>
                <Link to="/courses" className="text-blue-600 text-xs hover:underline">{t('student.browseAll')}</Link>
              </div>

              {courses.length === 0 ? (
                <div className="text-center py-16 text-gray-400">
                  <div className="text-5xl mb-3">📖</div>
                  <p>{t('student.notEnrolled')}</p>
                  <Link to="/courses" className="mt-2 inline-block text-blue-600 text-sm hover:underline">{t('student.browseAllCourses')}</Link>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {[t('admin.colCourse'), t('courseDetail.teacher'), t('student.colProgress'), t('student.colAction')].map(h => (
                        <th key={h} className="text-left text-gray-400 font-semibold text-xs pb-3 pr-6">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {courses.map((c: any, idx: number) => {
                      const scoreObj = scores.find((s: any) => s.course_id === c.id);
                      const p = scoreObj ? Math.round(scoreObj.score) : 0;
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
                              </div>
                            </div>
                          </td>
                          <td className="py-3 pr-6 text-gray-600 text-sm">{c.teacher_name || '—'}</td>
                          <td className="py-3 pr-6 w-52">
                            <ProgressBar percent={p} height={6} />
                          </td>
                          <td className="py-3 pr-6">
                            <button
                              onClick={() => navigate(`/courses/${c.id}`)}
                              className="bg-blue-500 hover:bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg transition flex items-center gap-1"
                            >
                              {t('student.openArrow')}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'progress' && (
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col items-center">
                <h2 className="font-bold text-gray-800 text-sm mb-4 self-start">{t('student.overallPerformance')}</h2>
                <CircularProgress percent={overallProgress} size={160} />
              </div>
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <h2 className="font-bold text-gray-800 text-sm mb-4">{t('student.courseProgress')}</h2>
                {courses.length === 0 ? (
                  <p className="text-gray-400 text-sm text-center py-8">{t('student.noCoursesEnrolled')}</p>
                ) : (
                  <div className="space-y-4">
                    {scoresLoading ? (
                      <div className="flex justify-center py-6">
                        <div className="w-5 h-5 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                      </div>
                    ) : courses.map((c: any) => {
                      const scoreObj = scores.find((s: any) => s.course_id === c.id);
                      const p = scoreObj ? Math.round(scoreObj.score) : null;
                      return (
                        <div key={c.id}>
                          <div className="flex justify-between text-xs mb-1.5">
                            <span className="font-semibold text-gray-700 truncate pr-2">{c.name}</span>
                            {p !== null
                              ? <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${labelColor(p)}`}>{p}%</span>
                              : <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-100 text-gray-400">—</span>
                            }
                          </div>
                          <ProgressBar percent={p ?? 0} showLabel={false} height={6} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Performance Score Cards */}
              {scoresLoading ? (
                <div className="lg:col-span-2 flex justify-center py-6">
                  <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : scores.length > 0 && (
                <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-4">{t('student.performanceScores')}</h2>
                  <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {scores.map((s: any) => {
                      const cls = s.classification ?? 'average';
                      const colorCls = SCORE_COLOR[cls] ?? SCORE_COLOR.average;
                      const course = courseMap[s.course_id];
                      return (
                        <div key={s.id} className={`rounded-xl border p-4 ${colorCls}`}>
                          <p className="text-xs font-semibold truncate mb-1">
                            {course?.name ?? s.course_id}
                          </p>
                          <p className="text-2xl font-black mb-1">{s.score.toFixed(1)}</p>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${colorCls}`}>
                            {t(`classification.${cls}`) || SCORE_LABEL[cls] || cls}
                          </span>
                          <div className="mt-3 space-y-1 text-[10px] opacity-80">
                            <div className="flex justify-between">
                              <span>{t('progress.grades')}</span>
                              <span>{s.grade_score.toFixed(0)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>{t('progress.attendance')}</span>
                              <span>{s.attendance_score.toFixed(0)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>{t('progress.feedback')}</span>
                              <span>{s.feedback_score.toFixed(0)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span>{t('progress.trend')}</span>
                              <span>{s.trend_score.toFixed(0)}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Insights */}
              {data?.alerts?.length > 0 && (
                <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                  <h2 className="font-bold text-gray-800 text-sm mb-3">{t('student.aiInsights')}</h2>
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
                </div>
              )}
            </div>
          )}

          {tab === 'updates' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <h2 className="font-bold text-gray-800 text-sm mb-4">{t('student.recentUpdates')}</h2>
              {updatesLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : updates.length === 0 ? (
                <EmptyState icon="🔔" title={t('student.noUpdates')} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('updates.timestamp'), t('updates.type'), t('updates.description'), t('admin.colCourse')].map(h => (
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
                          <td className="py-2.5 pr-4 text-gray-500 truncate">{u.course_name ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'history' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-800 text-sm">{t('student.learningHistory')}</h2>
                <button
                  onClick={() => {
                    if (!user?.id) return;
                    apiService.exportStudentReport(user.id, 'pdf').then(r => {
                      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                      const a = document.createElement('a'); a.href = url; a.download = 'report.pdf'; a.click();
                    }).catch(() => {});
                  }}
                  className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition"
                >
                  {t('student.exportPDF')}
                </button>
              </div>

              {histLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : history.length === 0 ? (
                <EmptyState icon="📋" title={t('student.noLessonRecords')} description={t('student.noLessonRecordsDesc')} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('common.date') || 'Date', t('history.course') || 'Course', t('common.attendance') || 'Attendance', t('common.grade') || 'Grade', t('common.feedback') || 'Feedback'].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {history.map((r: any) => (
                        <tr key={r.id} className="hover:bg-gray-50 transition">
                          <td className="py-2.5 pr-4 text-gray-600">
                            {new Date(r.lesson_date).toLocaleDateString()}
                          </td>
                          <td className="py-2.5 pr-4 text-gray-500 truncate max-w-[120px]">
                            {courseMap[r.course_id]?.name ?? r.course_id ?? '—'}
                          </td>
                          <td className="py-2.5 pr-4">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${ATT_COLOR[r.attendance_status] ?? 'bg-gray-100 text-gray-600'}`}>
                              {t(`att.${r.attendance_status}`) || r.attendance_status}
                            </span>
                          </td>
                          <td className="py-2.5 pr-4 font-semibold text-gray-800">
                            {r.grade_value != null ? `${r.grade_value}%` : '—'}
                          </td>
                          <td className="py-2.5 pr-4 text-gray-500 max-w-xs truncate">
                            {r.teacher_feedback || '—'}
                          </td>
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
    </DashboardLayout>
  );
};
