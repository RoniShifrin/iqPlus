import React, { useState } from 'react';
import { apiService } from '../services/apiService';

interface Props {
  recipientId: string;
  recipientName: string;
  courseId?: string;
  courseName?: string;
  onClose: () => void;
  onSent?: () => void;
}

const MSG_TYPES = [
  { value: 'general',      label: 'General'      },
  { value: 'academic',     label: 'Academic'     },
  { value: 'announcement', label: 'Announcement' },
] as const;

export const SendMessageModal: React.FC<Props> = ({
  recipientId, recipientName, courseId, courseName, onClose, onSent,
}) => {
  const [subject, setSubject]       = useState('');
  const [content, setContent]       = useState('');
  const [msgType, setMsgType]       = useState<string>('general');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [success, setSuccess]       = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiService.sendMessage({
        recipient_id: recipientId,
        subject: subject.trim(),
        content: content.trim(),
        message_type: msgType,
        course_id: courseId || undefined,
      });
      setSuccess(true);
      setTimeout(() => {
        onSent?.();
        onClose();
      }, 800);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to send message.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Send Message</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              To: <strong>{recipientName}</strong>
              {courseName && <span className="text-gray-400"> · {courseName}</span>}
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
          <div className="py-8 text-center">
            <p className="text-2xl mb-2">✓</p>
            <p className="text-sm font-semibold text-green-600">Message sent!</p>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                value={msgType}
                onChange={e => setMsgType(e.target.value)}
              >
                {MSG_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Subject</label>
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder="Message subject…"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                required
                maxLength={200}
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Message</label>
              <textarea
                rows={5}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                placeholder="Write your message…"
                value={content}
                onChange={e => setContent(e.target.value)}
                required
                minLength={1}
                maxLength={5000}
              />
            </div>

            {error && (
              <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{error}</p>
            )}

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
                {loading ? 'Sending…' : 'Send Message'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
