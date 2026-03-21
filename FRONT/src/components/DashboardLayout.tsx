import React, { ReactNode, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import type { Lang } from '../i18n/translations';
import { apiService } from '../services/apiService';
import { AvatarUpload } from './AvatarUpload';
import { NotificationPanel } from './NotificationPanel';
import { SearchBar } from './SearchBar';

/* ── SVG Icons ── */
const IconHome: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>);
const IconSchedule: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3h-1V1h-2v2H8V1H6v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm0 16H5V8h14v11zM7 10h5v5H7z"/></svg>);
const IconCourses: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l11 6 9-4.91V17h2V9L12 3zm-9 7.18v4.44l9 4.9 9-4.9v-4.44L12 15.1 3 10.18z"/></svg>);
const IconProgress: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M3.5 18.5l6-6 4 4L22 6.92 20.59 5.5l-7.09 8-4-4L2 17l1.5 1.5z"/></svg>);
const IconStudents: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>);
const IconTeachers: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>);
const IconMaterials: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>);
const IconSettings: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94s-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54C14.43 2.17 14.22 2 14 2h-4c-.22 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.27.41.49.41h4c.22 0 .43-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>);
const IconProfile: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>);
const IconMessages: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>);
const IconLogout: React.FC = () => (<svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>);
const IconPlanner: React.FC = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z"/></svg>);

/* NAV — labelKey is the default label, parentLabelKey overrides for parent role */
interface NavItem {
  labelKey: string;
  parentLabelKey?: string;
  href: string;
  Icon: React.FC;
  roles: string[];
  exact?: boolean;
}

const NAV: NavItem[] = [
  { labelKey: 'nav.dashboard',  href: '/dashboard',  Icon: IconHome,      roles: ['admin','teacher','student','parent'], exact: true },
  { labelKey: 'nav.schedule',   href: '/schedule',   Icon: IconSchedule,  roles: ['teacher','student','parent'] },
  { labelKey: 'nav.courses',    href: '/courses',    Icon: IconCourses,   roles: ['admin','teacher','student','parent'] },
  { labelKey: 'nav.students',   href: '/students',   Icon: IconStudents,  roles: ['admin','teacher'] },
  { labelKey: 'nav.teachers',   href: '/teachers',   Icon: IconTeachers,  roles: ['admin'] },
  { labelKey: 'nav.materials',  href: '/materials',  Icon: IconMaterials, roles: ['student','parent'] },
  { labelKey: 'planner.nav',    href: '/planner',    Icon: IconPlanner,   roles: ['student','parent'] },
  { labelKey: 'nav.progress',   href: '/progress',   Icon: IconProgress,  roles: ['admin','teacher','student','parent'] },
  { labelKey: 'nav.chat',       href: '/chat',        Icon: IconMessages,  roles: ['admin','teacher','student'] },
  { labelKey: 'nav.profile',    href: '/profile',    Icon: IconProfile,   roles: ['admin','teacher','student','parent'] },
  { labelKey: 'nav.settings',   href: '/settings',   Icon: IconSettings,  roles: ['admin','teacher','student','parent'] },
];

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const AvatarBubble: React.FC<{ name: string; url?: string | null; size?: number }> = ({ name, url, size = 34 }) => {
  const initials = name.split(' ').map((w: string) => w[0]).join('').toUpperCase().slice(0, 2);
  return url ? (
    <img src={`${API_URL}${url}`} alt={name} className="rounded-full object-cover ring-2 ring-white/30" style={{ width: size, height: size }} />
  ) : (
    <div className="rounded-full bg-blue-500 flex items-center justify-center text-white font-bold ring-2 ring-white/20" style={{ width: size, height: size, fontSize: size * 0.35 }}>
      {initials || '?'}
    </div>
  );
};

export interface Tab { key: string; label: string }

interface Props {
  children: ReactNode;
  tabs?: Tab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
}

interface CourseShortcut { id: string; name: string; code: string }

export const DashboardLayout: React.FC<Props> = ({ children, tabs, activeTab, onTabChange }) => {
  const { user, logout } = useAuth();
  const { t, lang, theme, setLang, setTheme } = useApp();
  const navigate = useNavigate();
  const location = useLocation();

  /* ── Course shortcuts — refreshed on visibility change for teacher/student ── */
  const [courseShortcuts, setCourseShortcuts] = useState<CourseShortcut[]>([]);
  useEffect(() => {
    if (!user?.id || !['teacher', 'student', 'parent'].includes(user.role ?? '')) return;
    const fetchShortcuts = () => {
      apiService.getMyCourses()
        .then(r => {
          const list: CourseShortcut[] = (r.data ?? []).map((c: any) => ({
            id: c.id, name: c.name, code: c.code,
          }));
          setCourseShortcuts(list);
        })
        .catch(() => {});
    };
    fetchShortcuts();
    const onVisible = () => { if (document.visibilityState === 'visible') fetchShortcuts(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [user?.id]);

  const role = user?.role || 'student';
  const displayName = user?.display_name || [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || '';
  const firstName = displayName.split(' ')[0];
  const dashPath = ({
    admin: '/dashboard/admin', teacher: '/dashboard/teacher',
    student: '/dashboard/student', parent: '/dashboard/parent',
  } as Record<string, string>)[role] || '/';

  const getNavHref = (item: NavItem): string => {
    if (item.exact) return dashPath;
    const tabMap: Record<string, string> = {
      '/schedule':  `${dashPath}?tab=schedule`,
      '/students':  `${dashPath}?tab=students`,
      '/teachers':  `${dashPath}?tab=teachers`,
    };
    return tabMap[item.href] ?? item.href;
  };

  const isActive = (item: NavItem) => {
    if (item.exact) {
      if (!location.pathname.startsWith('/dashboard')) return false;
      // Don't highlight Dashboard when a sidebar-mapped tab owns the current view
      const currentTab = new URLSearchParams(location.search).get('tab') ?? '';
      const sidebarMappedTabs = new Set(['schedule', 'students', 'teachers']);
      return !sidebarMappedTabs.has(currentTab);
    }
    const tabForHref: Record<string, string> = {
      '/schedule': 'schedule', '/students': 'students', '/teachers': 'teachers',
    };
    if (tabForHref[item.href]) {
      return location.pathname.startsWith('/dashboard') &&
             new URLSearchParams(location.search).get('tab') === tabForHref[item.href];
    }
    return location.pathname.startsWith(item.href);
  };

  const handleLogout = async () => { await logout(); navigate('/login'); };

  const roleLabel = role === 'admin' ? t('topbar.adminDashboard') : t(`role.${role}`);

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-page)' }}>
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 flex flex-col shadow-lg" style={{ background: 'var(--bg-sidebar)' }}>
        <div className="px-5 py-4 flex items-center gap-2 border-b border-white/10">
          <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center"><span className="text-white font-black text-xs">iQ</span></div>
          <span className="text-white font-black text-sm">plus<sup className="text-orange-300 text-xs">+</sup></span>
        </div>

        <div className="px-4 py-2">
          <span className="text-blue-300 text-xs font-semibold uppercase tracking-wider">{t('nav.myDashboard')}</span>
        </div>

        <nav className="flex-1 px-2 py-1 space-y-0.5">
          {NAV.filter(n => n.roles.includes(role)).map(item => {
            const active = isActive(item);
            return (
              <Link
                key={item.labelKey + item.href}
                to={getNavHref(item)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all ${
                  active ? 'bg-white/15 text-white font-semibold' : 'text-blue-200/80 hover:bg-white/8 hover:text-white'
                }`}
              >
                <span className={active ? 'text-orange-300' : 'text-blue-300'}><item.Icon /></span>
                {t(item.labelKey)}
              </Link>
            );
          })}
        </nav>

        {/* ── Course shortcuts (teacher / student / parent) ── */}
        {courseShortcuts.length > 0 && (
          <div className="px-2 pb-2 border-t border-white/10 pt-2">
            <span className="px-3 text-blue-300/70 text-[10px] font-semibold uppercase tracking-wider">
              {t('nav.myCourses')}
            </span>
            <div className="mt-1 space-y-0.5">
              {courseShortcuts.map(c => {
                const active = location.pathname === `/courses/${c.id}`;
                return (
                  <Link
                    key={c.id}
                    to={`/courses/${c.id}`}
                    title={c.name}
                    className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs transition-all ${
                      active ? 'bg-white/15 text-white font-semibold' : 'text-blue-200/80 hover:bg-white/8 hover:text-white'
                    }`}
                  >
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${
                      active ? 'bg-orange-400/80 text-white' : 'bg-white/10 text-blue-300'
                    }`}>
                      {c.code.slice(0, 6)}
                    </span>
                    <span className="truncate">{c.name}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-3 mb-3">
            <AvatarUpload size={36} />
            <div className="overflow-hidden">
              <p className="text-white text-xs font-semibold truncate">{firstName}</p>
              <p className="text-blue-300 text-xs capitalize">{t(`role.${role}`)}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-2 px-3 py-2 w-full rounded-lg text-xs text-blue-200 hover:bg-white/10 hover:text-white transition">
            <IconLogout /> {t('nav.logout')}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between shadow-sm flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center"><span className="text-white font-black text-xs">iQ</span></div>
              <span className="font-black text-sm text-gray-800">plus<sup className="text-orange-400 text-xs">+</sup></span>
            </div>
            <span className="text-gray-200 text-lg">|</span>
            <span className="font-semibold text-gray-600 text-sm">{roleLabel}</span>
          </div>

          <div className="flex items-center gap-3">
            <SearchBar />

            {/* ── Language + Theme quick toggles ─────────────────────────── */}
            {/* Language */}
            <div className="flex rounded-lg overflow-hidden border border-gray-200 flex-shrink-0">
              {(['en', 'he'] as Lang[]).map(l => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  title={t(`lang.${l}`)}
                  className={`px-2 py-1 text-[10px] font-bold transition ${
                    lang === l
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-500 hover:bg-gray-50 bg-white'
                  }`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Theme */}
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
              className="w-7 h-7 flex items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 transition text-sm flex-shrink-0"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>

            {tabs && tabs.length > 0 && (
              <div className="flex gap-0.5 bg-gray-100 rounded-xl p-1">
                {tabs.map(tab => (
                  <button key={tab.key} onClick={() => onTabChange?.(tab.key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                      activeTab === tab.key ? 'bg-white text-blue-700 shadow' : 'text-gray-500 hover:text-gray-700'
                    }`}>
                    {tab.label}
                  </button>
                ))}
              </div>
            )}

            <NotificationPanel />

            <div className="flex items-center gap-2.5 pl-3 border-l border-gray-100">
              <AvatarBubble name={displayName} url={user?.avatar_url} size={32} />
              <div className="hidden sm:block">
                <p className="text-xs font-bold text-gray-800 leading-none">{t('topbar.hello')}, {firstName}</p>
                <p className="text-[10px] text-gray-400 capitalize">{t(`role.${role}`)}</p>
              </div>
              <button onClick={handleLogout} className="flex items-center gap-1 text-xs text-gray-400 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 hover:text-gray-700 transition">
                <IconLogout /> {t('nav.logout')}
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
};
