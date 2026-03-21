import React, { useState } from 'react';
import { apiService } from '../services/apiService';

const DIMENSIONS = [
  { key: 'report_clarity',      label: 'Report Clarity'      },
  { key: 'dashboard_usability', label: 'Dashboard Usability' },
  { key: 'navigation_ease',     label: 'Navigation Ease'     },
] as const;

type Dim = typeof DIMENSIONS[number]['key'];

const StarRow: React.FC<{ label: string; value: number; onChange: (v: number) => void }> = ({ label, value, onChange }) => (
  <div className="flex items-center justify-between gap-2">
    <span className="text-xs text-gray-600 w-36">{label}</span>
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(star => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          className={`text-lg leading-none transition ${star <= value ? 'text-yellow-400' : 'text-gray-200 hover:text-yellow-300'}`}
        >
          ★
        </button>
      ))}
    </div>
  </div>
);

export const UsabilityWidget: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [ratings, setRatings] = useState<Record<Dim, number>>({
    report_clarity: 0,
    dashboard_usability: 0,
    navigation_ease: 0,
  });
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const allRated = Object.values(ratings).every(v => v > 0);

  const submit = async () => {
    if (!allRated) return;
    setSubmitting(true);
    try {
      await apiService.submitUsabilityFeedback({
        ...ratings,
        comment: comment.trim() || undefined,
      });
      setDone(true);
      setTimeout(() => { setOpen(false); setDone(false); }, 1800);
    } catch {
      // silent fail — widget is non-critical
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {open ? (
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-4 w-72">
          <div className="flex items-center justify-between mb-3">
            <span className="font-bold text-gray-800 text-sm">Rate your experience</span>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
          </div>

          {done ? (
            <p className="text-center text-green-600 text-sm py-4">Thank you for your feedback!</p>
          ) : (
            <>
              <div className="space-y-2 mb-3">
                {DIMENSIONS.map(d => (
                  <StarRow
                    key={d.key}
                    label={d.label}
                    value={ratings[d.key]}
                    onChange={v => setRatings(r => ({ ...r, [d.key]: v }))}
                  />
                ))}
              </div>
              <textarea
                rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none mb-3"
                placeholder="Optional comment…"
                value={comment}
                onChange={e => setComment(e.target.value)}
                maxLength={500}
              />
              <button
                onClick={submit}
                disabled={!allRated || submitting}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg transition"
              >
                {submitting ? 'Sending…' : 'Submit'}
              </button>
            </>
          )}
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          title="Rate this page"
          className="w-10 h-10 bg-white border border-gray-200 shadow-lg rounded-full flex items-center justify-center text-lg hover:bg-gray-50 transition"
        >
          ★
        </button>
      )}
    </div>
  );
};
