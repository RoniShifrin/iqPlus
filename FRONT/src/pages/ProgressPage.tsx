import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { ProgressBar } from '../components/widgets/ProgressBar';
import { AIInsightPanel } from '../components/AIInsightPanel';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

/* ── helpers ── */
const SCORE_BADGE: Record<string, string> = {
  excellent:       'bg-emerald-100 text-emerald-700',
  good:            'bg-blue-100 text-blue-700',
  average:         'bg-yellow-100 text-yellow-700',
  needs_attention: 'bg-red-100 text-red-700',
};
const PRED_BADGE: Record<string, string> = {
  likely_improving:   'bg-emerald-100 text-emerald-700',
  likely_stable:      'bg-blue-100 text-blue-700',
  at_risk:            'bg-yellow-100 text-yellow-800',
  needs_intervention: 'bg-red-100 text-red-700',
};
const PRED_ICON: Record<string, string> = {
  likely_improving:   '↑',
  likely_stable:      '→',
  at_risk:            '⚠',
  needs_intervention: '🚨',
};
const labelStr = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

/* ── Prediction card ── */
const PredictionCard: React.FC<{ pred: any }> = ({ pred }) => {
  if (!pred?.prediction_label) return null;
  return (
    <div className={`rounded-xl border p-4 text-sm ${PRED_BADGE[pred.prediction_label] ?? 'bg-gray-100 text-gray-700'}`}>
      <div className="flex items-center gap-2 font-bold mb-1">
        <span>{PRED_ICON[pred.prediction_label] ?? '•'}</span>
        <span>{labelStr(pred.prediction_label)}</span>
        {pred.risk_level && (
          <span className={`ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            pred.risk_level === 'high'   ? 'bg-red-200 text-red-800'
            : pred.risk_level === 'medium' ? 'bg-yellow-200 text-yellow-800'
            : 'bg-gray-200 text-gray-600'
          }`}>{pred.risk_level} risk</span>
        )}
      </div>
      <p className="opacity-90">{pred.explanation}</p>
      {pred.recommendation && (
        <p className="mt-1.5 text-xs opacity-75 italic">{pred.recommendation}</p>
      )}
    </div>
  );
};

/* ── Score breakdown ── */
const ScoreBreakdown: React.FC<{ score: any }> = ({ score }) => {
  const { t } = useApp();
  return (
  <div className="space-y-1.5 text-xs text-gray-600">
    {[
      { label: t('progress.grades'),     val: score.grade_score },
      { label: t('progress.attendance'), val: score.attendance_score },
      { label: t('progress.feedback'),   val: score.feedback_score },
      { label: t('progress.trend'),      val: score.trend_score },
    ].map(({ label, val }) => (
      <div key={label} className="flex items-center gap-2">
        <span className="w-32 flex-shrink-0">{label}</span>
        <div className="flex-1"><ProgressBar percent={Math.round(val ?? 0)} showLabel={false} height={4} /></div>
        <span className="w-8 text-right font-semibold text-gray-700">{Math.round(val ?? 0)}</span>
      </div>
    ))}
  </div>
  );
};

/* ── Student view ── */
const StudentView: React.FC<{ userId: string }> = ({ userId }) => {
  const { t } = useApp();
  const [scores, setScores]         = useState<any[]>([]);
  const [predictions, setPreds]     = useState<any[]>([]);
  const [aiInsights, setAiInsights] = useState<any>(null);
  const [loading, setLoading]       = useState(true);
  const [courseNameMap, setCourseNameMap] = useState<Record<string, string>>({});

  useEffect(() => {
    let mounted = true;
    Promise.all([
      apiService.getStudentScores(userId).then(r => { if (mounted) setScores(r.data ?? []); }).catch(() => {}),
      apiService.getAllPredictions(userId).then(r => { if (mounted) setPreds(r.data ?? []); }).catch(() => {}),
      apiService.getStudentAIInsights(userId).then(r => { if (mounted) setAiInsights(r.data); }).catch(() => {}),
      apiService.getDashboard().then(r => {
        if (!mounted) return;
        const map: Record<string, string> = {};
        (r.data?.courses ?? []).forEach((c: any) => { map[c.id] = c.name; });
        setCourseNameMap(map);
      }).catch(() => {}),
    ]).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [userId]);

  if (loading) return <div className="flex justify-center py-16"><div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" /></div>;

  const predMap = Object.fromEntries(predictions.map((p: any) => [p.course_id, p]));

  if (scores.length === 0)
    return (
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center text-gray-400">
        <div className="text-4xl mb-3">📊</div>
        <p className="font-semibold text-gray-600">{t('progress.noData')}</p>
        <p className="text-sm mt-1">{t('progress.noDataHint')}</p>
      </div>
    );

  return (
    <div className="space-y-5">
      {aiInsights?.insights?.length > 0 && (
        <AIInsightPanel
          insights={aiInsights.insights}
          overallTrend={aiInsights.overall_trend}
          hasHighRisk={aiInsights.has_high_risk}
        />
      )}
      {scores.map((s: any) => (
        <div key={s.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-gray-700 truncate max-w-[220px]">{courseNameMap[s.course_id] ?? s.course_id}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-3xl font-black text-gray-900">{(s.score ?? 0).toFixed(1)}</span>
                <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${SCORE_BADGE[s.classification] ?? 'bg-gray-100 text-gray-600'}`}>
                  {labelStr(s.classification ?? '')}
                </span>
              </div>
            </div>
            <div className="w-32">
              <ProgressBar percent={Math.round(s.score ?? 0)} showLabel height={10} />
            </div>
          </div>
          <ScoreBreakdown score={s} />
          {predMap[s.course_id] && (
            <div className="mt-4"><PredictionCard pred={predMap[s.course_id]} /></div>
          )}
        </div>
      ))}
    </div>
  );
};

/* ── Teacher / Admin view ── */
const TeacherAdminView: React.FC<{ data: any }> = ({ data }) => {
  const { t } = useApp();
  const studentProgress: any[] = data?.metrics?.student_progress ?? [];
  const atRisk = studentProgress.filter(s => s.classification === 'needs_attention');
  const good   = studentProgress.filter(s => ['excellent', 'good'].includes(s.classification ?? ''));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: t('progress.totalStudents'),  val: studentProgress.length, color: 'bg-blue-500' },
          { label: t('progress.performingWell'), val: good.length,            color: 'bg-emerald-500' },
          { label: t('progress.needsAttention'), val: atRisk.length,          color: 'bg-red-500' },
        ].map(c => (
          <div key={c.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-xl ${c.color} flex items-center justify-center text-white text-lg font-black`}>{c.val}</div>
            <p className="text-sm font-semibold text-gray-700">{c.label}</p>
          </div>
        ))}
      </div>

      {atRisk.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
          <h3 className="text-sm font-bold text-red-700 mb-3">{t('progress.atRisk')}</h3>
          <div className="space-y-2">
            {atRisk.map((s: any, i: number) => (
              <div key={`${s.student_id}-${i}`} className="flex items-center gap-3 p-2 rounded-lg bg-red-50">
                <span className="text-sm font-semibold text-gray-800 flex-1 truncate">
                  <Link to={`/users/${s.student_id}/profile`} className="hover:underline">{s.student_name}</Link>
                </span>
                <span className="text-xs text-gray-500 truncate max-w-[140px]">{s.course_name}</span>
                <span className="text-sm font-bold text-red-700">{s.score != null ? s.score.toFixed(0) : '—'}</span>
                {s.prediction_label && (
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${PRED_BADGE[s.prediction_label] ?? ''}`}>
                    {PRED_ICON[s.prediction_label]} {labelStr(s.prediction_label)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
        <h3 className="text-sm font-bold text-gray-700 mb-3">{t('progress.allProgress')}</h3>
        {studentProgress.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-8">
            {t('progress.noStudentData')}
          </p>
        ) : (
          <div className="space-y-2">
            {studentProgress.map((s: any, i: number) => (
              <div key={`${s.student_id}-${i}`} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-0">
                <span className="text-sm font-semibold text-gray-800 w-36 flex-shrink-0 truncate">
                  <Link to={`/users/${s.student_id}/profile`} className="hover:underline">{s.student_name}</Link>
                </span>
                <span className="text-xs text-gray-400 flex-1 truncate">{s.course_name}</span>
                <div className="w-28 flex-shrink-0"><ProgressBar percent={Math.round(s.score ?? 0)} showLabel={false} height={5} /></div>
                <span className="text-sm font-bold text-gray-700 w-8 text-right">{s.score != null ? s.score.toFixed(0) : '—'}</span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-20 text-center flex-shrink-0 ${SCORE_BADGE[s.classification] ?? 'bg-gray-100 text-gray-600'}`}>
                  {labelStr(s.classification ?? '—')}
                </span>
                {s.prediction_label && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${PRED_BADGE[s.prediction_label] ?? ''}`}>
                    {PRED_ICON[s.prediction_label]}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ── Parent view ── */
const ParentView: React.FC<{ data: any }> = ({ data }) => {
  const { t } = useApp();
  const children: any[] = data?.metrics?.children ?? [];
  const courseNameMap: Record<string, string> = Object.fromEntries(
    (data?.courses ?? []).map((c: any) => [c.id, c.name])
  );

  if (children.length === 0)
    return (
      <div className="bg-white rounded-2xl p-10 text-center text-gray-400 border border-gray-100">
        <div className="text-4xl mb-3">👨‍👩‍👧</div>
        <p>{t('progress.noChildren')}</p>
      </div>
    );

  return (
    <div className="space-y-6">
      {children.map((child: any) => {
        const scores: any[] = child.performance_scores ?? [];
        const avg = scores.length
          ? scores.reduce((a: number, s: any) => a + (s.score ?? 0), 0) / scores.length
          : null;
        return (
          <div key={child.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-800">{child.name}</h3>
              {avg != null && (
                <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                  avg >= 80 ? SCORE_BADGE.excellent
                  : avg >= 65 ? SCORE_BADGE.good
                  : avg >= 50 ? SCORE_BADGE.average
                  : SCORE_BADGE.needs_attention
                }`}>
                  {t('progress.avg')} {avg.toFixed(0)}/100
                </span>
              )}
            </div>
            {scores.length === 0 ? (
              <p className="text-gray-400 text-sm">{t('progress.noPerformance')}</p>
            ) : (
              <div className="space-y-3">
                {scores.map((s: any) => (
                  <div key={s.course_id}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-gray-700 font-semibold truncate pr-2">{courseNameMap[s.course_id] ?? s.course_id.slice(-8)}</span>
                      <span className={`px-2 py-0.5 rounded-full font-bold ${SCORE_BADGE[s.classification] ?? 'bg-gray-100 text-gray-600'}`}>
                        {(s.score ?? 0).toFixed(0)} — {labelStr(s.classification ?? '')}
                      </span>
                    </div>
                    <ProgressBar percent={Math.round(s.score ?? 0)} showLabel={false} height={5} />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

/* ── Main export ── */
export const ProgressPage: React.FC = () => {
  const { user } = useAuth();
  const { t } = useApp();
  const [dashData, setDashData]     = useState<any>(null);
  const [dashLoading, setDashLoading] = useState(true);

  const role = user?.role ?? 'student';

  useEffect(() => {
    if (role !== 'student') {
      apiService.getDashboard()
        .then(r => setDashData(r.data))
        .catch(() => {})
        .finally(() => setDashLoading(false));
    } else {
      setDashLoading(false);
    }
  }, [role]);

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-black text-gray-900">{t('progress.title')}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {role === 'student' && t('progress.subtitleStudent')}
            {role === 'teacher' && t('progress.subtitleTeacher')}
            {role === 'admin'   && t('progress.subtitleAdmin')}
            {role === 'parent'  && t('progress.subtitleParent')}
          </p>
        </div>

        {dashLoading && role !== 'student' ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {role === 'student'                      && user?.id && <StudentView userId={user.id} />}
            {(role === 'teacher' || role === 'admin') && <TeacherAdminView data={dashData} />}
            {role === 'parent'                       && <ParentView data={dashData} />}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};
