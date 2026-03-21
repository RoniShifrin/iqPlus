import React from 'react';

interface FeedbackEntry {
  id: string;
  student_id?: string;
  sentiment: string;
  content: string;
  visibility?: string;
  submitted_at?: string;
}

interface Props {
  studentId: string;
  studentName: string;
  feedback: FeedbackEntry[];
  onClose: () => void;
}

const SENTIMENT_BADGE: Record<string, string> = {
  positive: 'bg-green-100 text-green-700',
  neutral:  'bg-gray-100 text-gray-600',
  negative: 'bg-red-100 text-red-700',
};

const SENTIMENT_ICON: Record<string, string> = {
  positive: '✅',
  neutral:  '➖',
  negative: '⚠️',
};

export const FeedbackHistoryModal: React.FC<Props> = ({
  studentId, studentName, feedback, onClose,
}) => {
  // Filter to this student's feedback, newest first
  const entries = [...feedback]
    .filter(f => !f.student_id || f.student_id === studentId)
    .sort((a, b) => {
      const da = a.submitted_at ? new Date(a.submitted_at).getTime() : 0;
      const db = b.submitted_at ? new Date(b.submitted_at).getTime() : 0;
      return db - da;
    });

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div>
            <h3 className="font-bold text-gray-800 text-sm">Feedback History</h3>
            <p className="text-xs text-gray-500 mt-0.5">{studentName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {entries.length === 0 ? (
            <div className="text-center py-10 text-gray-400">
              <div className="text-3xl mb-2">💬</div>
              <p className="text-sm">No feedback recorded for this student yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {entries.map((f, i) => (
                <div key={f.id || i} className="border border-gray-100 rounded-xl p-3.5">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="text-sm">{SENTIMENT_ICON[f.sentiment] ?? '💬'}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      SENTIMENT_BADGE[f.sentiment] ?? 'bg-gray-100 text-gray-600'
                    }`}>
                      {f.sentiment}
                    </span>
                    {f.visibility && (
                      <span className="text-[10px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
                        {f.visibility}
                      </span>
                    )}
                    {f.submitted_at && (
                      <span className="text-[10px] text-gray-400 ml-auto">
                        {new Date(f.submitted_at).toLocaleDateString(undefined, {
                          year: 'numeric', month: 'short', day: 'numeric',
                        })}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-700 leading-relaxed">{f.content}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 text-center">
            {entries.length} feedback record{entries.length !== 1 ? 's' : ''} total
          </p>
        </div>
      </div>
    </div>
  );
};
