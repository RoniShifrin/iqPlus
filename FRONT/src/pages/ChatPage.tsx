import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { apiService } from '../services/apiService';

interface Conversation {
  id: string;
  type: 'direct' | 'course';
  participant_ids: string[];
  course_id?: string;
  other_participant_name?: string;
  other_participant_avatar_url?: string | null;
  course_name?: string;
  last_message_at: string;
  last_message_preview?: string;
  unread_count: number;
  created_at: string;
}

interface ChatMessage {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_name: string;
  sender_avatar_url?: string | null;
  content: string;
  read_by: string[];
  created_at: string;
}

interface Contact {
  id: string;
  name: string;
  role: string;
  course_id?: string;
  course_name?: string;
  last_active_at?: string | null;
}

interface PresenceMap {
  [userId: string]: { is_online: boolean; last_active_at?: string | null };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function convLabel(conv: Conversation): string {
  if (conv.type === 'course') return conv.course_name ?? 'Course Chat';
  return conv.other_participant_name ?? 'Direct';
}

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

function initials(name: string): string {
  return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
}

/** Renders an avatar circle: real image if url is present, initials fallback otherwise. */
function AvatarCircle({ name, url, size, bg = 'bg-blue-500' }: { name: string; url?: string | null; size: number; bg?: string }) {
  if (url) {
    return (
      <img
        src={`${API_URL}${url}`}
        alt={name}
        className="rounded-full object-cover flex-shrink-0"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className={`rounded-full flex items-center justify-center text-white font-bold flex-shrink-0 ${bg}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
    >
      {initials(name)}
    </div>
  );
}

/** Returns true if last_active_at is within 5 minutes of now. */
function isOnlineFromDate(dateStr?: string | null): boolean {
  if (!dateStr) return false;
  return Date.now() - new Date(dateStr).getTime() < 5 * 60 * 1000;
}

// ── Component ─────────────────────────────────────────────────────────────────

const ChatPage: React.FC = () => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);

  // New chat panel
  const [showNewChat, setShowNewChat] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [letterFilter, setLetterFilter] = useState<string | null>(null);
  const [loadingContacts, setLoadingContacts] = useState(false);

  // Presence map: userId → { is_online, last_active_at }
  const [presence, setPresence] = useState<PresenceMap>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Course scope from URL: if ?course_id= is set, New Chat is filtered to that course
  const courseScopeId = searchParams.get('course_id') || null;

  // ── Load conversations ────────────────────────────────────────────────────
  const loadConversations = async () => {
    setLoadingConvs(true);
    try {
      const r = await apiService.getConversations();
      setConversations(r.data);
    } catch {
    } finally {
      setLoadingConvs(false);
    }
  };

  useEffect(() => { loadConversations(); }, []);

  // ── Handle URL params ─────────────────────────────────────────────────────
  useEffect(() => {
    const userId = searchParams.get('user_id');
    const courseId = searchParams.get('course_id');
    const convId = searchParams.get('conv_id');

    if (convId) {
      selectConversation(convId);
    } else if (userId) {
      openOrCreate('direct', { participant_id: userId });
    } else if (courseId) {
      openOrCreate('course', { course_id: courseId });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // ── Open or create conversation ───────────────────────────────────────────
  const openOrCreate = async (
    type: 'direct' | 'course',
    params: { participant_id?: string; course_id?: string },
  ) => {
    try {
      const r = await apiService.startConversation({ type, ...params });
      const conv: Conversation = r.data;
      setConversations(prev => {
        const exists = prev.find(c => c.id === conv.id);
        if (exists) return prev;
        return [conv, ...prev];
      });
      selectConversation(conv.id);
    } catch {
      // permission denied — silently ignore
    }
  };

  // ── Select & load messages ────────────────────────────────────────────────
  const selectConversation = async (convId: string) => {
    if (selectedId === convId) return;
    setSelectedId(convId);
    setMessages([]);
    setLoadingMsgs(true);
    try {
      const r = await apiService.getChatMessages(convId);
      setMessages(r.data);
      await apiService.markConversationRead(convId);
      setConversations(prev =>
        prev.map(c => c.id === convId ? { ...c, unread_count: 0 } : c)
      );
      // Fetch presence for the other participant (direct chats only)
      const conv = conversations.find(c => c.id === convId);
      if (conv?.type === 'direct') {
        const otherId = conv.participant_ids.find(p => p !== user?.id);
        if (otherId) fetchPresence([otherId]);
      }
    } catch {
    } finally {
      setLoadingMsgs(false);
    }
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Presence helpers ──────────────────────────────────────────────────────
  const fetchPresence = async (userIds: string[]) => {
    if (!userIds.length) return;
    try {
      const r = await apiService.getChatPresence(userIds);
      const map: PresenceMap = {};
      (r.data as any[]).forEach(p => {
        map[p.user_id] = { is_online: p.is_online, last_active_at: p.last_active_at };
      });
      setPresence(prev => ({ ...prev, ...map }));
    } catch {
      // non-critical — ignore
    }
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const sendMessage = async () => {
    if (!draft.trim() || !selectedId || sending) return;
    const content = draft.trim();
    setDraft('');
    setSending(true);
    try {
      const r = await apiService.sendChatMessage(selectedId, content);
      const newMsg: ChatMessage = r.data;
      setMessages(prev => [...prev, newMsg]);
      setConversations(prev =>
        prev.map(c =>
          c.id === selectedId
            ? { ...c, last_message_preview: content, last_message_at: newMsg.created_at }
            : c
        )
      );
    } catch {
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Load contacts for new chat ────────────────────────────────────────────
  const openNewChat = async () => {
    setShowNewChat(true);
    setContactSearch('');
    setLetterFilter(null);
    setContacts([]);
    setLoadingContacts(true);
    try {
      // If we have a course scope (navigated from a course), filter contacts to that course
      const r = await apiService.getChatContacts(courseScopeId || undefined);
      const loaded: Contact[] = r.data;
      setContacts(loaded);
      // Seed presence from last_active_at already in the contacts response
      const map: PresenceMap = {};
      loaded.forEach(c => {
        map[c.id] = { is_online: isOnlineFromDate(c.last_active_at), last_active_at: c.last_active_at };
      });
      setPresence(prev => ({ ...prev, ...map }));
    } catch {
    } finally {
      setLoadingContacts(false);
    }
  };

  const filteredContacts = contacts.filter(c => {
    // Letter shortcut: first character of the contact's name must match
    if (letterFilter && !c.name.toUpperCase().startsWith(letterFilter)) return false;
    // Text search: name or course contains the query
    const q = contactSearch.toLowerCase();
    return !q ||
      c.name.toLowerCase().includes(q) ||
      (c.course_name ?? '').toLowerCase().includes(q);
  });

  const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
  // Letters that have at least one contact — used to dim letters with no matches
  const activeLetters = new Set(contacts.map(c => c.name.charAt(0).toUpperCase()));

  const selectedConv = conversations.find(c => c.id === selectedId);
  const totalUnread = conversations.reduce((sum, c) => sum + c.unread_count, 0);

  // Presence for the selected direct chat partner
  const otherParticipantId = selectedConv?.type === 'direct'
    ? selectedConv.participant_ids.find(p => p !== user?.id)
    : undefined;
  const otherPresence = otherParticipantId ? presence[otherParticipantId] : undefined;

  return (
    <DashboardLayout>
      <div className="flex h-[calc(100vh-80px)] bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">

        {/* ── Left panel: conversation list ────────────────────────────── */}
        <div className="w-72 flex-shrink-0 border-r border-gray-100 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <span className="font-bold text-gray-800 text-sm">Chat</span>
              {totalUnread > 0 && (
                <span className="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">
                  {totalUnread}
                </span>
              )}
              {courseScopeId && (
                <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-semibold">
                  course
                </span>
              )}
            </div>
            <button
              onClick={openNewChat}
              title="New conversation"
              className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-600 transition"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 3H5a2 2 0 00-2 2v14l4-4h12a2 2 0 002-2V5a2 2 0 00-2-2zm-7 3a1 1 0 011 1v2h2a1 1 0 010 2h-2v2a1 1 0 01-2 0v-2H9a1 1 0 010-2h2V7a1 1 0 011-1z"/>
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loadingConvs ? (
              <div className="py-10 text-center text-xs text-gray-400">Loading…</div>
            ) : conversations.length === 0 ? (
              <div className="py-10 text-center text-xs text-gray-400 px-4">
                No conversations yet.<br />Press + to start one.
              </div>
            ) : (
              conversations.map(conv => {
                const isSelected = selectedId === conv.id;
                // Show presence dot for direct chats
                const otherId = conv.type === 'direct'
                  ? conv.participant_ids.find(p => p !== user?.id)
                  : undefined;
                const online = otherId ? presence[otherId]?.is_online ?? false : false;

                return (
                  <button
                    key={conv.id}
                    onClick={() => selectConversation(conv.id)}
                    className={`w-full flex items-start gap-3 px-4 py-3 border-b border-gray-50 text-left transition ${
                      isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    {/* Avatar with presence ring */}
                    <div className="relative flex-shrink-0">
                      <AvatarCircle
                        name={conv.type === 'course' ? (conv.course_name ?? '##') : (conv.other_participant_name ?? '?')}
                        url={conv.type === 'direct' ? conv.other_participant_avatar_url : null}
                        size={36}
                        bg={conv.type === 'course' ? 'bg-green-500' : 'bg-blue-500'}
                      />
                      {conv.type === 'direct' && (
                        <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white ${
                          online ? 'bg-green-400' : 'bg-gray-300'
                        }`} />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className={`text-xs font-semibold truncate ${conv.unread_count > 0 ? 'text-gray-900' : 'text-gray-700'}`}>
                          {convLabel(conv)}
                        </span>
                        <span className="text-[10px] text-gray-400 flex-shrink-0">{timeAgo(conv.last_message_at)}</span>
                      </div>
                      <div className="flex items-center justify-between mt-0.5">
                        <p className={`text-[11px] truncate ${conv.unread_count > 0 ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>
                          {conv.last_message_preview ?? 'No messages yet'}
                        </p>
                        {conv.unread_count > 0 && (
                          <span className="ml-1 min-w-[16px] h-4 bg-blue-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center px-1 flex-shrink-0">
                            {conv.unread_count > 9 ? '9+' : conv.unread_count}
                          </span>
                        )}
                      </div>
                      {conv.type === 'course' && (
                        <p className="text-[10px] text-gray-400">Course Chat</p>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ── Right panel: message thread ───────────────────────────────── */}
        {selectedConv ? (
          <div className="flex-1 flex flex-col min-w-0">
            {/* Thread header */}
            <div className="flex items-center gap-3 px-5 py-3 border-b border-gray-100 bg-white">
              <div className="relative flex-shrink-0">
                <AvatarCircle
                  name={selectedConv.type === 'course' ? (selectedConv.course_name ?? '##') : (selectedConv.other_participant_name ?? '?')}
                  url={selectedConv.type === 'direct' ? selectedConv.other_participant_avatar_url : null}
                  size={32}
                  bg={selectedConv.type === 'course' ? 'bg-green-500' : 'bg-blue-500'}
                />
                {selectedConv.type === 'direct' && (
                  <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white ${
                    otherPresence?.is_online ? 'bg-green-400' : 'bg-gray-300'
                  }`} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-gray-800 truncate">{convLabel(selectedConv)}</p>
                {selectedConv.type === 'direct' && (
                  <p className={`text-[11px] ${otherPresence?.is_online ? 'text-green-500' : 'text-gray-400'}`}>
                    {otherPresence?.is_online
                      ? 'Online'
                      : otherPresence?.last_active_at
                        ? `Last seen ${timeAgo(otherPresence.last_active_at)} ago`
                        : 'Offline'}
                  </p>
                )}
                {selectedConv.type === 'course' && (
                  <p className="text-[11px] text-gray-400">Course Chat</p>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3 bg-gray-50/30">
              {loadingMsgs ? (
                <div className="py-10 text-center text-xs text-gray-400">Loading messages…</div>
              ) : messages.length === 0 ? (
                <div className="py-10 text-center text-xs text-gray-400">No messages yet. Say hello!</div>
              ) : (
                messages.map((msg, idx) => {
                  const isMe = msg.sender_id === user?.id;
                  const showSenderLabel = !isMe && (
                    idx === 0 || messages[idx - 1].sender_id !== msg.sender_id
                  );
                  const showTimestamp =
                    idx === messages.length - 1 ||
                    messages[idx + 1].sender_id !== msg.sender_id;

                  return (
                    <div key={msg.id} className={`flex items-end gap-2 ${isMe ? 'flex-row-reverse' : 'flex-row'}`}>
                      {/* Avatar — only show when sender changes */}
                      <div className={`flex-shrink-0 ${showTimestamp ? 'opacity-100' : 'opacity-0'}`}>
                        <AvatarCircle
                          name={msg.sender_name}
                          url={msg.sender_avatar_url}
                          size={28}
                          bg={isMe ? 'bg-blue-500' : 'bg-gray-400'}
                        />
                      </div>
                      <div className={`max-w-xs lg:max-w-md ${isMe ? 'items-end' : 'items-start'} flex flex-col`}>
                        {showSenderLabel && (
                          <p className="text-[10px] text-gray-400 mb-0.5 px-1">{msg.sender_name}</p>
                        )}
                        <div className={`rounded-2xl px-3 py-2 text-sm leading-relaxed break-words ${
                          isMe
                            ? 'bg-blue-600 text-white rounded-br-sm'
                            : 'bg-white text-gray-800 rounded-bl-sm shadow-sm border border-gray-100'
                        }`}>
                          {msg.content}
                        </div>
                        {showTimestamp && (
                          <p className="text-[10px] text-gray-400 mt-0.5 px-1">{formatTime(msg.created_at)}</p>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Send box */}
            <div className="px-5 py-3 border-t border-gray-100 bg-white flex items-end gap-2">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Write a message… (Enter to send, Shift+Enter for newline)"
                rows={1}
                className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-32 overflow-y-auto"
                style={{ minHeight: '40px' }}
              />
              <button
                onClick={sendMessage}
                disabled={!draft.trim() || sending}
                className="w-9 h-9 flex items-center justify-center rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition disabled:opacity-40 flex-shrink-0"
                title="Send (Enter)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" className="opacity-20 mb-3">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
            <p className="text-sm font-medium text-gray-500">Select a conversation</p>
            <p className="text-xs mt-1 text-gray-400">or press + to start a new one</p>
          </div>
        )}
      </div>

      {/* ── New chat panel ──────────────────────────────────────────────── */}
      {showNewChat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 w-80 max-h-[70vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div>
                <span className="font-bold text-sm text-gray-800">New Conversation</span>
                {courseScopeId && (
                  <span className="ml-2 text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-semibold">
                    course members only
                  </span>
                )}
              </div>
              <button onClick={() => setShowNewChat(false)} className="text-gray-400 hover:text-gray-600 transition text-lg leading-none">×</button>
            </div>
            <div className="px-4 py-2 border-b border-gray-50 space-y-2">
              <input
                type="text"
                placeholder="Search people…"
                value={contactSearch}
                onChange={e => { setContactSearch(e.target.value); setLetterFilter(null); }}
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              {/* A–Z alphabet shortcuts */}
              <div className="flex flex-wrap gap-0.5">
                {ALPHABET.map(letter => {
                  const isSelected = letterFilter === letter;
                  const hasContacts = activeLetters.has(letter);
                  return (
                    <button
                      key={letter}
                      onClick={() => {
                        setContactSearch('');
                        setLetterFilter(isSelected ? null : letter);
                      }}
                      disabled={!hasContacts && !loadingContacts}
                      title={hasContacts ? `People starting with ${letter}` : `No contacts starting with ${letter}`}
                      className={`w-[22px] h-[22px] rounded text-[10px] font-semibold transition flex items-center justify-center ${
                        isSelected
                          ? 'bg-blue-600 text-white'
                          : hasContacts
                          ? 'bg-gray-100 text-gray-700 hover:bg-blue-100 hover:text-blue-700'
                          : 'text-gray-300 cursor-default'
                      }`}
                    >
                      {letter}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loadingContacts ? (
                <div className="py-8 text-center text-xs text-gray-400">Loading…</div>
              ) : filteredContacts.length === 0 ? (
                <div className="py-8 text-center text-xs text-gray-400">No contacts available</div>
              ) : (
                filteredContacts.map((c, i) => {
                  const online = presence[c.id]?.is_online ?? isOnlineFromDate(c.last_active_at);
                  return (
                    <button
                      key={`${c.id}-${c.course_id ?? i}`}
                      onClick={() => {
                        setShowNewChat(false);
                        openOrCreate('direct', { participant_id: c.id });
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 border-b border-gray-50 text-left hover:bg-gray-50 transition"
                    >
                      <div className="relative flex-shrink-0">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-[10px] font-bold ${
                          c.role === 'teacher' ? 'bg-orange-400' : 'bg-indigo-400'
                        }`}>
                          {initials(c.name)}
                        </div>
                        <span className={`absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white ${
                          online ? 'bg-green-400' : 'bg-gray-300'
                        }`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-gray-800 truncate">{c.name}</p>
                        <p className="text-[10px] text-gray-400 truncate">
                          {c.role.charAt(0).toUpperCase() + c.role.slice(1)}
                          {c.course_name ? ` · ${c.course_name}` : ''}
                        </p>
                      </div>
                      <span className={`text-[10px] flex-shrink-0 ${online ? 'text-green-500' : 'text-gray-400'}`}>
                        {online ? 'Online' : 'Offline'}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
};

export default ChatPage;
