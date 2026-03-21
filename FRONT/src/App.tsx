import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AppProvider } from './contexts/AppContext';
import { PrivateRoute } from './components/PrivateRoute';
import { Navbar } from './components/Navbar';
import { UsabilityWidget } from './components/UsabilityWidget';

import { LandingPage }      from './pages/LandingPage';
import { LoginPage }        from './pages/LoginPage';
import { SignupPage }       from './pages/SignupPage';
import { CoursesPage }      from './pages/CoursesPage';
import { CourseFormPage }   from './pages/CourseFormPage';
import { ProgressPage }     from './pages/ProgressPage';
import { AdminDashboard }   from './pages/AdminDashboard';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { StudentDashboard } from './pages/StudentDashboard';
import { ParentDashboard }  from './pages/ParentDashboard';
import { CourseDetailPage } from './pages/CourseDetailPage';
import { SettingsPage }     from './pages/SettingsPage';
import { MaterialsPage }   from './pages/MaterialsPage';
import { MessagesPage }    from './pages/MessagesPage';
import NotificationsPage  from './pages/NotificationsPage';
import ChatPage           from './pages/ChatPage';
import ProfilePage        from './pages/ProfilePage';
import UserProfilePage   from './pages/UserProfilePage';
import { AcademicPlannerPage } from './pages/AcademicPlannerPage';

/** If logged in → go to role dashboard. If not → show landing page. */
const HomeRoute: React.FC = () => {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  if (!user)   return <LandingPage />;
  const routes: Record<string, string> = {
    admin:   '/dashboard/admin',
    teacher: '/dashboard/teacher',
    student: '/dashboard/student',
    parent:  '/dashboard/parent',
  };
  return <Navigate to={routes[user.role || ''] || '/dashboard/student'} replace />;
};

const ROLE_DASH: Record<string, string> = {
  admin: '/dashboard/admin', teacher: '/dashboard/teacher',
  student: '/dashboard/student', parent: '/dashboard/parent',
};
const SIDEBAR_TAB_MAP: Record<string, Record<string, string>> = {
  '/schedule':  { admin: 'schedule', teacher: 'schedule', student: 'schedule', parent: 'schedule' },
  '/students':  { admin: 'students', teacher: 'students' },
  '/teachers':  { admin: 'teachers' },
};
const RoleTabRedirect: React.FC<{ path: string }> = ({ path }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  const role = user.role || 'student';
  const dash = ROLE_DASH[role] || '/';
  const tab  = SIDEBAR_TAB_MAP[path]?.[role];
  return <Navigate to={tab ? `${dash}?tab=${tab}` : dash} replace />;
};

export default function App() {
  return (
    <AppProvider>
    <AuthProvider>
      <BrowserRouter>
        {/* Navbar only on inner pages (hides itself on /dashboard/* and login/signup handled by PageShell) */}
        <Navbar />
        <Routes>
          {/* Root — landing or dashboard */}
          <Route path="/" element={<HomeRoute />} />

          {/* Auth pages — their own layout (PageShell) */}
          <Route path="/login"  element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />

          {/* Role dashboards */}
          <Route path="/dashboard/admin"
            element={<PrivateRoute requiredRoles={['admin']}><AdminDashboard /></PrivateRoute>} />
          <Route path="/dashboard/teacher"
            element={<PrivateRoute requiredRoles={['teacher']}><TeacherDashboard /></PrivateRoute>} />
          <Route path="/dashboard/student"
            element={<PrivateRoute requiredRoles={['student']}><StudentDashboard /></PrivateRoute>} />
          <Route path="/dashboard/parent"
            element={<PrivateRoute requiredRoles={['parent']}><ParentDashboard /></PrivateRoute>} />
          <Route path="/dashboard" element={<PrivateRoute><HomeRoute /></PrivateRoute>} />

          {/* Courses */}
          <Route path="/courses"
            element={<PrivateRoute><CoursesPage /></PrivateRoute>} />
          <Route path="/courses/new"
            element={<PrivateRoute requiredRoles={['admin', 'teacher']}><CourseFormPage /></PrivateRoute>} />
          <Route path="/courses/:id/edit"
            element={<PrivateRoute requiredRoles={['admin', 'teacher']}><CourseFormPage /></PrivateRoute>} />
          <Route path="/courses/:courseId"
            element={<PrivateRoute><CourseDetailPage /></PrivateRoute>} />

          {/* Progress */}
          <Route path="/progress"
            element={<PrivateRoute><ProgressPage /></PrivateRoute>} />

          {/* Sidebar shortcuts — resolve to role-appropriate dashboard tab */}
          <Route path="/schedule"  element={<PrivateRoute><RoleTabRedirect path="/schedule"  /></PrivateRoute>} />
          <Route path="/students"  element={<PrivateRoute><RoleTabRedirect path="/students"  /></PrivateRoute>} />
          <Route path="/teachers"  element={<PrivateRoute><RoleTabRedirect path="/teachers"  /></PrivateRoute>} />
          <Route path="/materials" element={<PrivateRoute><MaterialsPage /></PrivateRoute>} />
          <Route path="/profile"   element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
          <Route path="/users/:userId/profile" element={<PrivateRoute><UserProfilePage /></PrivateRoute>} />
          <Route path="/settings"  element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
          <Route path="/messages"  element={<PrivateRoute requiredRoles={['teacher','student']}><MessagesPage /></PrivateRoute>} />
          <Route path="/notifications" element={<PrivateRoute><NotificationsPage /></PrivateRoute>} />
          <Route path="/chat" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
          <Route path="/planner"
            element={<PrivateRoute requiredRoles={['student','parent']}><AcademicPlannerPage /></PrivateRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <UsabilityWidget />
      </BrowserRouter>
    </AuthProvider>
    </AppProvider>
  );
}
