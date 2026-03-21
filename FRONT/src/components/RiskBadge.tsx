import React from 'react';

interface RiskBadgeProps {
  riskLevel: 'low' | 'medium' | 'high' | string;
  predictionLabel?: string;
  size?: 'xs' | 'sm';
}

const RISK_STYLES: Record<string, string> = {
  high:   'bg-red-100 text-red-700 border border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  low:    'bg-green-100 text-green-700 border border-green-200',
};

const RISK_ICONS: Record<string, string> = {
  high:   '🔴',
  medium: '🟡',
  low:    '🟢',
};

const PRED_ICONS: Record<string, string> = {
  likely_improving:   '↑',
  likely_stable:      '→',
  at_risk:            '⚠',
  needs_intervention: '🚨',
};

export const RiskBadge: React.FC<RiskBadgeProps> = ({ riskLevel, predictionLabel, size = 'xs' }) => {
  const styles = RISK_STYLES[riskLevel] ?? RISK_STYLES.low;
  const icon   = RISK_ICONS[riskLevel]  ?? '⚪';
  const predIcon = predictionLabel ? (PRED_ICONS[predictionLabel] ?? '') : '';

  const textClass = size === 'sm' ? 'text-[11px]' : 'text-[10px]';

  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full font-semibold ${textClass} ${styles}`}>
      {icon} {riskLevel} risk{predIcon ? ` ${predIcon}` : ''}
    </span>
  );
};
