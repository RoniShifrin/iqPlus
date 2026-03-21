import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { apiService } from '../services/apiService';

const DAY_EN = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] as const;

interface FormState {
  code: string;
  name: string;
  description: string;
  capacity: number;
  visibility_scope: string;
  days: string[];
  start_time: string;
  end_time: string;
  teacherId: string; // Admin-only: which teacher to assign
}

interface TeacherOption { id: string; first_name: string; last_name: string; }

export const CourseFormPage: React.FC = () => {
  const { id } = useParams<{ id?: string }>();
  const isEdit = Boolean(id);
  const { user } = useAuth();
  const { t } = useApp();
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>({
    code: '', name: '', description: '', capacity: 30,
    visibility_scope: 'school_only', days: [], start_time: '09:00', end_time: '10:00',
    teacherId: '',
  });
  const [loading, setLoading]     = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]          = useState('');
  const [teachers, setTeachers]    = useState<TeacherOption[]>([]);

  useEffect(() => {
    if (user && user.role !== 'admin' && user.role !== 'teacher') {
      navigate('/', { replace: true });
    }
  }, [user]);

  // Admin only: load teacher list for the assignment selector (create mode only)
  useEffect(() => {
    if (user?.role === 'admin' && !isEdit) {
      apiService.getAdminUsers('teacher')
        .then(r => setTeachers(
          (r.data ?? []).filter((t: any) => t.is_active && !t.deleted_at)
        ))
        .catch(() => {});
    }
  }, [user?.role, isEdit]);

  useEffect(() => {
    if (!isEdit || !id) return;
    apiService.getCourse(id)
      .then((r) => {
        const c = r.data;
        // Teachers may only edit their own courses — block access before rendering the form
        if (user?.role === 'teacher' && c.teacher_id !== (user as any).id) {
          setError('You do not have permission to edit this course.');
          return;
        }
        setForm({
          code: c.code, name: c.name, description: c.description || '',
          capacity: c.capacity, visibility_scope: c.visibility_scope,
          days: c.schedule?.days || [],
          start_time: c.schedule?.start_time || '09:00',
          end_time:   c.schedule?.end_time   || '10:00',
          teacherId: '', // not used in edit mode
        });
      })
      .catch(() => setError('Could not load course.'))
      .finally(() => setLoading(false));
  }, [id, user]);

  const DAYS = DAY_EN.map(d => ({ key: d, label: t(`courseForm.day.${d.toLowerCase()}`) }));
  const VISIBILITY_OPTIONS = [
    { value: 'school_only',  label: t('courseForm.vis.schoolOnly')  },
    { value: 'public',       label: t('courseForm.vis.public')       },
    { value: 'teacher_only', label: t('courseForm.vis.teacherOnly')  },
  ];

  const toggleDay = (day: string) =>
    setForm((f) => ({
      ...f,
      days: f.days.includes(day) ? f.days.filter((d) => d !== day) : [...f.days, day],
    }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');

    const payload: Record<string, any> = {
      code: form.code,
      name: form.name,
      description: form.description || undefined,
      capacity: Number(form.capacity),
      visibility_scope: form.visibility_scope,
      schedule: form.days.length > 0
        ? { days: form.days, start_time: form.start_time, end_time: form.end_time }
        : undefined,
    };
    // Admin must pick a teacher; teacher is auto-assigned on the backend
    if (user?.role === 'admin' && !isEdit) {
      payload.teacher_id = form.teacherId;
    }

    try {
      if (isEdit && id) {
        await apiService.updateCourse(id, payload);
      } else {
        await apiService.createCourse(payload);
      }
      navigate('/courses');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save course.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen text-gray-500">{t('common.loading')}</div>;
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-6">
        <button onClick={() => navigate('/courses')} className="text-indigo-600 hover:underline text-sm">
          {t('courseForm.backToCourses')}
        </button>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">
          {isEdit ? t('courseForm.editCourse') : t('courseForm.createNewCourse')}
        </h1>
      </div>

      {error && (
        <div className="mb-5 p-3 bg-red-50 border border-red-300 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow p-6 space-y-5">

        {/* Code */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.courseCode')}</label>
          <input
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
            placeholder="e.g. MATH101"
            required
            disabled={isEdit}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:bg-gray-50 disabled:text-gray-400"
          />
          {isEdit && <p className="text-xs text-gray-400 mt-1">{t('courseForm.codeCannotChange')}</p>}
        </div>

        {/* Name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.courseName')}</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Mathematics — Grade 10"
            required
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.description')}</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={3}
            placeholder={t('courseForm.descPlaceholder')}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
          />
        </div>

        {/* Teacher assignment — Admin only, create mode only */}
        {user?.role === 'admin' && !isEdit && (
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.assignTeacher')}</label>
            <select
              required
              value={form.teacherId}
              onChange={(e) => setForm({ ...form, teacherId: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option value="">{t('courseForm.selectTeacher')}</option>
              {teachers.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.first_name} {t.last_name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Capacity + Visibility */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.capacity')}</label>
            <input
              type="number" min={1} max={500}
              value={form.capacity}
              onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">{t('courseForm.visibility')}</label>
            <select
              value={form.visibility_scope}
              onChange={(e) => setForm({ ...form, visibility_scope: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              {VISIBILITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Schedule */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">{t('courseForm.schedule')}</label>
          <div className="flex flex-wrap gap-2 mb-3">
            {DAYS.map(({ key, label }) => (
              <button
                key={key} type="button" onClick={() => toggleDay(key)}
                className={`px-3 py-1 rounded-full text-xs font-semibold border transition ${
                  form.days.includes(key)
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {form.days.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('courseForm.startTime')}</label>
                <input type="time" value={form.start_time}
                  onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">{t('courseForm.endTime')}</label>
                <input type="time" value={form.end_time}
                  onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={submitting}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white font-bold py-2.5 rounded-lg transition">
            {submitting ? t('courseForm.saving') : isEdit ? t('courseForm.saveChanges') : t('courseForm.createCourse')}
          </button>
          <button type="button" onClick={() => navigate('/courses')}
            className="px-5 border border-gray-300 text-gray-600 hover:bg-gray-50 rounded-lg transition">
            {t('courseForm.cancel')}
          </button>
        </div>
      </form>

      <div className="mt-4 p-3 bg-blue-50 rounded-lg text-xs text-blue-700">
        {t('courseForm.draftNote')}
      </div>
    </div>
  );
};
