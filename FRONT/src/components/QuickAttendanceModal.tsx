import React, { useState } from 'react';
import { apiService } from '../services/apiService';

interface Props {
  studentId: string;
  studentName: string;
  courseId: string;
  onClose: () => void;
  onSaved?: () => void;
}

const STATUSES = ['present', 'absent', 'late', 'excused'] as const;
type AttStatus = typeof STATUSES[number];

const STATUS_STYLE: Record<AttStatus, string> = {
  present: 'bg-green-50 border-green-300 text-green-700 hover:bg-green-100',
  absent:  'bg-red-50 border-red-300 text-red-700 hover:bg-red-100',
  late:    'bg-yellow-50 border-yellow-300 text-yellow-700 hover:bg-yellow-100',
  excused: 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100',
};

export const QuickAttendanceModal: React.FC<Props> = ({
  studentId, studentName, courseId, onClose, onSaved,
}) => {
  const today = new Date().toISOString().split('T')[0];
  const [status, setStatus] = useState<AttStatus>('present');
  const [date, setDate] = useState(today);
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Guard: all required fields must be present
    if (!studentId || !courseId || !date || !status) {
      setError('Missing required fields. Please fill in all fields.');
      return;
    }

    setLoading(true);
    setError(null);

    // Backend AttendanceCreate.date expects a full ISO datetime string, not a date-only string.
    // Sending "2026-03-18" would trigger a Pydantic v2 validation error (422).
    const isoDate = `${date}T00:00:00.000Z`;

    const payload = {
      student_id: studentId,
      course_id:  courseId,
      status,
      date:       isoDate,
      remarks:    notes || undefined,
    };

    try {
      await apiService.recordAttendance(payload);
      setSaved(true);
      setTimeout(() => {
        if (onSaved) { onSaved(); } else { onClose(); }
      }, 900);
    } catch (err: any) {
      console.error('[QuickAttendanceModal] API error:', err);
      // FastAPI 422 returns detail as an array of objects — always stringify safely
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: any) => d?.msg ?? String(d)).join('; ')
          : 'Failed to record attendance.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Record Attendance</h3>
            <p className="text-xs text-gray-500 mt-0.5">{studentName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100"
          >
            &times;
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Date</label>
            <input
              type="date"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
              value={date}
              max={today}
              onChange={e => setDate(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-2">Status</label>
            <div className="grid grid-cols-2 gap-2">
              {STATUSES.map(s => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  className={`border rounded-lg py-2 text-xs font-semibold capitalize transition ${STATUS_STYLE[s]} ${
                    status === s ? 'ring-2 ring-offset-1 ring-current' : ''
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Notes (optional)</label>
            <input
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
              placeholder="e.g. arrived 10 minutes late"
              value={notes}
              onChange={e => setNotes(e.target.value)}
            />
          </div>

          {saved && <p className="text-xs text-green-700 bg-green-50 rounded-lg px-3 py-2 font-semibold">✓ Attendance recorded successfully!</p>}
          {error && <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>}

          {!saved && (
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 border border-gray-200 text-gray-600 text-xs py-2 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold py-2 rounded-lg transition"
              >
                {loading ? 'Saving…' : 'Save Attendance'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
