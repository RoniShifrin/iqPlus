import React from 'react';

interface Props {
  percent: number;   // 0-100
  size?: number;     // px, default 140
  stroke?: number;   // stroke width, default 12
}

function getLevel(p: number): { label: string; color: string; textColor: string } {
  if (p >= 85) return { label: 'Excellent', color: '#10b981', textColor: 'text-emerald-600' };
  if (p >= 70) return { label: 'Good',      color: '#3b82f6', textColor: 'text-blue-600' };
  if (p >= 50) return { label: 'Average',   color: '#f97316', textColor: 'text-orange-500' };
  return             { label: 'Needs Help', color: '#ef4444', textColor: 'text-red-500' };
}

export const CircularProgress: React.FC<Props> = ({ percent, size = 140, stroke = 12 }) => {
  const r      = (size - stroke) / 2;
  const circ   = 2 * Math.PI * r;
  const offset = circ - (percent / 100) * circ;
  const cx     = size / 2;
  const { label, color, textColor } = getLevel(percent);

  // Scale font sizes proportionally to the circle so text never overflows at small sizes
  const pctFontPx  = Math.max(10, Math.floor(size * 0.17));
  const lblFontPx  = Math.max(7,  Math.floor(size * 0.08));
  const showLabel  = size >= 90;   // omit label on tiny circles — it's unreadable and clutters the ring

  return (
    <div className="flex flex-col items-center">
      <div style={{ width: size, height: size }} className="relative">
        <svg width={size} height={size}>
          {/* Track */}
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
          {/* Progress */}
          <circle
            cx={cx} cy={cx} r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${cx} ${cx})`}
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        </svg>
        {/* Center text — sizes scale with the circle diameter */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span
            style={{ fontSize: pctFontPx + 'px', lineHeight: 1 }}
            className="font-black text-gray-900"
          >
            {percent}%
          </span>
          {showLabel && (
            <span
              style={{ fontSize: lblFontPx + 'px', lineHeight: 1 }}
              className={`font-bold uppercase tracking-wide ${textColor}`}
            >
              {label}
            </span>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 space-y-1 text-xs">
        {[
          { l: 'Excellent',  c: '#10b981', min: 85 },
          { l: 'Good',       c: '#3b82f6', min: 70 },
          { l: 'Average',    c: '#f97316', min: 50 },
          { l: 'Below Average', c: '#ef4444', min: 0 },
        ].map(item => (
          <div key={item.l} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.c }} />
            <span className="text-gray-500">{item.l}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
