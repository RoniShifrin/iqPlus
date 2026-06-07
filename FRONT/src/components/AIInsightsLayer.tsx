import React, { useEffect, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

// ── Card skeleton shared by all 3 insight cards ────────────────────────────

interface CardProps {
  title: string;
  icon: string;
  children: React.ReactNode;
  accent?: string;
}

const InsightCard: React.FC<CardProps> = ({ title, icon, children, accent = 'from-sky-50 to-blue-50 border-sky-100' }) => (
  <div className={`bg-gradient-to-br ${accent} rounded-2xl border p-5`}>
    <div className="flex items-center gap-2 mb-3">
      <span className="text-base">{icon}</span>
      <h3 className="font-bold text-gray-800 text-sm">{title}</h3>
    </div>
    {children}
  </div>
);

const Spinner = () => (
  <div className="flex justify-center py-4">
    <div className="w-5 h-5 border-4 border-sky-400 border-t-transparent rounded-full animate-spin" />
  </div>
);

// ── Weekly Summary Card ────────────────────────────────────────────────────

interface WeeklySummaryProps {
  studentId?: string;
  courseId?: string;
}

const WeeklySummaryCard: React.FC<WeeklySummaryProps> = ({ studentId, courseId }) => {
  const { t, lang } = useApp();
  const [summary, setSummary]   = useState<string | null>(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(false);
    setSummary(null);
    apiService.getWeeklySummary({ student_id: studentId, course_id: courseId })
      .then(r => {
        if (!mounted) return;
        setSummary(r.data?.summary ?? null);
      })
      .catch(() => { if (mounted) setError(true); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [studentId, courseId, lang]);

  return (
    <InsightCard
      title={t('ail.weeklySummaryTitle')}
      icon="📅"
      accent="from-sky-50 to-blue-50 border-sky-100"
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <p className="text-xs text-red-400 text-center py-2">{t('ail.error')}</p>
      ) : !summary ? (
        <p className="text-xs text-gray-400 text-center py-2">{t('ail.noData')}</p>
      ) : (
        <p className="text-xs text-gray-700 leading-relaxed">{summary}</p>
      )}
      {!loading && !error && (
        <p className="text-[10px] text-sky-400/70 mt-3">{t('ail.basedOnData')}</p>
      )}
    </InsightCard>
  );
};

// ── Score Explanation Card ─────────────────────────────────────────────────

interface ScoreExplainProps {
  studentId: string;
  courseId?: string;
}

const CLASSIFICATION_STYLE: Record<string, string> = {
  excellent:       'bg-green-100 text-green-700',
  good:            'bg-blue-100 text-blue-700',
  average:         'bg-yellow-100 text-yellow-700',
  needs_attention: 'bg-red-100 text-red-700',
};

const ScoreExplanationCard: React.FC<ScoreExplainProps> = ({ studentId, courseId }) => {
  const { t, lang } = useApp();
  const [scores, setScores]   = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(false);

  useEffect(() => {
    if (!studentId) { setLoading(false); return; }
    let mounted = true;
    setLoading(true);
    setError(false);
    apiService.getScoreExplanation(studentId, courseId)
      .then(r => {
        if (!mounted) return;
        setScores(r.data?.scores ?? []);
      })
      .catch(() => { if (mounted) setError(true); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [studentId, courseId, lang]);

  return (
    <InsightCard
      title={t('ail.scoreExplainTitle')}
      icon="📊"
      accent="from-violet-50 to-purple-50 border-violet-100"
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <p className="text-xs text-red-400 text-center py-2">{t('ail.error')}</p>
      ) : scores.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-2">{t('ail.noData')}</p>
      ) : (
        <div className="space-y-3">
          {scores.slice(0, courseId ? 1 : 3).map((s: any, i: number) => (
            <div key={i}>
              {!courseId && (
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-semibold text-gray-500">
                    Course {i + 1} — {s.score}/100
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${CLASSIFICATION_STYLE[s.classification] ?? ''}`}>
                    {s.classification?.replace('_', ' ')}
                  </span>
                </div>
              )}
              {courseId && (
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xl font-black text-gray-800">{s.score}/100</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${CLASSIFICATION_STYLE[s.classification] ?? ''}`}>
                    {s.classification?.replace('_', ' ')}
                  </span>
                </div>
              )}
              <p className="text-xs text-gray-700 leading-relaxed">{s.score_explanation}</p>
            </div>
          ))}
        </div>
      )}
      {!loading && !error && scores.length > 0 && (
        <p className="text-[10px] text-violet-400/70 mt-3">{t('ail.basedOnData')}</p>
      )}
    </InsightCard>
  );
};

// ── Action Items Card ──────────────────────────────────────────────────────

interface ActionItemsProps {
  studentId?: string;
  courseId?: string;
}

const ActionItemsCard: React.FC<ActionItemsProps> = ({ studentId, courseId }) => {
  const { t, lang } = useApp();
  const [items, setItems]     = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(false);
    apiService.getActionItems({ student_id: studentId, course_id: courseId })
      .then(r => {
        if (!mounted) return;
        setItems(r.data?.items ?? []);
      })
      .catch(() => { if (mounted) setError(true); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [studentId, courseId, lang]);

  return (
    <InsightCard
      title={t('ail.actionItemsTitle')}
      icon="✅"
      accent="from-emerald-50 to-green-50 border-emerald-100"
    >
      {loading ? (
        <Spinner />
      ) : error ? (
        <p className="text-xs text-red-400 text-center py-2">{t('ail.error')}</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-2">{t('ail.noData')}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
              <span className="text-emerald-500 mt-0.5 flex-shrink-0 font-bold">{i + 1}.</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
      {!loading && !error && (
        <p className="text-[10px] text-emerald-400/70 mt-3">{t('ail.recommendations')}</p>
      )}
    </InsightCard>
  );
};

// ── Public composite component ─────────────────────────────────────────────

export type AIInsightsLayerRole = 'student' | 'parent' | 'teacher' | 'admin';

interface AIInsightsLayerProps {
  /** The authenticated user's ID — used for score explanation (student/parent context) */
  userId: string;
  /** Optional: narrow scope to one course */
  courseId?: string;
  /** Optional: for parent role, the selected child's ID */
  childStudentId?: string;
  /** Show score explanation card only for student/parent roles */
  showScoreExplain?: boolean;
}

/**
 * Renders Weekly Summary, Score Explanation, and Action Items cards.
 * Each card independently loads and fails gracefully — never blocks the dashboard.
 */
export const AIInsightsLayer: React.FC<AIInsightsLayerProps> = ({
  userId,
  courseId,
  childStudentId,
  showScoreExplain = true,
}) => {
  const scoreStudentId = childStudentId ?? userId;

  return (
    <div className="space-y-4">
      <WeeklySummaryCard studentId={childStudentId} courseId={courseId} />
      {showScoreExplain && (
        <ScoreExplanationCard studentId={scoreStudentId} courseId={courseId} />
      )}
      <ActionItemsCard studentId={childStudentId} courseId={courseId} />
    </div>
  );
};
