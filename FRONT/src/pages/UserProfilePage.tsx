import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

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

const ROLE_GRADIENT: Record<string, string> = {
  admin:   'from-purple-400 to-purple-600',
  teacher: 'from-blue-400 to-blue-600',
  student: 'from-green-400 to-green-600',
  parent:  'from-orange-400 to-orange-600',
};

const ROLE_BADGE: Record<string, string> = {
  admin:   'bg-purple-100 text-purple-700',
  teacher: 'bg-blue-100 text-blue-700',
  student: 'bg-green-100 text-green-700',
  parent:  'bg-orange-100 text-orange-700',
};

const UserProfilePage: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const { user: currentUser } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!userId) return;
    // Own profile → redirect to /profile
    if (userId === currentUser?.id) {
      navigate('/profile', { replace: true });
      return;
    }
    apiService.getUserProfile(userId)
      .then(r => { if (r.data) setProfile(r.data); else setError('Profile not found.'); })
      .catch((err: any) => {
        const status = err?.response?.status;
        if (status === 403) setError('You do not have permission to view this profile.');
        else if (status === 404) setError('Profile not found.');
        else setError('Unable to load profile. Please try again.');
      })
      .finally(() => setLoading(false));
  }, [userId, currentUser?.id]);

  const displayName = profile
    ? (profile.display_name || [profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.email || '?')
    : '?';
  const role: string = profile?.role ?? '';

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto px-4 py-6">
        {loading ? (
          <div className="py-16 text-center text-sm text-gray-400">Loading…</div>
        ) : error || !profile ? (
          <div className="py-16 text-center text-sm text-gray-400">{error || 'Profile not found.'}</div>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-5">
            <div className="flex items-start gap-5">
              {/* Avatar */}
              <div className="flex-shrink-0">
                {profile.avatar_url ? (
                  <img
                    src={`${API_URL}${profile.avatar_url}`}
                    alt={displayName}
                    className="w-[88px] h-[88px] rounded-full object-cover border border-gray-100 shadow-sm"
                  />
                ) : (
                  <div className={`w-[88px] h-[88px] rounded-full bg-gradient-to-br ${ROLE_GRADIENT[role] ?? 'from-gray-300 to-gray-500'} flex items-center justify-center text-white font-black text-2xl`}>
                    {(displayName || '?').slice(0, 2).toUpperCase()}
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-xl font-black text-gray-900 truncate">{displayName}</h2>
                  <span className={`flex-shrink-0 text-xs font-bold px-2.5 py-1 rounded-full capitalize ${ROLE_BADGE[role] ?? 'bg-gray-100 text-gray-600'}`}>
                    {capitalize(role)}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-0.5">{profile.email}</p>
                <div className="mt-3 space-y-0">
                  <InfoRow label="Status" value={
                    <span className={`font-semibold ${profile.is_active ? 'text-green-600' : 'text-red-500'}`}>
                      {profile.is_active ? t('enrollment.active') : t('enrollment.inactive')}
                    </span>
                  } />
                  {profile.age != null && <InfoRow label="Age" value={profile.age} />}
                  <InfoRow label="Member since" value={formatDate(profile.created_at)} />
                </div>
              </div>
            </div>

            {/* Courses section */}
            <div className="border-t border-gray-100 pt-4">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                {role === 'teacher' ? 'Teaching' : role === 'parent' ? 'Children\'s Courses' : 'Enrolled Courses'}
              </h3>
              {profile.courses && profile.courses.length > 0 ? (
                <div className="space-y-1.5">
                  {profile.courses.map((c: any) => (
                    <div key={c.id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-50 text-sm">
                      <span className="font-medium text-gray-800">{c.name}</span>
                      <span className="text-xs text-gray-400 ml-2 flex-shrink-0">{c.code}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400">No courses.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default UserProfilePage;
