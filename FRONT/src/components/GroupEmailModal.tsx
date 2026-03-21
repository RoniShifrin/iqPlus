import React, { useState } from 'react';
import { apiService } from '../services/apiService';

interface Props {
  courseId: string;
  courseName: string;
  studentCount: number;
  onClose: () => void;
}

export const GroupEmailModal: React.FC<Props> = ({
  courseId, courseName, studentCount, onClose,
}) => {
  const [form, setForm] = useState({ subject: '', content: '', include_parents: false });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<{ sent: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const r = await apiService.announceCourse(courseId, {
        subject: form.subject,
        content: form.content,
        include_parents: form.include_parents,
      });
      setSuccess({ sent: r.data.sent_count ?? studentCount });
      setTimeout(onClose, 2000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to send group email.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Group Email</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {courseName} · {studentCount} student{studentCount !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100"
          >
            &times;
          </button>
        </div>

        {success ? (
          <div className="text-center py-8">
            <div className="text-4xl mb-3">✅</div>
            <p className="text-sm font-semibold text-green-600">
              Sent to {success.sent} recipient{success.sent !== 1 ? 's' : ''}!
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3 text-sm">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Subject</label>
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder="Subject…"
                value={form.subject}
                onChange={e => setForm(f => ({ ...f, subject: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Message</label>
              <textarea
                rows={5}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                placeholder="Write your message to all students…"
                value={form.content}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                required
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                className="rounded"
                checked={form.include_parents}
                onChange={e => setForm(f => ({ ...f, include_parents: e.target.checked }))}
              />
              <span className="text-xs text-gray-600">Also send to linked parents</span>
            </label>
            <p className="text-[10px] text-gray-400 bg-gray-50 rounded-lg px-3 py-2">
              Sends an email to all enrolled students
              {form.include_parents ? ' and their linked parents' : ''}.
            </p>
            {error && <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
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
                {loading ? 'Sending…' : '✉ Send to All'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
