import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { SendMessageModal } from '../components/SendMessageModal';
import { useAuth } from '../contexts/AuthContext';
import { apiService } from '../services/apiService';

type MsgTab = 'inbox' | 'sent' | 'compose';

interface Message {
  id: string;
  sender_id: string;
  recipient_id: string;
  subject: string;
  content: string;
  message_type: string;
  course_id?: string;
  read_status: boolean;
  created_at: string;
}

interface Contact {
  id: string;
  name: string;
  role: string;
  course_id: string;
  course_name: string;
  student_id?: string;    // parent contacts: which linked child this relates to
  student_name?: string;  // parent contacts: child's display name
}

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60)    return 'just now';
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(dateStr).toLocaleDateString();
}

const TYPE_BADGE: Record<string, string> = {
  general:      'bg-gray-100 text-gray-600',
  academic:     'bg-blue-100 text-blue-700',
  announcement: 'bg-purple-100 text-purple-700',
  alert:        'bg-red-100 text-red-700',
};

export const MessagesPage: React.FC = () => {
  const { user } = useAuth();
  const [tab, setTab]           = useState<MsgTab>('inbox');
  const [inbox, setInbox]       = useState<Message[]>([]);
  const [sent, setSent]         = useState<Message[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading]   = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Compose state
  const [composeTarget, setComposeTarget] = useState<Contact | null>(null);

  // Child filter for parents
  const [childFilter, setChildFilter] = useState<string>('all');

  const role = user?.role ?? 'student';

  const loadInbox = () =>
    apiService.getInbox().then(r => setInbox(r.data ?? [])).catch(() => {});

  const loadSent = () =>
    apiService.getSentMessages().then(r => setSent(r.data ?? [])).catch(() => {});

  const loadContacts = () =>
    apiService.getMessageContacts().then(r => setContacts(r.data?.contacts ?? [])).catch(() => {});

  useEffect(() => {
    setLoading(true);
    Promise.all([loadInbox(), loadSent(), loadContacts()])
      .finally(() => setLoading(false));
  }, []);

  const handleExpand = async (msg: Message) => {
    const isExpanding = expanded !== msg.id;
    setExpanded(isExpanding ? msg.id : null);
    if (isExpanding && !msg.read_status && tab === 'inbox') {
      await apiService.markMessageRead(msg.id).catch(() => {});
      setInbox(prev => prev.map(m => m.id === msg.id ? { ...m, read_status: true } : m));
    }
  };

  // ── Parent-specific derived data ────────────────────────────────────────────
  // Map course_id → { student_id, student_name } — used to show child context on messages
  const courseToChild: Record<string, { student_id: string; student_name: string }> =
    role === 'parent'
      ? Object.fromEntries(
          contacts
            .filter(c => c.student_id && c.student_name)
            .map(c => [c.course_id, { student_id: c.student_id!, student_name: c.student_name! }])
        )
      : {};

  // Unique linked children derived from contacts (no extra API call needed)
  const linkedChildren: { id: string; name: string }[] = role !== 'parent' ? [] :
    Array.from(
      new Map(
        contacts
          .filter(c => c.student_id && c.student_name)
          .map(c => [c.student_id!, c.student_name!])
      ).entries()
    ).map(([id, name]) => ({ id, name }));

  // ── Message filtering ───────────────────────────────────────────────────────
  const rawMessages = tab === 'inbox' ? inbox : sent;
  const messages = (childFilter === 'all' || role !== 'parent')
    ? rawMessages
    : rawMessages.filter(msg => {
        if (!msg.course_id) return false;
        return courseToChild[msg.course_id]?.student_id === childFilter;
      });

  const unreadCount = inbox.filter(m => !m.read_status).length;

  // Contacts filtered by selected child (for compose)
  const visibleContacts = (childFilter === 'all' || role !== 'parent')
    ? contacts
    : contacts.filter(c => c.student_id === childFilter);

  // For display: resolve sender/recipient name from contacts when possible
  const contactMap = Object.fromEntries(contacts.map(c => [c.id, c]));

  const getCounterpartLabel = (msg: Message) => {
    if (tab === 'inbox') {
      return contactMap[msg.sender_id]?.name ?? `User …${msg.sender_id.slice(-6)}`;
    }
    return contactMap[msg.recipient_id]?.name ?? `User …${msg.recipient_id.slice(-6)}`;
  };

  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto">
        <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-black text-gray-900">Messages</h1>
            <p className="text-sm text-gray-400 mt-1">
              Internal platform messages with your {role === 'teacher' ? 'students' : 'teachers'}.
            </p>
          </div>
          {contacts.length > 0 && (
            <button
              onClick={() => setTab('compose')}
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition"
            >
              + New Message
            </button>
          )}
        </div>

        {/* ── Child filter (parents with multiple linked children only) ── */}
        {role === 'parent' && linkedChildren.length > 1 && (
          <div className="mb-4 flex items-center gap-3">
            <span className="text-xs text-gray-500 font-semibold">Filter by child:</span>
            <div className="relative">
              <select
                value={childFilter}
                onChange={e => { setChildFilter(e.target.value); setExpanded(null); }}
                className="bg-white border border-gray-200 rounded-xl px-3 py-1.5 text-xs font-semibold text-gray-800 shadow-sm appearance-none pr-7 focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                <option value="all">All Children</option>
                {linkedChildren.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none text-[10px]">▼</span>
            </div>
            {childFilter !== 'all' && (
              <span className="text-[10px] text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">
                {messages.length} message{messages.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1 mb-5 w-fit">
          {[
            { key: 'inbox' as MsgTab, label: `Inbox${unreadCount > 0 ? ` (${unreadCount})` : ''}` },
            { key: 'sent'  as MsgTab, label: 'Sent' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setExpanded(null); }}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition ${
                tab === t.key ? 'bg-white text-blue-700 shadow' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : tab === 'compose' ? (
          /* ── Compose panel ── */
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-gray-800 text-sm">New Message</h2>
              <button onClick={() => setTab('inbox')} className="text-xs text-gray-400 hover:text-gray-600">← Back to inbox</button>
            </div>
            {visibleContacts.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">
                No contacts available yet. You need to share an active course with someone to message them.
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-gray-500 mb-3">Select a recipient:</p>
                {visibleContacts.map((c, i) => (
                  <button
                    key={i}
                    onClick={() => setComposeTarget(c)}
                    className="w-full flex items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 text-left transition"
                  >
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-300 to-purple-400 flex items-center justify-center text-white font-bold text-xs flex-shrink-0">
                      {c.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-gray-800 truncate">{c.name}</p>
                      <p className="text-[10px] text-gray-400 truncate capitalize">
                        {c.role} · {c.course_name}
                        {c.student_name ? ` · for ${c.student_name}` : ''}
                      </p>
                    </div>
                    <span className="text-xs text-blue-600 font-semibold">Message →</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* ── Inbox / Sent list ── */
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
            {messages.length === 0 ? (
              <div className="p-10 text-center text-gray-400">
                <div className="text-4xl mb-3">✉</div>
                <p className="font-semibold text-gray-600">No messages yet</p>
                <p className="text-sm mt-1">
                  {tab === 'inbox' ? 'Messages from teachers or students will appear here.' : 'Messages you send will appear here.'}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {messages.map(msg => {
                  const childContext = role === 'parent' && msg.course_id
                    ? courseToChild[msg.course_id]
                    : null;
                  return (
                    <div key={msg.id}>
                      <button
                        onClick={() => handleExpand(msg)}
                        className={`w-full flex items-start gap-3 px-5 py-4 text-left transition hover:bg-gray-50 ${
                          !msg.read_status && tab === 'inbox' ? 'bg-blue-50/40' : ''
                        }`}
                      >
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-300 to-purple-400 flex items-center justify-center text-white font-bold text-xs flex-shrink-0 mt-0.5">
                          {getCounterpartLabel(msg).slice(0, 2).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                            <span className={`text-xs font-semibold truncate ${!msg.read_status && tab === 'inbox' ? 'text-gray-900' : 'text-gray-700'}`}>
                              {getCounterpartLabel(msg)}
                            </span>
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${TYPE_BADGE[msg.message_type] ?? TYPE_BADGE.general}`}>
                              {msg.message_type}
                            </span>
                            {/* Child context badge — only shown for parents */}
                            {childContext && (
                              <span className="text-[10px] font-medium text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded-full flex-shrink-0">
                                {childContext.student_name}
                              </span>
                            )}
                            {!msg.read_status && tab === 'inbox' && (
                              <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                            )}
                          </div>
                          <p className={`text-xs truncate ${!msg.read_status && tab === 'inbox' ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
                            {msg.subject}
                          </p>
                          <p className="text-[10px] text-gray-400 mt-0.5">{timeAgo(msg.created_at)}</p>
                        </div>
                      </button>
                      {expanded === msg.id && (
                        <div className="px-5 pb-4 bg-gray-50 border-t border-gray-100">
                          <p className="text-xs font-semibold text-gray-700 py-3">{msg.subject}</p>
                          <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                          {tab === 'inbox' && (
                            <div className="mt-3 pt-3 border-t border-gray-100">
                              <button
                                onClick={() => {
                                  // Prefer the contact that matches both sender AND course (important for parents
                                  // whose teacher might teach multiple linked children)
                                  const contact =
                                    contacts.find(c => c.id === msg.sender_id && c.course_id === msg.course_id) ??
                                    contacts.find(c => c.id === msg.sender_id);
                                  if (contact) setComposeTarget(contact);
                                }}
                                className="text-xs text-blue-600 hover:underline font-semibold"
                              >
                                ↩ Reply
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Compose modal triggered from inbox reply or compose list */}
      {composeTarget && (
        <SendMessageModal
          recipientId={composeTarget.id}
          recipientName={composeTarget.name}
          courseId={composeTarget.course_id}
          courseName={composeTarget.course_name}
          onClose={() => setComposeTarget(null)}
          onSent={() => {
            setComposeTarget(null);
            setTab('sent');
            loadSent();
          }}
        />
      )}
    </DashboardLayout>
  );
};
