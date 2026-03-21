import React, { useEffect, useState } from 'react';
import { ProgressBar } from './widgets/ProgressBar';
import { apiService } from '../services/apiService';

interface Props {
  studentId: string;
  studentName: string;
  courseId: string;
  currentScore?: number | null;
  currentClassification?: string | null;
  onClose: () => void;
}

const SCORE_BADGE: Record<string, string> = {
  excellent:       'bg-green-100 text-green-700',
  good:            'bg-blue-100 text-blue-700',
  average:         'bg-yellow-100 text-yellow-700',
  needs_attention: 'bg-red-100 text-red-700',
};

const ATT_BADGE: Record<string, string> = {
  present: 'bg-green-100 text-green-700',
  absent:  'bg-red-100 text-red-700',
  late:    'bg-yellow-100 text-yellow-700',
  excused: 'bg-gray-100 text-gray-600',
};

export const StudentProgressModal: React.FC<Props> = ({
  studentId, studentName, courseId, currentScore, currentClassification, onClose,
}) => {
  const [history, setHistory]     = useState<any[]>([]);
  const [attendance, setAttendance] = useState<any[]>([]);
  const [insight, setInsight]     = useState<any>(null);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    const p1 = apiService.getScoreHistory(studentId, courseId, 10)
      .then(r => setHistory(r.data ?? []))
      .catch(() => {});
    const p2 = apiService.getAttendance({ student_id: studentId, course_id: courseId })
      .then(r => setAttendance(r.data ?? []))
      .catch(() => {});
    const p3 = apiService.getFeedbackInsight(studentId, courseId)
      .then(r => setInsight(r.data ?? null))
      .catch(() => {});
    Promise.all([p1, p2, p3]).finally(() => setLoading(false));
  }, [studentId, courseId]);

  const attSummary = attendance.reduce((acc: Record<string, number>, a: any) => {
    const s = a.status?.value ?? a.status ?? 'unknown';
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});

  const totalAtt = attendance.length;
  const presentCount = (attSummary.present ?? 0) + (attSummary.late ?? 0);
  const attRate = totalAtt > 0 ? Math.round((presentCount / totalAtt) * 100) : null;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Progress Summary</h3>
            <p className="text-xs text-gray-500 mt-0.5">{studentName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Current score */}
          {currentScore != null && (
            <div className="flex items-center gap-4 bg-gray-50 rounded-xl p-4">
              <div>
                <p className="text-3xl font-black text-gray-900">{currentScore.toFixed(1)}</p>
                <p className="text-xs text-gray-400 mt-0.5">Current Score</p>
              </div>
              {currentClassification && (
                <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                  SCORE_BADGE[currentClassification] ?? 'bg-gray-100 text-gray-600'
                }`}>
                  {currentClassification.replace('_', ' ')}
                </span>
              )}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-8">
              <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* Attendance summary */}
              {totalAtt > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-600 mb-2">Attendance</h4>
                  <div className="grid grid-cols-4 gap-2 mb-2">
                    {(['present','absent','late','excused'] as const).map(s => (
                      <div key={s} className={`rounded-lg p-2 text-center ${ATT_BADGE[s]}`}>
                        <p className="text-lg font-black">{attSummary[s] ?? 0}</p>
                        <p className="text-[10px] capitalize font-semibold">{s}</p>
                      </div>
                    ))}
                  </div>
                  {attRate != null && (
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-500">Attendance rate</span>
                        <span className="font-semibold text-gray-700">{attRate}%</span>
                      </div>
                      <ProgressBar percent={attRate} showLabel={false} height={5} />
                    </div>
                  )}
                </div>
              )}

              {/* Score history */}
              {history.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-600 mb-2">Score History (recent {history.length})</h4>
                  <div className="space-y-1.5">
                    {history.map((h: any, i: number) => (
                      <div key={h.id || i} className="flex items-center gap-3">
                        <div className="w-16 text-[10px] text-gray-400 flex-shrink-0">
                          {h.computed_at ? new Date(h.computed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—'}
                        </div>
                        <div className="flex-1">
                          <ProgressBar percent={Math.round(h.score ?? 0)} showLabel={false} height={5} />
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full w-12 text-center flex-shrink-0 ${
                          SCORE_BADGE[h.classification] ?? 'bg-gray-100 text-gray-600'
                        }`}>
                          {(h.score ?? 0).toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>
                  {/* Trend */}
                  {history.length >= 2 && (() => {
                    const oldest = history[history.length - 1]?.score ?? 0;
                    const newest = history[0]?.score ?? 0;
                    const diff = newest - oldest;
                    const trendColor = diff > 2 ? 'text-green-600' : diff < -2 ? 'text-red-600' : 'text-gray-500';
                    const trendIcon = diff > 2 ? '↑' : diff < -2 ? '↓' : '→';
                    return (
                      <p className={`text-xs mt-2 font-semibold ${trendColor}`}>
                        Trend: {trendIcon} {Math.abs(diff).toFixed(1)} pts over last {history.length} records
                      </p>
                    );
                  })()}
                </div>
              )}

              {/* Feedback text-analysis insight */}
              {insight?.summary && (
                <div className={`rounded-xl p-3 border text-xs
                  ${insight.dominant_sentiment === 'positive'
                    ? 'bg-green-50 border-green-200 text-green-800'
                    : insight.dominant_sentiment === 'negative'
                    ? 'bg-red-50 border-red-200 text-red-700'
                    : 'bg-blue-50 border-blue-200 text-blue-700'}`}>
                  <p className="font-semibold mb-0.5">Feedback Analysis</p>
                  <p>{insight.summary}</p>
                  {insight.tags && insight.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {insight.tags.map((t: string) => (
                        <span key={t} className="px-1.5 py-0.5 rounded bg-white/60 font-medium capitalize">
                          {t.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                  {insight.contribution != null && (
                    <p className="mt-1 text-[10px] opacity-70">
                      Feedback contribution to score: {insight.contribution}/100
                    </p>
                  )}
                </div>
              )}

              {history.length === 0 && totalAtt === 0 && (
                <p className="text-xs text-gray-400 text-center py-6">No history data available yet.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
