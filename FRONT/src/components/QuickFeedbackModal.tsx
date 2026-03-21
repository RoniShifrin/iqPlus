import React, { useState } from 'react';
import { apiService } from '../services/apiService';
import { useApp } from '../contexts/AppContext';

interface Props {
  studentId: string;
  studentName: string;
  courseId?: string;
  courses?: { id: string; name: string }[];
  onClose: () => void;
  onSaved?: () => void;
}

export const QuickFeedbackModal: React.FC<Props> = ({
  studentId, studentName, courseId: prefillCourseId, courses = [], onClose, onSaved,
}) => {
  const { t } = useApp();
  const [form, setForm] = useState({
    course_id: prefillCourseId || '',
    sentiment: 'positive',
    content: '',
    visibility: 'private',
    delivery_target: 'none',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // AI suggest state
  const [aiTone, setAiTone] = useState<'encouraging' | 'formal' | 'constructive'>('constructive');
  const [aiGenerating, setAiGenerating] = useState(false);

  const handleSuggest = async () => {
    const courseId = form.course_id || prefillCourseId;
    if (!courseId) { setError('Please select a course first.'); return; }
    setAiGenerating(true);
    setError(null);
    try {
      const res = await apiService.suggestFeedback({ student_id: studentId, course_id: courseId, tone: aiTone });
      setForm(f => ({ ...f, content: res.data.suggested_text }));
    } catch {
      setError('Could not generate suggestion. Please write feedback manually.');
    } finally {
      setAiGenerating(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.course_id) { setError('Please select a course.'); return; }
    setLoading(true);
    setError(null);
    try {
      await apiService.submitFeedback({ student_id: studentId, ...form });
      setSaved(true);
      setTimeout(() => {
        onSaved?.();
        onClose();
      }, 900);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to submit feedback.');
    } finally {
      setLoading(false);
    }
  };

  const prefilledCourseName = courses.find(c => c.id === prefillCourseId)?.name;

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Quick Feedback</h3>
            <p className="text-xs text-gray-500 mt-0.5">For: <strong>{studentName}</strong></p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100">&times;</button>
        </div>

        <form onSubmit={submit} className="space-y-3 text-sm">
          {prefillCourseId ? (
            <div className="bg-blue-50 rounded-lg px-3 py-2">
              <p className="text-xs text-blue-700 font-semibold">{prefilledCourseName ?? prefillCourseId}</p>
            </div>
          ) : (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Course</label>
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.course_id}
                onChange={e => setForm(f => ({ ...f, course_id: e.target.value }))}
                required
              >
                <option value="">Select course…</option>
                {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Sentiment</label>
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.sentiment}
                onChange={e => setForm(f => ({ ...f, sentiment: e.target.value }))}
              >
                {['positive', 'neutral', 'negative'].map(s => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Visibility</label>
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.visibility}
                onChange={e => setForm(f => ({ ...f, visibility: e.target.value }))}
              >
                <option value="private">Private</option>
                <option value="published">Published</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Deliver to</label>
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={form.delivery_target}
                onChange={e => setForm(f => ({ ...f, delivery_target: e.target.value }))}
              >
                {[['none','None'],['student','Student'],['parent','Parent'],['both','Both']].map(([v,l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
          </div>

          {/* AI Suggest row */}
          <div className="flex items-center gap-2 bg-indigo-50 rounded-lg px-3 py-2">
            <span className="text-xs text-indigo-500 font-semibold flex-shrink-0">🤖 AI</span>
            <select
              value={aiTone}
              onChange={e => setAiTone(e.target.value as any)}
              className="flex-1 border border-indigo-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white"
            >
              <option value="constructive">{t('ai.tone.constructive')}</option>
              <option value="encouraging">{t('ai.tone.encouraging')}</option>
              <option value="formal">{t('ai.tone.formal')}</option>
            </select>
            <button
              type="button"
              onClick={handleSuggest}
              disabled={aiGenerating}
              className="flex-shrink-0 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold px-3 py-1 rounded-lg transition"
            >
              {aiGenerating ? t('ai.suggesting') : t('ai.suggestFeedback')}
            </button>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1">Feedback</label>
            <textarea
              rows={4}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
              placeholder="Enter feedback (min 10 characters)…"
              value={form.content}
              onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
              required
              minLength={10}
            />
          </div>

          {saved && <p className="text-xs text-green-700 bg-green-50 rounded-lg px-3 py-2 font-semibold">✓ Feedback submitted successfully!</p>}
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
                {loading ? 'Submitting…' : 'Submit Feedback'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
