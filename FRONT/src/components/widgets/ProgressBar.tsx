import React from 'react';

interface Props {
  percent: number;
  showLabel?: boolean;
  height?: number;
}

function barColor(p: number) {
  if (p >= 85) return 'bg-emerald-500';
  if (p >= 70) return 'bg-blue-500';
  if (p >= 50) return 'bg-orange-400';
  return 'bg-red-400';
}

function levelLabel(p: number) {
  if (p >= 85) return 'Excellent';
  if (p >= 70) return 'Good';
  if (p >= 50) return 'Average';
  return 'Needs Help';
}

function labelColor(p: number) {
  if (p >= 85) return 'bg-emerald-100 text-emerald-700';
  if (p >= 70) return 'bg-blue-100 text-blue-700';
  if (p >= 50) return 'bg-orange-100 text-orange-700';
  return 'bg-red-100 text-red-600';
}

export const ProgressBar: React.FC<Props> = ({ percent, showLabel = true, height = 6 }) => (
  <div className="flex items-center gap-3">
    <div className="flex-1 bg-gray-100 rounded-full overflow-hidden" style={{ height }}>
      <div
        className={`h-full rounded-full transition-all ${barColor(percent)}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
    {showLabel && (
      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${labelColor(percent)}`}>
        {percent}% · {levelLabel(percent)}
      </span>
    )}
  </div>
);

export { levelLabel, labelColor, barColor };
