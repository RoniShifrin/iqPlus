import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { AvatarUpload } from '../components/AvatarUpload';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const formatDate = (d?: string | Date | null) => {
  if (!d) return '—';
  return new Date(d as string).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
};

const capitalize = (s?: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : '—');

const InfoRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex items-start gap-2 py-2.5 border-b border-gray-100 last:border-0">
    <span className="w-36 flex-shrink-0 text-xs font-semibold text-gray-400 uppercase tracking-wider pt-0.5">{label}</span>
    <span className="text-sm text-gray-800 font-medium">{value || '—'}</span>
  </div>
);

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
    <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">{title}</h3>
    {children}
  </div>
);

/* ── Main Component ──────────────────────────────────────────────────────── */

export const ProfilePage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const { t } = useApp();
  const role = user?.role ?? 'student';

  /* ── Profile data ── */
  const [profile, setProfile] = useState<any>(null);

  /* ── Edit state ── */
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ first_name: '', last_name: '', display_name: '', age: '' });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveOk, setSaveOk] = useState(false);

  /* ── Role-specific data ── */
  const [roleData, setRoleData] = useState<any>(null);
  const [scores, setScores]     = useState<any[]>([]);

  /* ── Load profile ── */
  useEffect(() => {
    apiService.getProfile().then(r => setProfile(r.data)).catch(() => {});
  }, []);

  /* ── Load role-specific data ── */
  useEffect(() => {
    if (!role || !user?.id) return;
    apiService.getDashboard()
      .then(r => setRoleData(r.data))
      .catch(() => {});
    if (role === 'student') {
      apiService.getStudentScores(user.id)
        .then(r => setScores(r.data ?? []))
        .catch(() => {});
    }
  }, [role, user?.id]);

  /* ── Sync edit form when profile loads ── */
  useEffect(() => {
    if (!profile) return;
    setEditForm({
      first_name:    profile.first_name    ?? '',
      last_name:     profile.last_name     ?? '',
      display_name:  profile.display_name  ?? '',
      age:           profile.age != null   ? String(profile.age) : '',
    });
  }, [profile]);

  const startEdit = () => { setSaveError(''); setSaveOk(false); setEditing(true); };
  const cancelEdit = () => { setEditing(false); setSaveError(''); };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setSaveError(''); setSaveOk(false);
    try {
      const payload: any = {
        first_name:   editForm.first_name   || null,
        last_name:    editForm.last_name    || null,
        display_name: editForm.display_name || null,
      };
      if (editForm.age !== '') payload.age = Number(editForm.age);
      const res = await apiService.updateProfile(payload);
      setProfile(res.data);
      await refreshUser();
      setEditing(false);
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 3000);
    } catch {
      setSaveError('Failed to save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const displayName = profile
    ? (profile.display_name || [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.email)
    : (user?.display_name || [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.email || '');

  const F = 'w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400';

  /* ── Role-specific sections ── */
  const renderRoleSection = () => {
    if (!roleData) return <p className="text-sm text-gray-400">Loading...</p>;

    if (role === 'student') {
      const enrolled: any[] = roleData.courses ?? [];
      return (
        <Section title="Academic Overview">
          <div className="space-y-2">
            {enrolled.length === 0 ? (
              <p className="text-sm text-gray-400">No enrolled courses.</p>
            ) : enrolled.map((c: any) => {
              const score = scores.find((s: any) => s.course_id === c.id);
              return (
                <div key={c.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{c.name}</p>
                    <p className="text-xs text-gray-400">{c.code}</p>
                  </div>
                  {score != null && (
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      score.score >= 80 ? 'bg-green-100 text-green-700'
                      : score.score >= 60 ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-red-100 text-red-600'
                    }`}>
                      {Math.round(score.score)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      );
    }

    if (role === 'teacher') {
      const courses: any[] = roleData.courses ?? [];
      return (
        <Section title="My Courses">
          <div className="space-y-2">
            {courses.length === 0 ? (
              <p className="text-sm text-gray-400">No assigned courses.</p>
            ) : courses.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-semibold text-gray-800">{c.name}</p>
                  <p className="text-xs text-gray-400">{c.code} · {capitalize(c.status)}</p>
                </div>
                <span className="text-xs text-gray-500">{c.enrolled_count ?? 0} students</span>
              </div>
            ))}
          </div>
        </Section>
      );
    }

    if (role === 'parent') {
      const children: any[] = roleData.metrics?.children ?? [];
      return (
        <Section title="Linked Children">
          {children.length === 0 ? (
            <p className="text-sm text-gray-400">No linked children. Contact your admin to link a student account.</p>
          ) : (
            <div className="space-y-3">
              {children.map((child: any, i: number) => (
                <div key={child.id ?? i} className="p-3 bg-gray-50 rounded-xl">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-bold text-gray-800">{child.name || 'Student'}</p>
                    <span className="text-xs text-gray-400">{child.enrolled_count ?? 0} courses</span>
                  </div>
                  {(child.performance_scores ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {child.performance_scores.map((s: any) => (
                        <span key={s.course_id} className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          s.score >= 80 ? 'bg-green-100 text-green-700'
                          : s.score >= 60 ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-red-100 text-red-600'
                        }`}>
                          {s.course_name ?? s.course_id}: {Math.round(s.score)}%
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Section>
      );
    }

    if (role === 'admin') {
      const m = roleData.metrics ?? roleData;
      return (
        <Section title="System Overview">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Total Users',     value: m.total_students != null ? (m.total_students + (m.total_teachers ?? 0)) : m.registered_users },
              { label: 'Students',        value: m.total_students },
              { label: 'Teachers',        value: m.total_teachers },
              { label: 'Active Courses',  value: m.active_courses },
            ].map(item => item.value != null && (
              <div key={item.label} className="bg-blue-50 rounded-xl p-3 text-center">
                <p className="text-2xl font-black text-blue-700">{item.value}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.label}</p>
              </div>
            ))}
          </div>
        </Section>
      );
    }

    return null;
  };

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">

        {/* ── Header card ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-start gap-5">
            {/* Avatar */}
            <AvatarUpload size={88} />

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-xl font-black text-gray-900 truncate">{displayName}</h2>
                  <p className="text-sm text-gray-500">{profile?.email ?? user?.email}</p>
                </div>
                <span className={`flex-shrink-0 text-xs font-bold px-2.5 py-1 rounded-full capitalize ${
                  role === 'admin'   ? 'bg-purple-100 text-purple-700' :
                  role === 'teacher' ? 'bg-blue-100 text-blue-700' :
                  role === 'student' ? 'bg-green-100 text-green-700' :
                  'bg-orange-100 text-orange-700'
                }`}>
                  {capitalize(role)}
                </span>
              </div>

              <div className="mt-3 space-y-0">
                <InfoRow label="Status"    value={
                  <span className={`font-semibold ${profile?.is_active ? 'text-green-600' : 'text-red-500'}`}>
                    {profile?.is_active ? t('enrollment.active') : t('enrollment.inactive')}
                  </span>
                } />
                {profile?.age != null && <InfoRow label="Age" value={profile.age} />}
                <InfoRow label="Member since" value={formatDate(profile?.created_at)} />
              </div>
            </div>
          </div>

          {/* ── Edit / Save ── */}
          <div className="mt-4 border-t border-gray-100 pt-4">
            {!editing ? (
              <button onClick={startEdit}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition shadow-sm shadow-blue-200">
                Edit Profile
              </button>
            ) : (
              <form onSubmit={handleSave} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">First Name</label>
                    <input className={F} value={editForm.first_name}
                      onChange={e => setEditForm(f => ({ ...f, first_name: e.target.value }))} placeholder="First name" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">Last Name</label>
                    <input className={F} value={editForm.last_name}
                      onChange={e => setEditForm(f => ({ ...f, last_name: e.target.value }))} placeholder="Last name" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Display Name</label>
                  <input className={F} value={editForm.display_name}
                    onChange={e => setEditForm(f => ({ ...f, display_name: e.target.value }))} placeholder="How your name appears" />
                </div>
                <div className="w-28">
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Age</label>
                  <input className={F} type="number" min={1} max={120} value={editForm.age}
                    onChange={e => setEditForm(f => ({ ...f, age: e.target.value }))} placeholder="Age" />
                </div>
                {saveError && <p className="text-xs text-red-500">{saveError}</p>}
                <div className="flex gap-2">
                  <button type="submit" disabled={saving}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-semibold rounded-xl transition">
                    {saving ? 'Saving…' : 'Save Changes'}
                  </button>
                  <button type="button" onClick={cancelEdit}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-semibold rounded-xl transition">
                    Cancel
                  </button>
                </div>
              </form>
            )}
            {saveOk && <p className="text-xs text-green-600 mt-2 font-semibold">Profile updated successfully.</p>}
          </div>
        </div>

        {/* ── Role-specific section ── */}
        {renderRoleSection()}

      </div>
    </DashboardLayout>
  );
};

export default ProfilePage;
