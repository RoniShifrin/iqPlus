import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * Navbar is shown only on non-dashboard pages (courses, progress).
 * Dashboard pages use DashboardLayout's sidebar instead.
 */
export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Hide on dashboard routes (they have their own layout)
  if (!user || location.pathname.startsWith('/dashboard') || location.pathname === '/login' || location.pathname === '/signup') return null;

  const active = (path: string) =>
    location.pathname === path ? 'bg-white/20 font-semibold' : 'hover:bg-white/10';

  const canManage = user.role === 'admin' || user.role === 'teacher';
  const dashRoute = {
    admin: '/dashboard/admin', teacher: '/dashboard/teacher',
    student: '/dashboard/student', parent: '/dashboard/parent',
  }[user.role || ''] || '/';

  return (
    <nav className="bg-gradient-to-r from-indigo-700 to-purple-700 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 flex justify-between h-16 items-center">
        <Link to={dashRoute} className="font-black text-xl">
          <span className="text-white">IQ</span><span className="text-purple-200">Plus</span>
        </Link>

        <div className="flex items-center gap-1 text-sm">
          <Link to={dashRoute} className={"px-3 py-1.5 rounded-lg transition " + active(dashRoute)}>
            Dashboard
          </Link>
          <Link to="/courses" className={"px-3 py-1.5 rounded-lg transition " + active('/courses')}>
            Courses
          </Link>
          {(user.role === 'student' || user.role === 'teacher') && (
            <Link to="/progress" className={"px-3 py-1.5 rounded-lg transition " + active('/progress')}>
              Progress
            </Link>
          )}
          {canManage && (
            <Link to="/courses/new"
              className="ml-2 bg-white text-indigo-700 hover:bg-indigo-50 px-3 py-1.5 rounded-lg font-semibold transition text-xs">
              + Course
            </Link>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm">
          <span className="text-purple-200 capitalize text-xs">{user.role}</span>
          <button
            onClick={async () => { await logout(); navigate('/login'); }}
            className="bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded-lg transition text-xs">
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
};
