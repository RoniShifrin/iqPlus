import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

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

type FilterTab = 'all' | 'unread';

const NotificationsPage: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterTab>('all');
  const navigate = useNavigate();
  const { t } = useApp();

  const timeAgo = (dateStr: string): string => {
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return t('notifications.justNow');
    if (diff < 3600) return `${Math.floor(diff / 60)}${t('notifications.mAgo')}`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}${t('notifications.hAgo')}`;
    return `${Math.floor(diff / 86400)}${t('notifications.dAgo')}`;
  };

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiService.getAllNotifications(200);
      setNotifications(r.data);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const markRead = async (id: string) => {
    await apiService.markNotificationRead(id);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read_status: true } : n));
  };

  const markAllRead = async () => {
    await apiService.markAllRead();
    setNotifications(prev => prev.map(n => ({ ...n, read_status: true })));
  };

  const handleClick = async (n: Notification) => {
    if (!n.read_status) await markRead(n.id);
    // Navigate to related entity if applicable
    if (n.related_entity_type === 'message') {
      navigate('/messages');
    } else if (n.course_id && n.related_entity_type === 'feedback') {
      navigate(`/courses/${n.course_id}`);
    } else if (n.course_id) {
      navigate(`/courses/${n.course_id}`);
    }
  };

  const visible = filter === 'unread'
    ? notifications.filter(n => !n.read_status)
    : notifications;

  const unreadCount = notifications.filter(n => !n.read_status).length;

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t('notifications.title')}</h1>
          {unreadCount > 0 && (
            <p className="text-sm text-gray-500 mt-0.5">{unreadCount} {t('notifications.unread')}</p>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            className="text-sm text-blue-600 hover:underline font-medium"
          >
            {t('notifications.markAllRead')}
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-100">
        {(['all', 'unread'] as FilterTab[]).map(tab => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition border-b-2 -mb-px ${
              filter === tab
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'all' ? t('notifications.filterAll') : t('notifications.filterUnread')}
            {tab === 'unread' && unreadCount > 0 && (
              <span className="ml-1.5 bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5">
                {unreadCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="py-16 text-center text-sm text-gray-400">{t('common.loading')}</div>
        ) : visible.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-400">
            {filter === 'unread' ? t('notifications.noUnread') : t('notifications.none')}
          </div>
        ) : (
          visible.map((n, i) => (
            <div
              key={n.id}
              onClick={() => handleClick(n)}
              className={`flex items-start gap-3 px-5 py-4 cursor-pointer transition ${
                i < visible.length - 1 ? 'border-b border-gray-50' : ''
              } ${n.read_status ? 'bg-white hover:bg-gray-50' : 'bg-blue-50 hover:bg-blue-100'}`}
            >
              <span className="text-xl flex-shrink-0 mt-0.5">{TYPE_ICON[n.type] ?? '🔔'}</span>
              <div className="flex-1 min-w-0">
                {n.title && (
                  <p className={`text-sm font-semibold leading-snug ${n.read_status ? 'text-gray-500' : 'text-gray-800'}`}>
                    {n.title}
                  </p>
                )}
                <p className={`text-sm leading-relaxed ${n.title ? 'opacity-75' : ''} ${n.read_status ? 'text-gray-500' : 'text-gray-800 font-medium'}`}>
                  {enrollmentText(n, t)}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">{timeAgo(n.created_at)}</p>
              </div>
              {!n.read_status && (
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500 flex-shrink-0 mt-1.5" />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default NotificationsPage;
