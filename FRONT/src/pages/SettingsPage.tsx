import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { AvatarUpload } from '../components/AvatarUpload';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import type { Lang } from '../i18n/translations';
import { apiService } from '../services/apiService';
import { safeStorage } from '../utils/safeStorage';

/* ── localStorage keys for notification preferences ── */
const PREF_KEYS = {
  emailAlerts:    'notif_email_alerts',
  weeklySummary:  'notif_weekly_summary',
  feedbackNotif:  'notif_feedback',
  systemNotif:    'notif_system',
  childUpdates:   'notif_child_updates',
  courseUpdates:  'notif_course_updates',
};

const getPref = (key: string, def = true): boolean => {
  const v = safeStorage.getItem(key);
  return v === null ? def : v === 'true';
};
const setPref = (key: string, val: boolean) => safeStorage.setItem(key, String(val));

/* ── Small reusable toggle ── */
const Toggle: React.FC<{ label: string; description?: string; value: boolean; onChange: (v: boolean) => void }> = ({
  label, description, value, onChange,
}) => (
  <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
    <div>
      <p className="text-sm font-medium text-gray-800">{label}</p>
      {description && <p className="text-xs text-gray-400 mt-0.5">{description}</p>}
    </div>
    <button
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full transition-colors duration-200 focus:outline-none ${value ? 'bg-blue-600' : 'bg-gray-300'}`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 mt-0.5 ${value ? 'translate-x-4' : 'translate-x-0.5'}`} />
    </button>
  </div>
);

/* ── Section card wrapper ── */
const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-5">
    <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-4">{title}</h3>
    {children}
  </div>
);

export const SettingsPage: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const { t, lang, theme, setLang, setTheme } = useApp();
  const role = user?.role || 'student';

  /* ── Profile form state ── */
  const [firstName, setFirstName]     = useState('');
  const [lastName, setLastName]       = useState('');
  const [displayName, setDisplayName] = useState('');
  const [saving, setSaving]           = useState(false);
  const [saveMsg, setSaveMsg]         = useState<{ ok: boolean; text: string } | null>(null);

  /* ── Notification prefs (localStorage) ── */
  const [prefs, setPrefs] = useState({
    emailAlerts:   getPref(PREF_KEYS.emailAlerts),
    weeklySummary: getPref(PREF_KEYS.weeklySummary),
    feedbackNotif: getPref(PREF_KEYS.feedbackNotif),
    systemNotif:   getPref(PREF_KEYS.systemNotif),
    childUpdates:  getPref(PREF_KEYS.childUpdates),
    courseUpdates: getPref(PREF_KEYS.courseUpdates),
  });

  useEffect(() => {
    apiService.getProfile().then(r => {
      const d = r.data;
      setFirstName(d.first_name || '');
      setLastName(d.last_name || '');
      setDisplayName(d.display_name || '');
    }).catch(() => {});
  }, []);

  const handleToggle = (key: keyof typeof prefs) => (val: boolean) => {
    setPref(PREF_KEYS[key], val);
    setPrefs(p => ({ ...p, [key]: val }));
  };

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      await apiService.updateProfile({
        first_name:   firstName   || undefined,
        last_name:    lastName    || undefined,
        display_name: displayName || undefined,
      });
      await refreshUser();
      setSaveMsg({ ok: true, text: t('settings.saveSuccess') });
    } catch {
      setSaveMsg({ ok: false, text: t('settings.saveError') });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 4000);
    }
  };

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto">
        {/* Page header */}
        <div className="mb-6">
          <h1 className="text-2xl font-black text-gray-900">{t('settings.title')}</h1>
          <p className="text-sm text-gray-400 mt-1">{t('settings.subtitle')}</p>
        </div>

        {/* ── Profile section ── */}
        <Section title={t('settings.profile')}>
          <div className="flex items-center gap-5 mb-6 pb-5 border-b border-gray-100">
            <AvatarUpload size={72} />
            <div>
              <p className="text-sm font-semibold text-gray-700">{t('settings.profilePhoto')}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t('settings.profilePhotoHint')}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">{t('settings.firstName')}</label>
              <input
                type="text"
                value={firstName}
                onChange={e => setFirstName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder={t('settings.firstName.placeholder')}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1">{t('settings.lastName')}</label>
              <input
                type="text"
                value={lastName}
                onChange={e => setLastName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                placeholder={t('settings.lastName.placeholder')}
              />
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs font-semibold text-gray-500 mb-1">{t('settings.displayName')}</label>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              placeholder={t('settings.displayNameHint')}
            />
          </div>

          <div className="mb-5">
            <label className="block text-xs font-semibold text-gray-500 mb-1">{t('settings.email')}</label>
            <input
              type="email"
              value={user?.email || ''}
              readOnly
              className="w-full border border-gray-100 bg-gray-50 rounded-lg px-3 py-2 text-sm text-gray-400 cursor-not-allowed"
            />
            <p className="text-xs text-gray-400 mt-1">{t('settings.emailHint')}</p>
          </div>

          <div className="mb-5 flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-500">{t('settings.role')}:</span>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold capitalize
              ${role === 'admin'   ? 'bg-red-100 text-red-700'
              : role === 'teacher' ? 'bg-blue-100 text-blue-700'
              : role === 'student' ? 'bg-green-100 text-green-700'
              : 'bg-purple-100 text-purple-700'}`}>
              {t(`role.${role}`)}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveProfile}
              disabled={saving}
              className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-60 transition"
            >
              {saving ? t('settings.saving') : t('settings.saveProfile')}
            </button>
            {saveMsg && (
              <span className={`text-sm font-medium ${saveMsg.ok ? 'text-green-600' : 'text-red-500'}`}>
                {saveMsg.text}
              </span>
            )}
          </div>
        </Section>

        {/* ── Appearance ── */}
        <Section title={t('settings.appearance')}>
          <Toggle
            label={t('settings.darkMode')}
            description={t('settings.darkModeDesc')}
            value={theme === 'dark'}
            onChange={v => setTheme(v ? 'dark' : 'light')}
          />
          {/* Language selector */}
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-gray-800">{t('settings.language')}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t('settings.languageDesc')}</p>
            </div>
            <div className="flex gap-2">
              {(['en', 'he'] as Lang[]).map(l => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    lang === l
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                  }`}
                >
                  {t(`lang.${l}`)}
                </button>
              ))}
            </div>
          </div>
        </Section>

        {/* ── Notification Preferences ── */}
        <Section title={t('settings.notifPrefs')}>
          <Toggle
            label={t('settings.inAppNotif')}
            description={t('settings.inAppNotifDesc')}
            value={prefs.systemNotif}
            onChange={handleToggle('systemNotif')}
          />
          <Toggle
            label={t('settings.emailAlerts')}
            description={t('settings.emailAlertsDesc')}
            value={prefs.emailAlerts}
            onChange={handleToggle('emailAlerts')}
          />
          <Toggle
            label={t('settings.weeklySummary')}
            description={t('settings.weeklySummaryDesc')}
            value={prefs.weeklySummary}
            onChange={handleToggle('weeklySummary')}
          />
          <Toggle
            label={t('settings.feedbackNotif')}
            description={t('settings.feedbackNotifDesc')}
            value={prefs.feedbackNotif}
            onChange={handleToggle('feedbackNotif')}
          />
          {role === 'parent' && (
            <Toggle
              label={t('settings.childUpdates')}
              description={t('settings.childUpdatesDesc')}
              value={prefs.childUpdates}
              onChange={handleToggle('childUpdates')}
            />
          )}
          {(role === 'teacher' || role === 'student') && (
            <Toggle
              label={t('settings.courseUpdates')}
              description={t('settings.courseUpdatesDesc')}
              value={prefs.courseUpdates}
              onChange={handleToggle('courseUpdates')}
            />
          )}
        </Section>

        {/* ── Teacher-specific ── */}
        {role === 'teacher' && (
          <Section title={t('settings.teacherComm')}>
            <div className="text-sm text-gray-600 space-y-2">
              <p>{t('settings.teacherCommText1')}</p>
              <p className="text-xs text-gray-400">{t('settings.teacherCommText2')}</p>
            </div>
          </Section>
        )}

        {/* ── Admin-specific ── */}
        {role === 'admin' && (
          <Section title={t('settings.adminSystem')}>
            <div className="text-sm text-gray-600 space-y-2">
              <p>{t('settings.adminSystemText')}</p>
              <p className="text-xs text-gray-400">{t('settings.adminSystemText2')}</p>
            </div>
          </Section>
        )}

        {/* ── Student-specific ── */}
        {role === 'student' && (
          <Section title={t('settings.learningPrefs')}>
            <Toggle
              label={t('settings.showScores')}
              description={t('settings.showScoresDesc')}
              value={getPref('pref_show_scores', true)}
              onChange={v => { setPref('pref_show_scores', v); setPrefs(p => ({ ...p })); }}
            />
          </Section>
        )}

        {/* ── Parent-specific ── */}
        {role === 'parent' && (
          <Section title={t('settings.childOverview')}>
            <Toggle
              label={t('settings.showAllChildren')}
              description={t('settings.showAllChildrenDesc')}
              value={getPref('pref_expand_children', true)}
              onChange={v => setPref('pref_expand_children', v)}
            />
          </Section>
        )}

        {/* Password note */}
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <strong>{t('settings.passwordTitle')}:</strong> {t('settings.passwordText')}
        </div>
      </div>
    </DashboardLayout>
  );
};
