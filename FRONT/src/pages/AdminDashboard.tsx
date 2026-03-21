import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { StatCard } from '../components/widgets/StatCard';
import { WeeklySchedule, coursesToSlots } from '../components/widgets/WeeklySchedule';
import { EmptyState } from '../components/widgets/EmptyState';
import { ErrorState } from '../components/widgets/ErrorState';
import { apiService } from '../services/apiService';
import { RiskBadge } from '../components/RiskBadge';
import { UserAvatar } from '../components/UserAvatar';
import { formatActivityDescription } from '../utils/enumLabels';
import { AIInsightsCard } from '../components/AIInsightsCard';

const VALID_TABS = new Set(['overview','students','teachers','schedule','health','audit','updates','ai','pending']);

const DIST_COLORS: Record<string, string> = {
  excellent:       'bg-emerald-400',
  good:            'bg-blue-400',
  average:         'bg-orange-400',
  needs_attention: 'bg-red-400',
};

const UPDATE_BADGE: Record<string, string> = {
  ai_alert:     'bg-red-100 text-red-700',
  enrollment:   'bg-blue-100 text-blue-700',
  lesson_record:'bg-green-100 text-green-700',
};

// ── Pending user row with inline role-correction dropdown ─────────────────────
const PendingUserRow: React.FC<{
  user: any;
  actionLoading: string | null;
  fmtDate: (d: string | null | undefined) => string;
  onApprove: (user: any, role?: string) => void;
  onReject: (user: any) => void;
}> = ({ user, actionLoading, fmtDate, onApprove, onReject }) => {
  const [correctedRole, setCorrectedRole] = React.useState(user.role);
  const busy = actionLoading === user.id;
  return (
    <tr className="hover:bg-gray-50 transition">
      <td className="py-2.5 pr-4">
        <div className="flex items-center gap-2">
          <UserAvatar name={user.display_name || '?'} url={user.avatar_url} size={28} bg="bg-gradient-to-br from-amber-300 to-orange-400" />
          <Link to={`/users/${user.id}/profile`} className="font-semibold text-gray-800 truncate max-w-[160px] hover:underline">{user.display_name || '—'}</Link>
        </div>
      </td>
      <td className="py-2.5 pr-4 text-gray-500">{user.email}</td>
      <td className="py-2.5 pr-4">
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">{user.role}</span>
      </td>
      <td className="py-2.5 pr-4 text-gray-400">{fmtDate(user.created_at)}</td>
      <td className="py-2.5 pr-4">
        <select
          value={correctedRole}
          onChange={e => setCorrectedRole(e.target.value)}
          disabled={busy}
          className="border border-gray-200 rounded-lg px-1.5 py-0.5 text-[10px] focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
        >
          <option value="student">student</option>
          <option value="teacher">teacher</option>
          <option value="parent">parent</option>
        </select>
      </td>
      <td className="py-2.5">
        <div className="flex gap-1">
          <button
            disabled={busy}
            onClick={() => onApprove(user, correctedRole !== user.role ? correctedRole : undefined)}
            className="bg-green-50 hover:bg-green-100 text-green-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50"
          >
            {busy ? '…' : 'Approve'}
          </button>
          <button
            disabled={busy}
            onClick={() => onReject(user)}
            className="bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      </td>
    </tr>
  );
};

export const AdminDashboard: React.FC = () => {
  const { t } = useApp();
  const statusActive = t('enrollment.active');
  const statusInactive = t('enrollment.inactive');
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') || 'overview';
  const [tab, setTab] = useState(VALID_TABS.has(initialTab) ? initialTab : 'overview');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // System health
  const [health, setHealth] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Audit log
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditFilter, setAuditFilter] = useState({ action: '', resource_type: '' });

  // Updates
  const [updates, setUpdates] = useState<any[]>([]);
  const [updatesLoading, setUpdatesLoading] = useState(false);

  // Students
  const [students, setStudents] = useState<any[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');

  // Teachers (real data)
  const [teachers, setTeachers] = useState<any[]>([]);
  const [teachersLoading, setTeachersLoading] = useState(false);
  const [teachersError, setTeachersError] = useState<string | null>(null);

  // User action state (deactivate / delete / view-courses / assign-course / role-change)
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedUserCourses, setExpandedUserCourses] = useState<string | null>(null);
  const [expandedCoursesData, setExpandedCoursesData] = useState<Record<string, any[]>>({});
  const [assignCourseTarget, setAssignCourseTarget] = useState<{ userId: string; role: string } | null>(null);
  const [assignCourseId, setAssignCourseId] = useState('');

  // AI Overview
  const [aiOverview, setAiOverview] = useState<any>(null);
  const [aiOverviewLoading, setAiOverviewLoading] = useState(false);
  const [studentRiskMap, setStudentRiskMap] = useState<Record<string, any>>({});

  // Dashboard AI insights
  const [dashInsights, setDashInsights] = useState<string[]>([]);
  const [dashInsightsLoading, setDashInsightsLoading] = useState(false);

  const loadDashInsights = () => {
    setDashInsightsLoading(true);
    apiService.getDashboardInsights()
      .then(r => setDashInsights(r.data?.insights ?? []))
      .catch(() => {})
      .finally(() => setDashInsightsLoading(false));
  };

  // Pending approvals
  const [pendingUsers, setPendingUsers] = useState<any[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);

  // Create user modal
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [createForm, setCreateForm] = useState({ first_name: '', last_name: '', email: '', password: '', role: 'student' });
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    apiService.getDashboard()
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load dashboard data.'))
      .finally(() => setLoading(false));
  };

  const loadAiOverview = () => {
    if (aiOverviewLoading) return;
    setAiOverviewLoading(true);
    apiService.getAdminAIOverview()
      .then(r => {
        setAiOverview(r.data);
        setStudentRiskMap(r.data?.student_risk_map ?? {});
      })
      .catch(() => {})
      .finally(() => setAiOverviewLoading(false));
  };

  const loadHealth = () => {
    setHealthLoading(true);
    apiService.getSystemHealth()
      .then(r => setHealth(r.data))
      .catch(() => {})
      .finally(() => setHealthLoading(false));
  };

  const loadPending = () => {
    setPendingLoading(true);
    apiService.getPendingUsers()
      .then(r => setPendingUsers(r.data ?? []))
      .catch(() => {})
      .finally(() => setPendingLoading(false));
  };

  const handleApproveUser = async (user: any, correctedRole?: string) => {
    setActionLoading(user.id);
    try {
      await apiService.approveUser(user.id, correctedRole);
      setPendingUsers(prev => prev.filter(u => u.id !== user.id));
      // Also refresh the appropriate role list if it's loaded
      if ((correctedRole || user.role) === 'student') loadStudents();
      if ((correctedRole || user.role) === 'teacher') loadTeachers();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Approval failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectUser = async (user: any) => {
    if (!window.confirm(`Reject registration for ${user.display_name || user.email}?\n\nThis will delete their account.`)) return;
    setActionLoading(user.id);
    try {
      await apiService.rejectUser(user.id);
      setPendingUsers(prev => prev.filter(u => u.id !== user.id));
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Rejection failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateLoading(true);
    setCreateError(null);
    try {
      await apiService.adminCreateUser(createForm);
      setShowCreateUser(false);
      setCreateForm({ first_name: '', last_name: '', email: '', password: '', role: 'student' });
      // Refresh appropriate list
      if (createForm.role === 'student') loadStudents();
      if (createForm.role === 'teacher') loadTeachers();
    } catch (err: any) {
      setCreateError(err?.response?.data?.detail || 'Failed to create user.');
    } finally {
      setCreateLoading(false);
    }
  };

  const loadAudit = (filters = auditFilter) => {
    setAuditLoading(true);
    apiService.getAuditLogs({ limit: 100, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) })
      .then(r => setAuditLogs(r.data))
      .catch(() => {})
      .finally(() => setAuditLoading(false));
  };

  const loadUpdates = () => {
    setUpdatesLoading(true);
    apiService.getDashboardUpdates()
      .then(r => setUpdates(r.data?.updates ?? []))
      .catch(() => {})
      .finally(() => setUpdatesLoading(false));
  };

  const [studentsError, setStudentsError] = useState<string | null>(null);

  const loadStudents = () => {
    setStudentsLoading(true);
    setStudentsError(null);
    apiService.getAdminUsers('student')
      .then(r => setStudents(r.data ?? []))
      .catch(() => setStudentsError('Failed to load students.'))
      .finally(() => setStudentsLoading(false));
  };

  const loadTeachers = () => {
    setTeachersLoading(true);
    setTeachersError(null);
    apiService.getAdminUsers('teacher')
      .then(r => setTeachers(r.data ?? []))
      .catch(() => setTeachersError('Failed to load teachers.'))
      .finally(() => setTeachersLoading(false));
  };

  const toggleUserActive = async (user: any) => {
    if (!window.confirm(`${user.is_active ? 'Deactivate' : 'Activate'} ${user.display_name}?`)) return;
    setActionLoading(user.id);
    try {
      if (user.is_active) {
        await apiService.deactivateUser(user.id);
      } else {
        await apiService.activateUser(user.id);
      }
      // Local state update — avoid full list refetch
      const updatedUser = { ...user, is_active: !user.is_active };
      if (user.role === 'student') {
        setStudents((prev: any[]) => prev.map(u => u.id === user.id ? updatedUser : u));
      } else {
        setTeachers((prev: any[]) => prev.map(u => u.id === user.id ? updatedUser : u));
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Action failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteUser = async (user: any) => {
    if (!window.confirm(`Permanently delete ${user.display_name}?\n\nThis is a soft delete — their data (grades, feedback, enrollments) is preserved but they cannot log in.`)) return;
    setActionLoading(user.id);
    try {
      await apiService.deleteUser(user.id);
      // Local state update — remove from list immediately
      if (user.role === 'student') {
        setStudents((prev: any[]) => prev.filter(u => u.id !== user.id));
      } else {
        setTeachers((prev: any[]) => prev.filter(u => u.id !== user.id));
      }
      if (expandedUserCourses === user.id) setExpandedUserCourses(null);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Delete failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const toggleUserCourses = async (userId: string) => {
    if (expandedUserCourses === userId) { setExpandedUserCourses(null); return; }
    setExpandedUserCourses(userId);
    if (expandedCoursesData[userId]) return; // already loaded
    try {
      const r = await apiService.getUserCourses(userId);
      setExpandedCoursesData(prev => ({ ...prev, [userId]: r.data ?? [] }));
    } catch {
      setExpandedCoursesData(prev => ({ ...prev, [userId]: [] }));
    }
  };

  const handleAssignStudentToCourse = async (studentId: string) => {
    if (!assignCourseId) return;
    setActionLoading(studentId);
    try {
      await apiService.enrollCourse({ student_id: studentId, course_id: assignCourseId });
      setAssignCourseTarget(null);
      setAssignCourseId('');
      // refresh courses for this user
      const r = await apiService.getUserCourses(studentId);
      setExpandedCoursesData(prev => ({ ...prev, [studentId]: r.data ?? [] }));
      setExpandedUserCourses(studentId);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Enroll failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleAssignTeacherToCourse = async (teacherId: string) => {
    if (!assignCourseId) return;
    setActionLoading(teacherId);
    try {
      await apiService.changeCourseTeacher(assignCourseId, teacherId);
      setAssignCourseTarget(null);
      setAssignCourseId('');
      // refresh courses for this teacher
      const r = await apiService.getUserCourses(teacherId);
      setExpandedCoursesData(prev => ({ ...prev, [teacherId]: r.data ?? [] }));
      setExpandedUserCourses(teacherId);
      load(); // refresh course list in overview
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Assign failed.');
    } finally {
      setActionLoading(null);
    }
  };

  // Sync tab state when URL query param changes (e.g. sidebar navigation on same route)
  useEffect(() => {
    const urlTab = searchParams.get('tab') || 'overview';
    setTab(VALID_TABS.has(urlTab) ? urlTab : 'overview');
  }, [searchParams]);

  useEffect(() => { load(); loadDashInsights(); }, []);

  useEffect(() => {
    if (tab === 'health')    loadHealth();
    if (tab === 'audit')     loadAudit();
    if (tab === 'updates')   loadUpdates();
    if (tab === 'students')  loadStudents();
    if (tab === 'teachers')  loadTeachers();
    if (tab === 'ai')        loadAiOverview();
    if (tab === 'pending')   loadPending();
    if (tab === 'overview')  loadDashInsights();
  }, [tab]);

  const handleRoleChange = async (user: any, newRole: string) => {
    if (!window.confirm(`Change ${user.display_name}'s role from "${user.role}" to "${newRole}"?`)) return;
    setActionLoading(user.id);
    try {
      await apiService.changeUserRole(user.id, newRole);
      // Move user between lists locally — avoid two full list refetches
      const updatedUser = { ...user, role: newRole };
      if (user.role === 'student') setStudents((prev: any[]) => prev.filter(u => u.id !== user.id));
      if (user.role === 'teacher') setTeachers((prev: any[]) => prev.filter(u => u.id !== user.id));
      if (newRole === 'student') setStudents((prev: any[]) => [updatedUser, ...prev]);
      if (newRole === 'teacher') setTeachers((prev: any[]) => [updatedUser, ...prev]);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Role change failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const fmtDate = (iso: string | null | undefined) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 7 * 86400) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString();
  };

  const m = data?.metrics || {};
  const courses: any[] = data?.courses || [];

  const scheduleSlots = coursesToSlots(courses);

  /* Group courses by teacher for the teachers list */
  const teacherMap: Record<string, { name: string; courses: any[] }> = {};
  courses.forEach((c: any) => {
    const tid = c.teacher_id || 'unknown';
    if (!teacherMap[tid]) teacherMap[tid] = { name: `Teacher (${tid.slice(-4)})`, courses: [] };
    teacherMap[tid].courses.push(c);
  });
  const teacherRows = Object.entries(teacherMap).map(([tid, info]) => ({
    id: tid, name: info.name,
    subject: info.courses.map(c => c.name.split(' ')[0]).join(', '),
    upcoming: info.courses.filter(c => c.status === 'published').length,
  }));

  return (
    <DashboardLayout tabs={[
      { key: 'overview',  label: t('tab.overview')   },
      { key: 'students',  label: t('tab.students')   },
      { key: 'teachers',  label: t('tab.teachers')   },
      { key: 'schedule',  label: t('tab.schedule')   },
      { key: 'health',    label: t('tab.health')     },
      { key: 'audit',     label: t('tab.audit')      },
      { key: 'updates',   label: t('tab.updates')    },
      { key: 'ai',        label: t('tab.aiOverview') },
      { key: 'pending',   label: pendingUsers.length > 0 ? `${t('enrollment.pending')} (${pendingUsers.length})` : t('enrollment.pending') },
    ]} activeTab={tab} onTabChange={setTab}>
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
            <StatCard label={t('admin.activeStudents')} value={m.total_users ?? 0}            icon={<span>👨‍🎓</span>} color="bg-blue-500" />
            <StatCard label={t('nav.teachers')}         value={Math.max(1, teacherRows.length)} icon={<span>👩‍🏫</span>} color="bg-orange-400" />
            <StatCard label={t('stat.activeCourses')}   value={m.published_courses ?? 0}      icon={<span>📚</span>} color="bg-green-500" />
            <StatCard label={t('admin.totalCourses')}   value={m.total_courses ?? 0}          icon={<span>🎓</span>} color="bg-purple-500" />
            <StatCard label={t('admin.enrollments')}    value={m.total_enrollments ?? 0}      icon={<span>📝</span>} color="bg-teal-500" />
          </div>

          {tab === 'overview' && (
            <div className="grid lg:grid-cols-2 gap-6">
              {/* Student Progress Distribution (real data) */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">{t('admin.progressDistribution')}</h2>
                  <Link to="/progress" className="text-blue-600 text-xs hover:underline">{t('admin.fullReport')}</Link>
                </div>
                {(() => {
                  const dist = m.progress_distribution ?? {};
                  const total = Object.values(dist).reduce((a: number, v: any) => a + (v as number), 0) as number;
                  const rows = [
                    { key: 'excellent',       icon: '🌟' },
                    { key: 'good',            icon: '✅' },
                    { key: 'average',         icon: '📈' },
                    { key: 'needs_attention', icon: '⚠️' },
                  ];
                  return total === 0 ? (
                    <p className="text-gray-400 text-xs text-center py-8">{t('admin.noPerformanceScores')}</p>
                  ) : (
                    <div className="space-y-3">
                      {rows.map(({ key, icon }) => {
                        const count = (dist[key] as number) ?? 0;
                        const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                        return (
                          <div key={key} className="flex items-center gap-3 text-xs">
                            <span className="w-4">{icon}</span>
                            <span className="w-28 text-gray-600 font-medium">{t(`classification.${key}`)}</span>
                            <div className="flex-1 bg-gray-100 rounded-full h-2">
                              <div className={`h-2 rounded-full ${DIST_COLORS[key]}`} style={{ width: `${pct}%` }} />
                            </div>
                            <span className="w-8 text-right font-bold text-gray-700">{count}</span>
                            <span className="w-8 text-right text-gray-400">{pct}%</span>
                          </div>
                        );
                      })}
                      <div className="pt-2 border-t border-gray-100 flex gap-4 text-xs">
                        <span className="text-gray-500">{t('admin.totalScored')} <strong className="text-gray-700">{total}</strong></span>
                        <span className="text-red-600">{t('admin.atRisk')} <strong>{m.at_risk_count ?? 0}</strong></span>
                        <span className="text-emerald-600">{t('admin.performingWell')} <strong>{m.students_improving ?? 0}</strong></span>
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Schedule Overview */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">Schedule Overview</h2>
                  <span className="text-xs text-gray-400">This Week</span>
                </div>
                {scheduleSlots.length > 0 ? (
                  <WeeklySchedule slots={scheduleSlots} />
                ) : (
                  <EmptyState icon="📅" title={t('admin.noScheduled')} />
                )}
              </div>

              {/* AI Dashboard Insights */}
              <AIInsightsCard
                insights={dashInsights}
                loading={dashInsightsLoading}
                onRefresh={loadDashInsights}
              />

              {/* Courses table */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 lg:col-span-2">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-bold text-gray-800 text-sm">{t('admin.allCourses')}</h2>
                  <Link to="/courses/new" className="bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-blue-700 transition">
                    + New Course
                  </Link>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('admin.colCourse'), t('admin.colCode'), t('admin.colStatus'), t('admin.colEnrolledCapacity'), ''].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {courses.map((c: any) => {
                        const enrolled = c.enrolled_count ?? 0;
                        const cap = c.capacity ?? 1;
                        const fill = Math.min(100, Math.round((enrolled / cap) * 100));
                        return (
                          <tr key={c.id} className="hover:bg-gray-50 transition cursor-pointer" onClick={() => window.location.href = `/courses/${c.id}`}>
                            <td className="py-2.5 pr-4 font-semibold text-blue-700 hover:underline">
                              <Link to={`/courses/${c.id}`} onClick={e => e.stopPropagation()}>{c.name}</Link>
                            </td>
                            <td className="py-2.5 pr-4 font-mono text-blue-600">{c.code}</td>
                            <td className="py-2.5 pr-4">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                c.status === 'published' ? 'bg-green-100 text-green-700' :
                                c.status === 'draft' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                              }`}>{c.status}</span>
                            </td>
                            <td className="py-2.5 pr-4">
                              <div className="flex items-center gap-2">
                                <span className="text-gray-600 text-xs w-12">{enrolled}/{cap}</span>
                                <div className="flex-1 bg-gray-100 rounded-full h-1.5 w-20">
                                  <div className="h-1.5 rounded-full bg-blue-400" style={{ width: `${fill}%` }} />
                                </div>
                              </div>
                            </td>
                            <td className="py-2.5 pr-2">
                              <Link to={`/courses/${c.id}`} onClick={e => e.stopPropagation()} className="text-blue-600 text-xs hover:underline">Open →</Link>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {courses.length === 0 && <p className="text-center text-gray-400 py-8">No courses yet</p>}
                </div>
              </div>

              {/* System Statistics */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 lg:col-span-2">
                <h2 className="font-bold text-gray-800 text-sm mb-4">{t('admin.systemStats')}</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  {[
                    { label: t('admin.activeUsers'),      value: m.active_users ?? m.total_users ?? 0,   icon: '👥', color: 'text-blue-700' },
                    { label: t('stat.activeCourses'),     value: m.active_courses ?? 0,                  icon: '📗', color: 'text-green-700' },
                    { label: t('stat.archivedCourses'),   value: m.archived_courses ?? 0,                icon: '📦', color: 'text-gray-600' },
                    { label: t('stat.avgStudents'),       value: m.avg_students_per_course ?? 0,         icon: '📊', color: 'text-purple-700' },
                    { label: t('admin.upcomingLessons'),  value: m.upcoming_lessons ?? 0,                icon: '📅', color: 'text-orange-600' },
                  ].map(s => (
                    <div key={s.label} className="bg-gray-50 rounded-xl p-3 text-center">
                      <div className="text-xl mb-1">{s.icon}</div>
                      <p className={`text-xl font-black ${s.color}`}>{s.value}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5 leading-tight">{s.label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Create User Modal */}
          {showCreateUser && (
            <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
              <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 w-full max-w-md">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold text-gray-800 text-sm">Create User</h3>
                  <button onClick={() => { setShowCreateUser(false); setCreateError(null); }} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
                </div>
                <form onSubmit={handleCreateUser} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 mb-1">First Name</label>
                      <input required className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        value={createForm.first_name} onChange={e => setCreateForm(f => ({ ...f, first_name: e.target.value }))} />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-600 mb-1">Last Name</label>
                      <input required className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                        value={createForm.last_name} onChange={e => setCreateForm(f => ({ ...f, last_name: e.target.value }))} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Email</label>
                    <input required type="email" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      value={createForm.email} onChange={e => setCreateForm(f => ({ ...f, email: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Password (min 8 chars)</label>
                    <input required type="password" minLength={8} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      value={createForm.password} onChange={e => setCreateForm(f => ({ ...f, password: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Role</label>
                    <select className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                      value={createForm.role} onChange={e => setCreateForm(f => ({ ...f, role: e.target.value }))}>
                      <option value="student">Student</option>
                      <option value="teacher">Teacher</option>
                      <option value="parent">Parent</option>
                    </select>
                  </div>
                  {createError && <p className="text-red-500 text-xs">{createError}</p>}
                  <div className="flex gap-2 pt-1">
                    <button type="submit" disabled={createLoading}
                      className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-xs font-bold py-2 rounded-lg transition">
                      {createLoading ? 'Creating…' : 'Create User'}
                    </button>
                    <button type="button" onClick={() => { setShowCreateUser(false); setCreateError(null); }}
                      className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold py-2 rounded-lg transition">
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {tab === 'students' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-800 text-sm">All Students</h2>
                <div className="flex items-center gap-3">
                  <input
                    className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 w-48"
                    placeholder="Search by name or email…"
                    value={studentSearch}
                    onChange={e => setStudentSearch(e.target.value)}
                  />
                  <span className="text-xs text-gray-400">{students.length} student(s)</span>
                  <button onClick={() => setShowCreateUser(true)}
                    className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition">
                    + Create User
                  </button>
                </div>
              </div>
              {studentsLoading ? (
                <div className="flex justify-center py-16">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : studentsError ? (
                <div className="text-red-500 text-sm text-center py-8">{studentsError} <button onClick={loadStudents} className="underline ml-1">Retry</button></div>
              ) : students.length === 0 ? (
                <EmptyState icon="👨‍🎓" title="No students found" description="Students will appear here once they register." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('admin.colName'), t('admin.colEmail'), t('admin.colLastActive'), t('admin.colStatus'), t('admin.colRole'), t('admin.colActions')].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {students
                        .filter((s: any) => {
                          if (!studentSearch) return true;
                          const q = studentSearch.toLowerCase();
                          return (s.display_name || '').toLowerCase().includes(q) || s.email.toLowerCase().includes(q);
                        })
                        .map((s: any) => (
                          <React.Fragment key={s.id}>
                            <tr className="hover:bg-gray-50 transition">
                              <td className="py-2.5 pr-4">
                                <div className="flex items-center gap-2">
                                  <UserAvatar name={s.display_name || '?'} url={s.avatar_url} size={28} bg={s.is_active ? 'bg-gradient-to-br from-blue-300 to-purple-400' : 'bg-gray-300'} />
                                  <div>
                                    <Link to={`/users/${s.id}/profile`} className={`font-semibold truncate max-w-[200px] hover:underline ${s.is_active ? 'text-gray-800' : 'text-gray-400 line-through'}`}>{s.display_name || '—'}</Link>
                                    {studentRiskMap[s.id] && (
                                      <div className="mt-0.5">
                                        <RiskBadge
                                          riskLevel={studentRiskMap[s.id].risk_level}
                                          predictionLabel={studentRiskMap[s.id].prediction_label}
                                        />
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </td>
                              <td className="py-2.5 pr-4 text-gray-500">{s.email}</td>
                              <td className="py-2.5 pr-4 text-gray-400">{fmtDate(s.last_active_at)}</td>
                              <td className="py-2.5 pr-4">
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${s.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                  {s.is_active ? statusActive : statusInactive}
                                </span>
                              </td>
                              <td className="py-2.5 pr-4">
                                <select
                                  value={s.role}
                                  disabled={actionLoading === s.id}
                                  onChange={e => handleRoleChange(s, e.target.value)}
                                  className="border border-gray-200 rounded-lg px-1.5 py-0.5 text-[10px] focus:outline-none focus:ring-2 focus:ring-blue-300 disabled:opacity-50"
                                >
                                  <option value="student">student</option>
                                  <option value="teacher">teacher</option>
                                  <option value="parent">parent</option>
                                </select>
                              </td>
                              <td className="py-2.5">
                                <div className="flex flex-wrap gap-1">
                                  <Link
                                    to={`/users/${s.id}/profile`}
                                    className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    View Profile
                                  </Link>
                                  <button
                                    onClick={() => toggleUserCourses(s.id)}
                                    className="bg-blue-50 hover:bg-blue-100 text-blue-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    Courses {expandedUserCourses === s.id ? '▲' : '▼'}
                                  </button>
                                  <button
                                    onClick={() => setAssignCourseTarget(assignCourseTarget?.userId === s.id ? null : { userId: s.id, role: 'student' })}
                                    className="bg-green-50 hover:bg-green-100 text-green-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                  >
                                    + Assign Course
                                  </button>
                                  <button
                                    disabled={actionLoading === s.id}
                                    onClick={() => toggleUserActive(s)}
                                    className={`text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50 ${s.is_active ? 'bg-yellow-50 hover:bg-yellow-100 text-yellow-700' : 'bg-green-50 hover:bg-green-100 text-green-700'}`}
                                  >
                                    {actionLoading === s.id ? '…' : s.is_active ? 'Deactivate' : 'Activate'}
                                  </button>
                                  <button
                                    disabled={actionLoading === s.id}
                                    onClick={() => handleDeleteUser(s)}
                                    className="bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50"
                                  >
                                    Delete
                                  </button>
                                </div>
                              </td>
                            </tr>
                            {/* Assign-to-course panel */}
                            {assignCourseTarget?.userId === s.id && (
                              <tr>
                                <td colSpan={6} className="pb-3 px-2">
                                  <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-center gap-2 flex-wrap">
                                    <span className="text-xs font-semibold text-green-800">Assign {s.display_name} to:</span>
                                    <select
                                      className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-green-300"
                                      value={assignCourseId}
                                      onChange={e => setAssignCourseId(e.target.value)}
                                    >
                                      <option value="">— select course —</option>
                                      {courses.map((c: any) => (
                                        <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                                      ))}
                                    </select>
                                    <button
                                      disabled={!assignCourseId || actionLoading === s.id}
                                      onClick={() => handleAssignStudentToCourse(s.id)}
                                      className="bg-green-600 hover:bg-green-700 text-white text-[10px] font-semibold px-3 py-1.5 rounded-lg transition disabled:opacity-50"
                                    >
                                      {actionLoading === s.id ? 'Enrolling…' : 'Enroll'}
                                    </button>
                                    <button onClick={() => { setAssignCourseTarget(null); setAssignCourseId(''); }} className="text-[10px] text-gray-500 hover:underline">Cancel</button>
                                  </div>
                                </td>
                              </tr>
                            )}
                            {/* Expanded courses panel */}
                            {expandedUserCourses === s.id && (
                              <tr>
                                <td colSpan={6} className="pb-3 px-2">
                                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                                    <p className="text-[10px] font-semibold text-gray-500 mb-2 uppercase tracking-wide">Enrolled Courses</p>
                                    {!expandedCoursesData[s.id] ? (
                                      <p className="text-xs text-gray-400">Loading…</p>
                                    ) : expandedCoursesData[s.id].length === 0 ? (
                                      <p className="text-xs text-gray-400">Not enrolled in any courses.</p>
                                    ) : (
                                      <div className="space-y-1">
                                        {expandedCoursesData[s.id].map((c: any) => (
                                          <div key={c.enrollment_id} className="flex items-center justify-between">
                                            <span className="text-xs text-gray-700 font-medium">{c.course_name} <span className="font-mono text-gray-400 text-[10px]">({c.course_code})</span></span>
                                            <div className="flex items-center gap-2">
                                              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c.enrollment_status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{c.enrollment_status}</span>
                                              <Link to={`/courses/${c.course_id}`} className="text-[10px] text-blue-600 hover:underline">Open</Link>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        ))}
                    </tbody>
                  </table>
                  {studentSearch && students.filter((s: any) => {
                    const q = studentSearch.toLowerCase();
                    return (s.display_name || '').toLowerCase().includes(q) || s.email.toLowerCase().includes(q);
                  }).length === 0 && (
                    <p className="text-center text-gray-400 py-8 text-xs">No students match your search.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === 'teachers' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-800 text-sm">Teachers List</h2>
                <span className="text-xs text-gray-400">{teachers.length} teacher(s)</span>
              </div>
              {teachersLoading ? (
                <div className="flex justify-center py-16">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : teachersError ? (
                <div className="text-red-500 text-sm text-center py-8">{teachersError} <button onClick={loadTeachers} className="underline ml-1">Retry</button></div>
              ) : teachers.length === 0 ? (
                <EmptyState icon="👩‍🏫" title="No teachers found" description="Teachers will appear here once they register." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('admin.colName'), t('admin.colEmail'), t('admin.colLastActive'), t('admin.colStatus'), t('admin.colRole'), t('admin.colActions')].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {teachers.map((t: any) => (
                        <React.Fragment key={t.id}>
                          <tr className="hover:bg-gray-50 transition">
                            <td className="py-2.5 pr-4">
                              <div className="flex items-center gap-2">
                                <UserAvatar name={t.display_name || '?'} url={t.avatar_url} size={28} bg={t.is_active ? 'bg-gradient-to-br from-orange-300 to-red-400' : 'bg-gray-300'} />
                                <Link to={`/users/${t.id}/profile`} className={`font-semibold truncate max-w-[200px] hover:underline ${t.is_active ? 'text-gray-800' : 'text-gray-400 line-through'}`}>{t.display_name || '—'}</Link>
                              </div>
                            </td>
                            <td className="py-2.5 pr-4 text-gray-500">{t.email}</td>
                            <td className="py-2.5 pr-4 text-gray-400">{fmtDate(t.last_active_at)}</td>
                            <td className="py-2.5 pr-4">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${t.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                                {t.is_active ? statusActive : statusInactive}
                              </span>
                            </td>
                            <td className="py-2.5 pr-4">
                              <select
                                value={t.role}
                                disabled={actionLoading === t.id}
                                onChange={e => handleRoleChange(t, e.target.value)}
                                className="border border-gray-200 rounded-lg px-1.5 py-0.5 text-[10px] focus:outline-none focus:ring-2 focus:ring-orange-300 disabled:opacity-50"
                              >
                                <option value="student">student</option>
                                <option value="teacher">teacher</option>
                                <option value="parent">parent</option>
                              </select>
                            </td>
                            <td className="py-2.5">
                              <div className="flex flex-wrap gap-1">
                                <Link
                                  to={`/users/${t.id}/profile`}
                                  className="bg-gray-50 hover:bg-gray-100 text-gray-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  View Profile
                                </Link>
                                <button
                                  onClick={() => toggleUserCourses(t.id)}
                                  className="bg-blue-50 hover:bg-blue-100 text-blue-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  Courses {expandedUserCourses === t.id ? '▲' : '▼'}
                                </button>
                                <button
                                  onClick={() => setAssignCourseTarget(assignCourseTarget?.userId === t.id ? null : { userId: t.id, role: 'teacher' })}
                                  className="bg-orange-50 hover:bg-orange-100 text-orange-700 text-[10px] font-semibold px-2 py-1 rounded-lg transition"
                                >
                                  + Assign Course
                                </button>
                                <button
                                  disabled={actionLoading === t.id}
                                  onClick={() => toggleUserActive(t)}
                                  className={`text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50 ${t.is_active ? 'bg-yellow-50 hover:bg-yellow-100 text-yellow-700' : 'bg-green-50 hover:bg-green-100 text-green-700'}`}
                                >
                                  {actionLoading === t.id ? '…' : t.is_active ? 'Deactivate' : 'Activate'}
                                </button>
                                <button
                                  disabled={actionLoading === t.id}
                                  onClick={() => handleDeleteUser(t)}
                                  className="bg-red-50 hover:bg-red-100 text-red-600 text-[10px] font-semibold px-2 py-1 rounded-lg transition disabled:opacity-50"
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                          {/* Assign-to-course panel (changes course's teacher_id) */}
                          {assignCourseTarget?.userId === t.id && (
                            <tr>
                              <td colSpan={6} className="pb-3 px-2">
                                <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-semibold text-orange-800">Assign {t.display_name} as teacher of:</span>
                                  <select
                                    className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-orange-300"
                                    value={assignCourseId}
                                    onChange={e => setAssignCourseId(e.target.value)}
                                  >
                                    <option value="">— select course —</option>
                                    {courses.map((c: any) => (
                                      <option key={c.id} value={c.id}>{c.name} ({c.code})</option>
                                    ))}
                                  </select>
                                  <button
                                    disabled={!assignCourseId || actionLoading === t.id}
                                    onClick={() => handleAssignTeacherToCourse(t.id)}
                                    className="bg-orange-600 hover:bg-orange-700 text-white text-[10px] font-semibold px-3 py-1.5 rounded-lg transition disabled:opacity-50"
                                  >
                                    {actionLoading === t.id ? 'Assigning…' : 'Assign'}
                                  </button>
                                  <button onClick={() => { setAssignCourseTarget(null); setAssignCourseId(''); }} className="text-[10px] text-gray-500 hover:underline">Cancel</button>
                                </div>
                              </td>
                            </tr>
                          )}
                          {/* Expanded courses panel */}
                          {expandedUserCourses === t.id && (
                            <tr>
                              <td colSpan={6} className="pb-3 px-2">
                                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3">
                                  <p className="text-[10px] font-semibold text-gray-500 mb-2 uppercase tracking-wide">Teaching Courses</p>
                                  {!expandedCoursesData[t.id] ? (
                                    <p className="text-xs text-gray-400">Loading…</p>
                                  ) : expandedCoursesData[t.id].length === 0 ? (
                                    <p className="text-xs text-gray-400">Not assigned to any courses.</p>
                                  ) : (
                                    <div className="space-y-1">
                                      {expandedCoursesData[t.id].map((c: any) => (
                                        <div key={c.course_id} className="flex items-center justify-between">
                                          <span className="text-xs text-gray-700 font-medium">{c.course_name} <span className="font-mono text-gray-400 text-[10px]">({c.course_code})</span></span>
                                          <div className="flex items-center gap-2">
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c.status === 'published' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{c.status}</span>
                                            <Link to={`/courses/${c.course_id}`} className="text-[10px] text-blue-600 hover:underline">Open</Link>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'pending' && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-bold text-gray-800 text-sm">{t('admin.pendingApprovals')}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Review and approve or reject new user registrations</p>
                </div>
                <button onClick={loadPending} className="text-xs text-blue-600 hover:underline">{t('common.refresh')}</button>
              </div>
              {pendingLoading ? (
                <div className="flex justify-center py-16">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : pendingUsers.length === 0 ? (
                <EmptyState icon="✅" title="No pending registrations" description="All registrations have been reviewed." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {['Name', 'Email', 'Requested Role', 'Registered', 'Correct Role', 'Actions'].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {pendingUsers.map((u: any) => (
                        <PendingUserRow
                          key={u.id}
                          user={u}
                          actionLoading={actionLoading}
                          fmtDate={fmtDate}
                          onApprove={handleApproveUser}
                          onReject={handleRejectUser}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'schedule' && (() => {
            const scheduledCourses = courses.filter((c: any) => c.schedule?.days?.length);
            return (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="font-bold text-gray-800 text-sm">{t('admin.scheduleTitle')}</h2>
                    <p className="text-xs text-gray-400 mt-0.5">{scheduledCourses.length} / {courses.length} {t('nav.courses')} {t('courseForm.schedule').replace(' (optional)', '')}</p>
                  </div>
                  <span className="text-xs text-gray-400">{t('admin.allCourses')}</span>
                </div>
                {scheduledCourses.length === 0 ? (
                  <EmptyState icon="📅" title={t('admin.noScheduled')} description={t('admin.addScheduleHint')} />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100">
                          {[t('admin.colCourse'), t('admin.colCode'), t('admin.colTeacher'), t('admin.colDays'), t('admin.colTime'), t('admin.colEnrolled'), t('admin.colStatus')].map(h => (
                            <th key={h} className="text-left text-gray-400 font-semibold pb-2 pr-4">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {scheduledCourses.map((c: any) => {
                          const days = (c.schedule?.days ?? []).map((d: string) => d.slice(0, 3)).join(', ');
                          const time = c.schedule?.start_time ?? '—';
                          return (
                            <tr key={c.id} className="hover:bg-gray-50 transition">
                              <td className="py-2.5 pr-4 font-semibold text-blue-700">
                                <Link to={`/courses/${c.id}`} className="hover:underline">{c.name}</Link>
                              </td>
                              <td className="py-2.5 pr-4 font-mono text-blue-600 text-[10px]">{c.code}</td>
                              <td className="py-2.5 pr-4 text-gray-600">{c.teacher_name ?? '—'}</td>
                              <td className="py-2.5 pr-4 text-gray-600">{days}</td>
                              <td className="py-2.5 pr-4 text-gray-500">{time}</td>
                              <td className="py-2.5 pr-4 text-gray-600">{c.enrolled_count ?? 0}/{c.capacity}</td>
                              <td className="py-2.5 pr-4">
                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  c.status === 'published' ? 'bg-green-100 text-green-700' :
                                  c.status === 'draft'     ? 'bg-yellow-100 text-yellow-700' :
                                                              'bg-gray-100 text-gray-500'
                                }`}>{c.status}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })()}

          {tab === 'health' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-gray-800 text-sm">System Health</h2>
                <button onClick={loadHealth} className="text-xs text-blue-600 hover:underline">Refresh</button>
              </div>
              {healthLoading ? (
                <div className="flex justify-center py-16">
                  <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : !health ? (
                <p className="text-gray-400 text-sm text-center py-8">No data available.</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[
                    { key: 'activeUsers',     label: t('admin.activeUsers'),              value: health.active_users },
                    { key: 'lessonRecords',   label: 'Total Lesson Records',              value: health.total_lesson_records },
                    { key: 'lessonRec7d',     label: 'Lesson Records (7d)',               value: health.lesson_records_last_7_days },
                    { key: 'totalAlerts',     label: 'Total AI Alerts',                   value: health.total_ai_alerts },
                    { key: 'alerts7d',        label: 'Alerts (7d)',                       value: health.alerts_last_7_days },
                    { key: 'criticalAlerts',  label: 'Critical Alerts Open',              value: health.critical_alerts_open },
                    { key: 'weeklySent',      label: 'Weekly Reports Sent',               value: health.weekly_summaries_sent },
                    { key: 'pendingAck',      label: t('admin.pendingAcknowledgement'),   value: health.parent_acknowledgements_pending },
                  ].map(s => (
                    <div key={s.key} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4">
                      <p className="text-2xl font-black text-gray-900">{s.value ?? '—'}</p>
                      <p className="text-xs text-gray-500 mt-1">{s.label}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'audit' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 flex-wrap">
                <h2 className="font-bold text-gray-800 text-sm">Audit Log</h2>
                <input
                  className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                  placeholder="Filter by action…"
                  value={auditFilter.action}
                  onChange={e => setAuditFilter(f => ({ ...f, action: e.target.value }))}
                />
                <input
                  className="border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                  placeholder="Filter by resource type…"
                  value={auditFilter.resource_type}
                  onChange={e => setAuditFilter(f => ({ ...f, resource_type: e.target.value }))}
                />
                <button
                  onClick={() => loadAudit(auditFilter)}
                  className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-blue-700 transition"
                >
                  Search
                </button>
                <button
                  onClick={() => { setAuditFilter({ action: '', resource_type: '' }); loadAudit({ action: '', resource_type: '' }); }}
                  className="text-xs text-gray-500 hover:underline"
                >
                  Clear
                </button>
              </div>
              {auditLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : auditLogs.length === 0 ? (
                <EmptyState icon="📋" title="No audit logs found" />
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {['Timestamp', 'Action', 'Resource Type', 'Resource ID', 'Actor'].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold py-2 px-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {auditLogs.map((e: any) => (
                        <tr key={e.id} className="hover:bg-gray-50">
                          <td className="py-2 px-4 text-gray-500 whitespace-nowrap">
                            {new Date(e.timestamp).toLocaleString()}
                          </td>
                          <td className="py-2 px-4 font-mono text-blue-700">{e.action}</td>
                          <td className="py-2 px-4 text-gray-600">{e.resource_type}</td>
                          <td className="py-2 px-4 font-mono text-gray-400 truncate max-w-[120px]">
                            {e.resource_id ?? '—'}
                          </td>
                          <td className="py-2 px-4 font-mono text-gray-400 truncate max-w-[100px]">
                            {e.user_id?.slice(-8)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === 'updates' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-gray-800 text-sm">Recent Activity</h2>
                <button onClick={loadUpdates} className="text-xs text-blue-600 hover:underline">Refresh</button>
              </div>
              {updatesLoading ? (
                <div className="flex justify-center py-12">
                  <div className="w-7 h-7 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : updates.length === 0 ? (
                <EmptyState icon="🔔" title="No recent activity" />
              ) : (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-100">
                        {[t('updates.timestamp'), t('updates.type'), t('updates.description'), t('admin.colCourse'), t('courseDetail.colStudent')].map(h => (
                          <th key={h} className="text-left text-gray-400 font-semibold py-2 px-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {updates.map((u: any, i: number) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="py-2 px-4 text-gray-500 whitespace-nowrap">
                            {u.timestamp ? new Date(u.timestamp).toLocaleString() : '—'}
                          </td>
                          <td className="py-2 px-4">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${UPDATE_BADGE[u.type] ?? 'bg-gray-100 text-gray-600'}`}>
                              {u.type?.replace('_', ' ')}
                            </span>
                          </td>
                          <td className="py-2 px-4 text-gray-700 max-w-xs truncate">{formatActivityDescription(u.description, t)}</td>
                          <td className="py-2 px-4 text-gray-500 truncate max-w-[140px]">{u.course_name || '—'}</td>
                          <td className="py-2 px-4 text-gray-500 truncate max-w-[120px]">{u.student_name || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── AI Overview ─────────────────────────────────────────────────── */}
          {tab === 'ai' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="font-bold text-gray-800 text-sm">✦ AI Academic Intelligence</h2>
                <button onClick={loadAiOverview} className="text-xs text-purple-600 hover:underline">Refresh</button>
              </div>

              {aiOverviewLoading ? (
                <div className="flex justify-center py-16">
                  <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : !aiOverview ? (
                <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400">
                  <div className="text-4xl mb-3">🤖</div>
                  <p className="font-semibold text-gray-600">No AI data yet</p>
                  <p className="text-sm mt-1">Record grades, attendance, and feedback to generate AI insights.</p>
                </div>
              ) : (
                <>
                  {/* Summary banner */}
                  <div className="bg-purple-50 border border-purple-200 rounded-2xl p-4">
                    <p className="text-sm text-purple-900 font-medium">{aiOverview.summary}</p>
                    <div className="flex flex-wrap gap-3 mt-3">
                      {[
                        { label: 'High Risk', val: aiOverview.risk_counts?.high ?? 0,   color: 'bg-red-100 text-red-700' },
                        { label: 'Medium Risk', val: aiOverview.risk_counts?.medium ?? 0, color: 'bg-yellow-100 text-yellow-800' },
                        { label: 'Low Risk',  val: aiOverview.risk_counts?.low ?? 0,   color: 'bg-green-100 text-green-700' },
                        { label: 'Tracked',   val: aiOverview.total_tracked ?? 0,       color: 'bg-gray-100 text-gray-600' },
                      ].map(s => (
                        <div key={s.label} className={`px-3 py-1.5 rounded-xl text-xs font-semibold ${s.color}`}>
                          {s.label}: <strong>{s.val}</strong>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {/* Top risk courses */}
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                      <h3 className="text-sm font-bold text-gray-700 mb-3">🔴 Courses with Highest Risk</h3>
                      {(aiOverview.top_risk_courses ?? []).length === 0 ? (
                        <p className="text-xs text-gray-400 py-4 text-center">No high-risk courses detected.</p>
                      ) : (
                        <div className="space-y-2">
                          {aiOverview.top_risk_courses.map((c: any) => (
                            <div key={c.course_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                              <div>
                                <p className="text-xs font-semibold text-gray-700">{c.course_name}</p>
                                <p className="text-[10px] text-gray-400 font-mono">{c.course_code}</p>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <span className="text-[10px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold">
                                  {c.high_risk} high risk
                                </span>
                                <span className="text-[10px] text-gray-400">/ {c.total_students}</span>
                                <Link to={`/courses/${c.course_id}`} className="text-[10px] text-blue-600 hover:underline">Open</Link>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Declining courses */}
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                      <h3 className="text-sm font-bold text-gray-700 mb-3">📉 Declining Performance Trends</h3>
                      {(aiOverview.declining_courses ?? []).length === 0 ? (
                        <p className="text-xs text-gray-400 py-4 text-center">No declining courses detected.</p>
                      ) : (
                        <div className="space-y-2">
                          {aiOverview.declining_courses.map((c: any) => (
                            <div key={c.course_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                              <p className="text-xs font-semibold text-gray-700">{c.course_name}</p>
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-semibold">
                                  {c.at_risk_count}/{c.total_students} at risk
                                </span>
                                <Link to={`/courses/${c.course_id}`} className="text-[10px] text-blue-600 hover:underline">Open</Link>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Teacher workload */}
                    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                      <h3 className="text-sm font-bold text-gray-700 mb-3">👩‍🏫 Teachers with Heavy Load (3+ courses)</h3>
                      {(aiOverview.teacher_overload ?? []).length === 0 ? (
                        <p className="text-xs text-gray-400 py-4 text-center">No overloaded teachers detected.</p>
                      ) : (
                        <div className="space-y-2">
                          {aiOverview.teacher_overload.map((t: any) => (
                            <div key={t.teacher_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                              <p className="text-xs font-semibold text-gray-700">{t.teacher_name}</p>
                              <span className="text-[10px] bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full font-semibold">
                                {t.course_count} active courses
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Info card */}
                    <div className="bg-gray-50 rounded-2xl border border-gray-100 p-5 flex flex-col justify-center">
                      <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">About AI Insights</p>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        AI insights are derived from pre-computed performance scores, prediction models, and feedback analysis.
                        Results update automatically when teachers record grades, attendance, or feedback.
                        No student personal data is used in AI computations — only academic indicators.
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </>
      )}
    </DashboardLayout>
  );
};
