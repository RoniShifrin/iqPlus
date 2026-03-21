import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';
import { safeStorage } from '../utils/safeStorage';

interface Notification {
  id: string;
  message: string;
  type: string;
  title?: string;
  course_id?: string;
  related_entity_type?: string;
  related_entity_id?: string;
  read_status: boolean;
  created_at: string;
}

/** For enrollment approval/rejection, show a translated body when the course name (title) is available.
 *  Falls back to the stored English message for older notifications that have no title. */
function enrollmentText(n: Notification, t: (k: string) => string): string {
  if (!n.title) return n.message;
  if (n.type === 'enrollment_approved') return t('notif.enrollmentApproved');
  if (n.type === 'enrollment_rejected') return t('notif.enrollmentRejected');
  return n.message;
}

const TYPE_ICON: Record<string, string> = {
  ai_alert: '🤖',
  course_published: '📚',
  enrollment_approved: '✅',
  enrollment_rejected: '❌',
  enrollment_pending: '⏳',
  feedback_added: '💬',
  schedule_changed: '📅',
  message_received: '✉️',
};

function timeAgoRaw(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
}

/** Play a short two-tone alert beep using the Web Audio API — no external file needed. */
function playAlertBeep() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    [880, 1100].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = 'sine';
      gain.gain.setValueAtTime(0.18, ctx.currentTime + i * 0.12);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.18);
      osc.start(ctx.currentTime + i * 0.12);
      osc.stop(ctx.currentTime + i * 0.12 + 0.18);
    });
  } catch {}
}

const SOUND_PREF_KEY = 'iqplus_notification_sound';

export const NotificationPanel: React.FC = () => {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(
    () => safeStorage.getItem(SOUND_PREF_KEY) !== 'off'
  );
  const panelRef = useRef<HTMLDivElement>(null);
  /** Track AI alert IDs we've already played a sound for. */
  const seenAlertIds = useRef<Set<string>>(new Set());

  const timeAgo = (dateStr: string): string => {
    const diff = timeAgoRaw(dateStr);
    if (diff < 60) return t('notifications.justNow');
    if (diff < 3600) return `${Math.floor(diff / 60)}${t('notifications.mAgo')}`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}${t('notifications.hAgo')}`;
    return `${Math.floor(diff / 86400)}${t('notifications.dAgo')}`;
  };

  const toggleSound = () => {
    setSoundEnabled(prev => {
      const next = !prev;
      safeStorage.setItem(SOUND_PREF_KEY, next ? 'on' : 'off');
      return next;
    });
  };

  const fetchCount = async () => {
    try {
      const r = await apiService.getUnreadCount();
      setUnread(r.data.count);
    } catch {}
  };

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const r = await apiService.getNotifications();
      const fetched: Notification[] = r.data;
      // Play sound once per new unread AI alert
      let newAlert = false;
      fetched.forEach(n => {
        if (n.type === 'ai_alert' && !n.read_status && !seenAlertIds.current.has(n.id)) {
          seenAlertIds.current.add(n.id);
          newAlert = true;
        }
      });
      if (newAlert && soundEnabled) playAlertBeep();
      setNotifications(fetched);
    } catch {} finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCount();
    fetchNotifications(); // initial fetch to populate seenAlertIds
    const interval = setInterval(async () => {
      await fetchCount();
      await fetchNotifications(); // also re-check for new AI alerts
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (open) fetchNotifications();
  }, [open]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markRead = async (id: string) => {
    await apiService.markNotificationRead(id);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read_status: true } : n));
    setUnread(prev => Math.max(0, prev - 1));
  };

  const markAllRead = async () => {
    await apiService.markAllRead();
    setNotifications(prev => prev.map(n => ({ ...n, read_status: true })));
    setUnread(0);
  };

  return (
    <div className="relative" ref={panelRef}>
      {/* Bell button */}
      <button
        onClick={() => setOpen(o => !o)}
        className="relative flex items-center justify-center w-8 h-8 rounded-lg text-gray-500 hover:bg-gray-100 transition"
        aria-label="Notifications"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
        </svg>
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-10 w-80 bg-white rounded-2xl shadow-xl border border-gray-100 z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-50">
            <span className="font-bold text-gray-800 text-sm">{t('notifications.title')}</span>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleSound}
                title={soundEnabled ? t('notifications.muteSound') : t('notifications.enableSound')}
                className="text-gray-400 hover:text-gray-600 transition"
              >
                {soundEnabled ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                  </svg>
                )}
              </button>
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs text-blue-600 hover:underline">
                  {t('notifications.markAllReadShort')}
                </button>
              )}
            </div>
          </div>

          <div className="max-h-64 overflow-y-auto">
            {loading ? (
              <div className="py-8 text-center text-xs text-gray-400">{t('common.loading')}</div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center text-xs text-gray-400">{t('notifications.none')}</div>
            ) : (
              notifications.map(n => (
                <div
                  key={n.id}
                  onClick={() => !n.read_status && markRead(n.id)}
                  className={`flex items-start gap-3 px-4 py-3 border-b border-gray-50 cursor-pointer transition ${
                    n.read_status ? 'bg-white' : 'bg-blue-50 hover:bg-blue-100'
                  }`}
                >
                  <span className="text-lg flex-shrink-0 mt-0.5">{TYPE_ICON[n.type] ?? '🔔'}</span>
                  <div className="flex-1 min-w-0">
                    {n.title && (
                      <p className={`text-xs font-semibold leading-snug ${n.read_status ? 'text-gray-500' : 'text-gray-800'}`}>
                        {n.title}
                      </p>
                    )}
                    <p className={`text-xs leading-relaxed ${n.title ? 'opacity-75' : ''} ${n.read_status ? 'text-gray-500' : 'text-gray-800 font-medium'}`}>
                      {enrollmentText(n, t)}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">{timeAgo(n.created_at)}</p>
                  </div>
                  {!n.read_status && (
                    <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 mt-1" />
                  )}
                </div>
              ))
            )}
          </div>
          <div className="px-4 py-2.5 border-t border-gray-50 text-center">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="text-xs text-blue-600 hover:underline font-semibold"
            >
              {t('notifications.viewAll')}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
