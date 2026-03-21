import React from 'react';
import { useApp } from '../contexts/AppContext';

interface Props {
  insights: string[];
  loading: boolean;
  onRefresh: () => void;
}

export const AIInsightsCard: React.FC<Props> = ({ insights, loading, onRefresh }) => {
  const { t } = useApp();
  return (
    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">🤖</span>
          <h2 className="font-bold text-gray-800 text-sm">{t('ai.dashboardInsights')}</h2>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="text-indigo-600 text-xs hover:underline disabled:opacity-40"
        >
          {loading ? '…' : t('ai.refresh')}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-4">
          <div className="w-5 h-5 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : insights.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-3">{t('ai.insightsFallback')}</p>
      ) : (
        <ul className="space-y-2">
          {insights.map((insight, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-gray-700">
              <span className="text-indigo-400 mt-0.5 flex-shrink-0">•</span>
              <span>{insight}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[10px] text-indigo-400/70 mt-3">{t('ai.generatedFrom')}</p>
    </div>
  );
};
