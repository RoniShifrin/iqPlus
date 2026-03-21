import React, { useState } from 'react';
import { apiService } from '../services/apiService';

interface Props {
  recipientId: string;
  recipientName: string;
  recipientType: 'student' | 'parent';
  onClose: () => void;
}

export const QuickEmailModal: React.FC<Props> = ({
  recipientId, recipientName, recipientType, onClose,
}) => {
  const [form, setForm] = useState({ subject: '', content: '' });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiService.sendMessage({
        recipient_id: recipientId,
        subject: form.subject,
        content: form.content,
        message_type: 'academic',
        send_email: true,
      });
      setSuccess(true);
      setTimeout(onClose, 1800);
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
            <h3 className="font-bold text-gray-800 text-sm">
              {recipientType === 'parent' ? `Email Parent of ${recipientName}` : `Email ${recipientName}`}
            </h3>
            <p className="text-xs text-gray-400 capitalize mt-0.5">{recipientType}</p>
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
            <p className="text-sm font-semibold text-green-600">Message sent!</p>
            <p className="text-xs text-gray-400 mt-1">Email delivered to {recipientType}</p>
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
                placeholder="Write your message…"
                value={form.content}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                required
              />
            </div>
            <p className="text-[10px] text-gray-400 bg-gray-50 rounded-lg px-3 py-2">
              This message will be sent via email and stored in the inbox.
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
                {loading ? 'Sending…' : '✉ Send Email'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
