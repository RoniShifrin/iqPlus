import React from 'react';

interface AIInsightPanelProps {
  insights: string[];
  overallTrend?: string;
  hasHighRisk?: boolean;
  loading?: boolean;
  compact?: boolean;
}

const TREND_BADGE: Record<string, string> = {
  improving: 'bg-emerald-100 text-emerald-700',
  declining: 'bg-red-100 text-red-700',
  stable:    'bg-blue-100 text-blue-700',
};

const TREND_ICON: Record<string, string> = {
  improving: '↑',
  declining: '↓',
  stable:    '→',
};

export const AIInsightPanel: React.FC<AIInsightPanelProps> = ({
  insights,
  overallTrend,
  hasHighRisk,
  loading,
  compact,
}) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
        <span className="text-xs text-gray-400">Loading AI insights…</span>
      </div>
    );
  }

  if (!insights || insights.length === 0) {
    return (
      <div className="rounded-xl border border-gray-100 bg-gray-50 p-3 text-xs text-gray-400">
        No AI insights available yet. Record grades or attendance to generate analysis.
      </div>
    );
  }

  const borderColor = hasHighRisk
    ? 'border-red-200 bg-red-50'
    : overallTrend === 'improving'
    ? 'border-emerald-200 bg-emerald-50'
    : 'border-blue-100 bg-blue-50';

  return (
    <div className={`rounded-xl border ${borderColor} ${compact ? 'p-3' : 'p-4'}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-gray-600 uppercase tracking-wide">AI Insights</span>
        {overallTrend && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TREND_BADGE[overallTrend] ?? 'bg-gray-100 text-gray-500'}`}>
            {TREND_ICON[overallTrend] ?? ''} {overallTrend}
          </span>
        )}
        {hasHighRisk && (
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-200 text-red-800 ml-auto">
            High Risk
          </span>
        )}
      </div>
      <ul className={`space-y-1 ${compact ? 'text-[10px]' : 'text-xs'} text-gray-700`}>
        {insights.map((text, i) => (
          <li key={i} className="flex items-start gap-1.5">
            <span className="text-blue-400 flex-shrink-0 mt-px">•</span>
            <span>{text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
