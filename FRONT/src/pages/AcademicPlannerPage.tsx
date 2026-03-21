import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { apiService } from '../services/apiService';
import { useApp } from '../contexts/AppContext';
import { useAuth } from '../contexts/AuthContext';

// ── Types ──────────────────────────────────────────────────────────────────

interface CourseItem {
  id: string;
  name: string;
  code: string;
  status?: string;
  schedule?: { days?: string[]; start_time?: string; end_time?: string } | null;
  teacher_id?: string;
}

interface WorkloadDay {
  hours: number;
  courses: number;
  consecutive_blocks: number;
  pressure: 'light' | 'moderate' | 'heavy';
  slots: { name: string; time: string }[];
}

interface WorkloadSummary {
  weekly_hours: number;
  pressure_level: string;
  days: Record<string, WorkloadDay>;
  overloaded_days: string[];
  free_day_respected: boolean;
  balanced: boolean;
  summary_text: string;
}

interface RiskWarning {
  severity: 'info' | 'warning' | 'critical';
  course_id: string | null;
  message: string;
}

interface ConflictItem {
  course_a: { id: string; name: string };
  course_b: { id: string; name: string };
  shared_days: string[];
  time_a: string;
  time_b: string;
}

interface Combination {
  rank: number;
  score: number;
  explanation: string;
  courses: CourseItem[];
  excluded_courses: { id: string; name: string }[];
  workload_summary: WorkloadSummary;
  risk_warnings: RiskWarning[];
  hours_per_day: Record<string, number>;
}

interface AnalysisResult {
  combinations: Combination[];
  total_valid: number;
  selected_count: number;
  conflicts: ConflictItem[];
  global_workload: WorkloadSummary;
  global_risk_warnings: RiskWarning[];
  personalization_level: 'schedule_only' | 'partial' | 'full';
  message: string;
}

interface Recommendation {
  course: CourseItem;
  fit_score: number;
  reasons: string[];
  warnings: string[];
  schedule_fit: 'no_conflict' | 'has_conflict';
  category: 'great_fit' | 'good_fit' | 'possible' | 'not_recommended';
}

interface RecommendationsResult {
  recommendations: Recommendation[];
  enrolled_course_ids: string[];
  personalization_level: string;
  message: string;
}

interface ChildInfo {
  id: string;
  name: string;
}

interface Prefs {
  preferred_days: string[];
  preferred_free_day: string;
  max_courses: number;
  max_hours_per_day: number;
  avoid_early: boolean;
  avoid_late: boolean;
}

const ALL_DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

// ── Small reusable pieces ──────────────────────────────────────────────────

const ScheduleBadge: React.FC<{ schedule?: CourseItem['schedule'] }> = ({ schedule }) => {
  if (!schedule) return <span className="text-xs text-gray-400 italic">No schedule</span>;
  const days = (schedule.days ?? []).map(d => d.slice(0, 3)).join(', ');
  const time = schedule.start_time && schedule.end_time
    ? `${schedule.start_time}–${schedule.end_time}` : '';
  if (!days && !time) return <span className="text-xs text-gray-400 italic">No schedule</span>;
  return (
    <span className="text-xs text-blue-600 bg-blue-50 rounded px-1.5 py-0.5 whitespace-nowrap">
      {days}{time ? ` · ${time}` : ''}
    </span>
  );
};

const ScoreBar: React.FC<{ score: number }> = ({ score }) => {
  const color = score >= 70 ? 'bg-green-500' : score >= 45 ? 'bg-yellow-500' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-bold text-gray-700 w-8 text-right">{score}</span>
    </div>
  );
};

const PressureChip: React.FC<{ level: string }> = ({ level }) => {
  const map: Record<string, string> = {
    light:    'bg-green-50 text-green-700',
    moderate: 'bg-yellow-50 text-yellow-700',
    heavy:    'bg-red-50 text-red-700',
    unknown:  'bg-gray-50 text-gray-500',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${map[level] ?? map.unknown}`}>
      {level}
    </span>
  );
};

const SeverityIcon: React.FC<{ severity: string }> = ({ severity }) => {
  if (severity === 'critical') return <span className="text-red-500 flex-shrink-0">⛔</span>;
  if (severity === 'warning')  return <span className="text-amber-500 flex-shrink-0">⚠</span>;
  return <span className="text-blue-400 flex-shrink-0">ℹ</span>;
};

const SeverityBg: Record<string, string> = {
  critical: 'bg-red-50 border-red-200',
  warning:  'bg-amber-50 border-amber-200',
  info:     'bg-blue-50 border-blue-100',
};

const CategoryBadge: React.FC<{ category: string; t: (k: string) => string }> = ({ category, t }) => {
  const map: Record<string, string> = {
    great_fit:        'bg-green-100 text-green-800',
    good_fit:         'bg-blue-100 text-blue-800',
    possible:         'bg-yellow-100 text-yellow-800',
    not_recommended:  'bg-red-100 text-red-800',
  };
  const labels: Record<string, string> = {
    great_fit:       'planner.recGreat',
    good_fit:        'planner.recGood',
    possible:        'planner.recPossible',
    not_recommended: 'planner.recNot',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${map[category] ?? ''}`}>
      {t(labels[category] ?? category)}
    </span>
  );
};

// ── Workload Summary Panel ─────────────────────────────────────────────────

const WorkloadPanel: React.FC<{ workload: WorkloadSummary; t: (k: string) => string }> = ({ workload, t }) => (
  <div className="space-y-3">
    <div className="flex items-center gap-3 flex-wrap">
      {workload.weekly_hours != null && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">{t('planner.weeklyHours')}:</span>
          <span className="text-sm font-bold text-gray-800">{workload.weekly_hours}h</span>
        </div>
      )}
      {workload.pressure_level && (
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">{t('planner.pressure')}:</span>
          <PressureChip level={workload.pressure_level} />
        </div>
      )}
      {workload.balanced && (
        <span className="text-xs text-green-600 font-medium">✓ Balanced</span>
      )}
    </div>

    {Object.keys(workload.days ?? {}).length > 0 && (
      <div className="flex flex-wrap gap-2">
        {Object.entries(workload.days).map(([day, info]) => (
          <div key={day} className={`rounded-lg border px-3 py-2 text-xs ${
            info.pressure === 'heavy'    ? 'bg-red-50 border-red-200' :
            info.pressure === 'moderate' ? 'bg-yellow-50 border-yellow-200' :
            'bg-green-50 border-green-200'
          }`}>
            <p className="font-semibold text-gray-700">{day.slice(0, 3)}</p>
            <p className="text-gray-500">{info.hours}h · {info.courses} course{info.courses !== 1 ? 's' : ''}</p>
            {info.consecutive_blocks > 0 && (
              <p className="text-amber-600">{info.consecutive_blocks} back-to-back</p>
            )}
          </div>
        ))}
      </div>
    )}

    <p className="text-xs text-gray-500 italic">{workload.summary_text}</p>
  </div>
);

// ── Risk Warnings Panel ────────────────────────────────────────────────────

const RisksPanel: React.FC<{ risks: RiskWarning[]; t: (k: string) => string }> = ({ risks, t }) => {
  if (risks.length === 0) {
    return <p className="text-xs text-green-600 font-medium">✓ {t('planner.noRisks')}</p>;
  }
  return (
    <div className="space-y-2">
      {risks.map((r, i) => (
        <div key={i} className={`flex items-start gap-2 text-xs rounded-lg border px-3 py-2 ${SeverityBg[r.severity] ?? SeverityBg.info}`}>
          <SeverityIcon severity={r.severity} />
          <span className="text-gray-700">{r.message}</span>
        </div>
      ))}
    </div>
  );
};

// ── Main page ──────────────────────────────────────────────────────────────

export const AcademicPlannerPage: React.FC = () => {
  const { t } = useApp();
  const { user } = useAuth();
  const navigate = useNavigate();
  const isParent = user?.role === 'parent';

  // Child selector (parent only)
  const [children, setChildren] = useState<ChildInfo[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<string>('');

  // Course list
  const [courses, setCourses]       = useState<CourseItem[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);

  // Selection & prefs
  const [selected, setSelected]     = useState<Set<string>>(new Set());
  const [prefs, setPrefs]           = useState<Prefs>({
    preferred_days: [], preferred_free_day: '',
    max_courses: 5, max_hours_per_day: 6,
    avoid_early: false, avoid_late: false,
  });

  // Analysis
  const [analyzing, setAnalyzing]   = useState(false);
  const [result, setResult]         = useState<AnalysisResult | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [view, setView]             = useState<'select' | 'results'>('select');
  const [activeTab, setActiveTab]   = useState<'plan' | 'recommend'>('plan');
  const [expandedCombo, setExpandedCombo] = useState<number>(1);  // which combination card is expanded

  // Recommendations
  const [recs, setRecs]             = useState<RecommendationsResult | null>(null);
  const [loadingRecs, setLoadingRecs] = useState(false);

  // Load children for parent
  useEffect(() => {
    if (!isParent) return;
    (async () => {
      try {
        const res = await apiService.getDashboard();
        const ps = res.data?.performance_scores ?? [];
        const kids: ChildInfo[] = [];
        const seen = new Set<string>();
        for (const p of ps) {
          if (p.student_id && !seen.has(p.student_id)) {
            seen.add(p.student_id);
            kids.push({ id: p.student_id, name: p.student_name ?? p.student_id });
          }
        }
        setChildren(kids);
        if (kids.length > 0) setSelectedChildId(kids[0].id);
      } catch {}
    })();
  }, [isParent]);

  // Load courses
  useEffect(() => {
    (async () => {
      setLoadingCourses(true);
      try {
        const res = await apiService.getCourses();
        setCourses((res.data ?? []).filter((c: any) => c.status === 'published'));
      } catch { setCourses([]); }
      finally { setLoadingCourses(false); }
    })();
  }, []);

  // Load recommendations when switching to recommend tab
  const loadRecs = useCallback(async () => {
    setLoadingRecs(true);
    try {
      const res = await apiService.getPlannerRecommendations({
        student_id:  isParent ? selectedChildId || undefined : undefined,
        avoid_early: prefs.avoid_early,
        avoid_late:  prefs.avoid_late,
        max_hours_day: prefs.max_hours_per_day,
      });
      setRecs(res.data);
    } catch { setRecs(null); }
    finally { setLoadingRecs(false); }
  }, [isParent, selectedChildId, prefs.avoid_early, prefs.avoid_late, prefs.max_hours_per_day]);

  useEffect(() => {
    if (activeTab === 'recommend') loadRecs();
  }, [activeTab, loadRecs]);

  const toggleCourse = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
    setResult(null);
  };

  const toggleDay = (day: string) => {
    setPrefs(p => ({
      ...p,
      preferred_days: p.preferred_days.includes(day)
        ? p.preferred_days.filter(d => d !== day)
        : [...p.preferred_days, day],
    }));
  };

  const analyze = async () => {
    if (selected.size < 2) { setError(t('planner.selectAtLeast2')); return; }
    setAnalyzing(true); setError(null);
    try {
      const res = await apiService.analyzeSchedule({
        course_ids:  Array.from(selected),
        student_id:  isParent ? selectedChildId || undefined : undefined,
        preferences: {
          preferred_days:      prefs.preferred_days.length ? prefs.preferred_days : undefined,
          preferred_free_day:  prefs.preferred_free_day || undefined,
          max_courses:         prefs.max_courses,
          max_hours_per_day:   prefs.max_hours_per_day,
          avoid_early:         prefs.avoid_early,
          avoid_late:          prefs.avoid_late,
        },
      });
      setResult(res.data);
      setView('results');
      setExpandedCombo(1);
    } catch (e: any) {
      const data = e?.response?.data;
      const errMsg = data?.detail || data?.error || `Analysis failed (${e?.response?.status ?? 'network error'}).`;
      console.error('[Planner] analyze error:', e?.response?.status, data);
      setError(errMsg);
    } finally { setAnalyzing(false); }
  };

  const requestCourse = (courseId: string) => {
    navigate(`/courses/${courseId}`);
  };

  const personalizationBadge = (level?: string) => {
    if (level === 'full')    return <span className="text-[10px] text-green-600 bg-green-50 rounded px-2 py-0.5 font-medium">🧠 {t('planner.personalized')}</span>;
    if (level === 'partial') return <span className="text-[10px] text-blue-600 bg-blue-50 rounded px-2 py-0.5 font-medium">📊 {t('planner.partial')}</span>;
    return <span className="text-[10px] text-gray-500 bg-gray-50 rounded px-2 py-0.5">{t('planner.scheduleOnly')}</span>;
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      <div className="p-6 max-w-5xl mx-auto space-y-5">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('planner.title')}</h1>
            <p className="text-sm text-gray-500 mt-0.5">{t('planner.subtitle')}</p>
          </div>
          {/* Child picker for parents */}
          {isParent && children.length > 0 && (
            <div className="flex items-center gap-2 bg-indigo-50 rounded-xl px-3 py-2">
              <span className="text-xs text-indigo-600 font-semibold flex-shrink-0">{t('planner.forChild')}:</span>
              <select
                value={selectedChildId}
                onChange={e => setSelectedChildId(e.target.value)}
                className="text-xs border border-indigo-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-300"
              >
                {children.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}
        </div>

        {/* Tab bar */}
        {view === 'select' && (
          <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
            {(['plan', 'recommend'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`text-xs font-semibold px-4 py-2 rounded-lg transition-all ${
                  activeTab === tab ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab === 'plan' ? t('planner.tabPlan') : t('planner.tabRecommend')}
              </button>
            ))}
          </div>
        )}

        {/* ── PLAN TAB ─────────────────────────────────────────────── */}
        {activeTab === 'plan' && view === 'select' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* Course selection grid */}
            <div className="lg:col-span-2 space-y-4">
              <h2 className="font-semibold text-gray-800 text-sm">{t('planner.selectCourses')}</h2>
              {loadingCourses ? (
                <div className="flex justify-center py-12">
                  <div className="w-6 h-6 border-4 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : courses.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-10">{t('planner.noCourses')}</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {courses.map(c => {
                    const sel = selected.has(c.id);
                    return (
                      <button
                        key={c.id}
                        onClick={() => toggleCourse(c.id)}
                        className={`text-left rounded-xl border-2 p-3 transition-all ${
                          sel ? 'border-blue-500 bg-blue-50 shadow-sm' : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/30'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="font-semibold text-gray-800 text-xs truncate">{c.name}</p>
                            <p className="text-[10px] text-gray-400 mt-0.5">{c.code}</p>
                          </div>
                          <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center transition-all ${
                            sel ? 'border-blue-500 bg-blue-500' : 'border-gray-300'
                          }`}>
                            {sel && <svg width="8" height="8" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round"/></svg>}
                          </div>
                        </div>
                        <div className="mt-2"><ScheduleBadge schedule={c.schedule} /></div>
                      </button>
                    );
                  })}
                </div>
              )}
              {selected.size > 0 && (
                <p className="text-xs text-blue-600 font-medium">
                  {selected.size} course{selected.size !== 1 ? 's' : ''} selected
                </p>
              )}
            </div>

            {/* Preferences panel */}
            <div className="space-y-4">
              <h2 className="font-semibold text-gray-800 text-sm">{t('planner.preferences')}</h2>
              <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4 text-sm">

                {/* Preferred days */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">{t('planner.prefDays')}</label>
                  <div className="flex flex-wrap gap-1.5">
                    {ALL_DAYS.map(day => (
                      <button
                        key={day}
                        onClick={() => toggleDay(day)}
                        className={`text-xs px-2 py-1 rounded-lg border transition-all ${
                          prefs.preferred_days.includes(day)
                            ? 'border-indigo-500 bg-indigo-500 text-white'
                            : 'border-gray-200 text-gray-600 hover:border-indigo-300'
                        }`}
                      >
                        {day.slice(0, 3)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Preferred free day */}
                <div>
                  <label className="block text-xs text-gray-500 mb-1">{t('planner.prefFreeDay')}</label>
                  <select
                    value={prefs.preferred_free_day}
                    onChange={e => setPrefs(p => ({ ...p, preferred_free_day: e.target.value }))}
                    className="w-full text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  >
                    <option value="">— None —</option>
                    {ALL_DAYS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>

                {/* Max courses */}
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    {t('planner.maxCourses')}: <strong>{prefs.max_courses}</strong>
                  </label>
                  <input type="range" min={2} max={10} step={1}
                    value={prefs.max_courses}
                    onChange={e => setPrefs(p => ({ ...p, max_courses: +e.target.value }))}
                    className="w-full accent-indigo-500"
                  />
                </div>

                {/* Max hours/day */}
                <div>
                  <label className="block text-xs text-gray-500 mb-1">
                    {t('planner.maxHoursDay')}: <strong>{prefs.max_hours_per_day}h</strong>
                  </label>
                  <input type="range" min={1} max={12} step={0.5}
                    value={prefs.max_hours_per_day}
                    onChange={e => setPrefs(p => ({ ...p, max_hours_per_day: +e.target.value }))}
                    className="w-full accent-indigo-500"
                  />
                </div>

                {/* Avoid early / late */}
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={prefs.avoid_early}
                    onChange={e => setPrefs(p => ({ ...p, avoid_early: e.target.checked }))}
                    className="accent-indigo-500" />
                  <span className="text-xs text-gray-600">{t('planner.avoidEarly')}</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={prefs.avoid_late}
                    onChange={e => setPrefs(p => ({ ...p, avoid_late: e.target.checked }))}
                    className="accent-indigo-500" />
                  <span className="text-xs text-gray-600">{t('planner.avoidLate')}</span>
                </label>
              </div>

              {error && <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

              <button
                onClick={analyze}
                disabled={analyzing || selected.size < 2}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold py-2.5 rounded-xl transition"
              >
                {analyzing ? t('planner.analyzing') : t('planner.analyze')}
              </button>
            </div>
          </div>
        )}

        {/* ── RESULTS VIEW ──────────────────────────────────────────── */}
        {activeTab === 'plan' && view === 'results' && result && (
          <div className="space-y-6">

            {/* Header row */}
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <h2 className="font-semibold text-gray-800">{t('planner.results')}</h2>
                <p className="text-xs text-gray-400 mt-0.5">{result.message}</p>
                <div className="mt-1">{personalizationBadge(result.personalization_level)}</div>
              </div>
              <button onClick={() => setView('select')} className="text-sm text-indigo-600 hover:underline">
                {t('planner.back')}
              </button>
            </div>

            {/* No valid combinations */}
            {result.combinations.length === 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
                <p className="text-sm font-semibold text-amber-800">{t('planner.noResults')}</p>
                {result.global_workload && (
                  <WorkloadPanel workload={result.global_workload} t={t} />
                )}
                {result.global_risk_warnings?.length > 0 && (
                  <RisksPanel risks={result.global_risk_warnings} t={t} />
                )}
              </div>
            )}

            {/* Combination cards */}
            {result.combinations.map(combo => {
              const isExpanded = expandedCombo === combo.rank;
              return (
                <div key={combo.rank} className={`rounded-2xl border p-5 space-y-4 transition-all ${
                  combo.rank === 1 ? 'border-green-300 bg-green-50/30' : 'border-gray-200 bg-white'
                }`}>
                  {/* Combo header — always visible */}
                  <button
                    className="w-full text-left"
                    onClick={() => setExpandedCombo(isExpanded ? 0 : combo.rank)}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {combo.rank === 1 && (
                            <span className="text-xs bg-green-500 text-white font-bold px-2 py-0.5 rounded-full">
                              {t('planner.bestMatch')}
                            </span>
                          )}
                          <span className="text-xs text-gray-500 font-medium">
                            {t('planner.combination')} #{combo.rank} · {combo.courses.length} courses
                          </span>
                          <PressureChip level={combo.workload_summary?.pressure_level ?? 'unknown'} />
                          {combo.risk_warnings.filter(r => r.severity === 'critical').length > 0 && (
                            <span className="text-xs bg-red-100 text-red-700 font-semibold px-2 py-0.5 rounded-full">
                              ⛔ {combo.risk_warnings.filter(r => r.severity === 'critical').length} critical
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-600 max-w-lg">{combo.explanation}</p>
                      </div>
                      <div className="flex-shrink-0 min-w-[7rem] text-right space-y-1">
                        <p className="text-[10px] text-gray-400">{t('planner.score')}</p>
                        <ScoreBar score={combo.score} />
                        <span className="text-[10px] text-gray-400">{isExpanded ? '▲ collapse' : '▼ expand'}</span>
                      </div>
                    </div>
                  </button>

                  {/* Expandable detail */}
                  {isExpanded && (
                    <div className="space-y-4 pt-2 border-t border-gray-100">

                      {/* Courses */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {combo.courses.map(c => (
                          <div key={c.id} className="flex items-center justify-between bg-white rounded-lg border border-gray-100 px-3 py-2 gap-2">
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-gray-800 truncate">{c.name}</p>
                              <p className="text-[10px] text-gray-400">{c.code}</p>
                            </div>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              <ScheduleBadge schedule={c.schedule} />
                              <button
                                onClick={() => requestCourse(c.id)}
                                className="text-[10px] text-indigo-600 hover:underline"
                              >
                                {t('planner.viewCourse')}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Workload */}
                      {combo.workload_summary && Object.keys(combo.workload_summary.days ?? {}).length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">{t('planner.workload')}</h4>
                          <WorkloadPanel workload={combo.workload_summary} t={t} />
                        </div>
                      )}

                      {/* Risks */}
                      <div>
                        <h4 className="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">{t('planner.risks')}</h4>
                        <RisksPanel risks={combo.risk_warnings} t={t} />
                      </div>

                      {/* Excluded */}
                      {combo.excluded_courses.length > 0 && (
                        <div>
                          <p className="text-[10px] text-gray-400 mb-1.5 font-medium uppercase tracking-wide">{t('planner.excluded')}</p>
                          <div className="flex flex-wrap gap-1.5">
                            {combo.excluded_courses.map(ec => (
                              <span key={ec.id} className="text-xs bg-red-50 text-red-600 rounded px-2 py-0.5 line-through">{ec.name}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Request CTA */}
                      <div className="pt-1 flex flex-wrap gap-2">
                        {combo.courses.map(c => (
                          <button
                            key={c.id}
                            onClick={() => requestCourse(c.id)}
                            className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-3 py-1.5 rounded-lg transition"
                          >
                            {t('planner.viewCourse')}: {c.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Conflicts section */}
            {result.conflicts?.length > 0 && (
              <div className="bg-white rounded-2xl border border-gray-200 p-5">
                <h3 className="font-semibold text-gray-800 text-sm mb-3">
                  {t('planner.conflicts')} ({result.conflicts.length})
                </h3>
                <div className="space-y-2">
                  {result.conflicts.map((cf, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-gray-600 bg-amber-50 rounded-lg border border-amber-200 px-3 py-2">
                      <span className="text-amber-500 flex-shrink-0 mt-0.5">⚠</span>
                      <span>
                        <strong>{cf.course_a.name}</strong> {t('planner.and')} <strong>{cf.course_b.name}</strong>
                        {cf.shared_days.length > 0 && <> — {cf.shared_days.join(', ')} ({cf.time_a} / {cf.time_b})</>}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── RECOMMEND TAB ─────────────────────────────────────────── */}
        {activeTab === 'recommend' && (
          <div className="space-y-5">
            <div>
              <h2 className="font-semibold text-gray-800">{t('planner.recTitle')}</h2>
              <p className="text-xs text-gray-400 mt-0.5">{t('planner.recSubtitle')}</p>
            </div>

            {loadingRecs ? (
              <div className="flex justify-center py-12">
                <div className="w-6 h-6 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : !recs || recs.recommendations.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-10">{t('planner.recNoData')}</p>
            ) : (
              <>
                <div className="flex items-center gap-2 flex-wrap">
                  {personalizationBadge(recs.personalization_level)}
                  <span className="text-xs text-gray-400">{recs.message}</span>
                </div>

                <div className="space-y-3">
                  {recs.recommendations.map((rec, i) => (
                    <div key={i} className={`rounded-2xl border p-4 space-y-3 ${
                      rec.category === 'great_fit' ? 'border-green-200 bg-green-50/30' :
                      rec.category === 'not_recommended' ? 'border-red-100 bg-red-50/20' :
                      'border-gray-200 bg-white'
                    }`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <CategoryBadge category={rec.category} t={t} />
                            <span className="text-xs font-semibold text-gray-800 truncate">{rec.course.name}</span>
                            <span className="text-xs text-gray-400">{rec.course.code}</span>
                          </div>
                          <ScheduleBadge schedule={rec.course.schedule} />
                        </div>
                        <div className="flex-shrink-0 min-w-[7rem]">
                          <p className="text-[10px] text-gray-400 mb-1">{t('planner.score')}</p>
                          <ScoreBar score={rec.fit_score} />
                        </div>
                      </div>

                      {/* Reasons */}
                      {rec.reasons.length > 0 && (
                        <div className="space-y-1">
                          {rec.reasons.map((r, j) => (
                            <div key={j} className="flex items-start gap-1.5 text-xs text-green-700">
                              <span className="flex-shrink-0 mt-0.5">✓</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Warnings */}
                      {rec.warnings.length > 0 && (
                        <div className="space-y-1">
                          {rec.warnings.map((w, j) => (
                            <div key={j} className="flex items-start gap-1.5 text-xs text-amber-700">
                              <span className="flex-shrink-0 mt-0.5">⚠</span>
                              <span>{w}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Action */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => requestCourse(rec.course.id)}
                          className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-3 py-1.5 rounded-lg transition"
                        >
                          {t('planner.viewCourse')}
                        </button>
                        <button
                          onClick={() => {
                            setSelected(prev => {
                              const next = new Set(prev);
                              next.add(rec.course.id);
                              return next;
                            });
                            setActiveTab('plan');
                          }}
                          className="text-xs border border-indigo-200 text-indigo-600 hover:bg-indigo-50 font-medium px-3 py-1.5 rounded-lg transition"
                        >
                          + Add to plan
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};
