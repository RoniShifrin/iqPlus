import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { useApp } from '../contexts/AppContext';
import { useAuth } from '../contexts/AuthContext';
import { apiService } from '../services/apiService';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface MaterialRow {
  id: string;
  course_id: string;
  course_name: string;
  child_name?: string;
  title: string;
  file_url?: string;
  link_url?: string;
  created_at: string;
}

const getExt = (url?: string): string => {
  if (!url) return '';
  const seg = url.split('.').pop() ?? '';
  return seg.length <= 5 ? seg.toUpperCase() : '';
};

// Shared row renderer used by both table components
const MaterialActionCell: React.FC<{ m: MaterialRow; t: (k: string) => string; apiUrl: string }> = ({ m, t, apiUrl }) => {
  const isFile = !!m.file_url;
  const ext    = isFile ? getExt(m.file_url) : 'LINK';
  const href   = isFile ? `${apiUrl}${m.file_url}` : m.link_url;
  return (
    <tr className="hover:bg-gray-50/60 transition">
      <td className="py-3 px-4 max-w-[240px]">
        <div className="flex items-center gap-2.5">
          <span className="text-base flex-shrink-0">{isFile ? '📄' : '🔗'}</span>
          <span className="font-medium text-gray-800 truncate">{m.title}</span>
        </div>
      </td>
      <td className="py-3 px-4">
        <span className="text-xs font-mono text-gray-400">{ext || '—'}</span>
      </td>
      <td className="py-3 px-4 text-xs text-gray-400 whitespace-nowrap">
        {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
      </td>
      <td className="py-3 px-4">
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer"
            className="inline-block text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition font-medium"
          >
            {isFile ? t('materials.download') : t('materials.open')}
          </a>
        ) : (
          <span className="text-xs text-gray-300">—</span>
        )}
      </td>
    </tr>
  );
};

// Flat table for non-parent roles
const MaterialsTable: React.FC<{ rows: MaterialRow[]; t: (k: string) => string; apiUrl: string }> = ({ rows, t, apiUrl }) => (
  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-100 bg-gray-50/70">
          {[t('materials.colMaterial'), t('materials.colCourse'), t('materials.colType'), t('materials.colDate'), t('materials.colAction')].map(h => (
            <th key={h} className="text-left text-gray-500 font-semibold text-xs py-3 px-4">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-50">
        {rows.map(m => {
          const isFile = !!m.file_url;
          const ext    = isFile ? getExt(m.file_url) : 'LINK';
          const href   = isFile ? `${apiUrl}${m.file_url}` : m.link_url;
          return (
            <tr key={m.id} className="hover:bg-gray-50/60 transition">
              <td className="py-3 px-4 max-w-[240px]">
                <div className="flex items-center gap-2.5">
                  <span className="text-base flex-shrink-0">{isFile ? '📄' : '🔗'}</span>
                  <span className="font-medium text-gray-800 truncate">{m.title}</span>
                </div>
              </td>
              <td className="py-3 px-4">
                <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">
                  {m.course_name}
                </span>
              </td>
              <td className="py-3 px-4">
                <span className="text-xs font-mono text-gray-400">{ext || '—'}</span>
              </td>
              <td className="py-3 px-4 text-xs text-gray-400 whitespace-nowrap">
                {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
              </td>
              <td className="py-3 px-4">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer"
                    className="inline-block text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition font-medium"
                  >
                    {isFile ? t('materials.download') : t('materials.open')}
                  </a>
                ) : (
                  <span className="text-xs text-gray-300">—</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

// Grouped view for parent role: Child → Course → materials
const ParentGroupedMaterials: React.FC<{ rows: MaterialRow[]; t: (k: string) => string; apiUrl: string }> = ({ rows, t, apiUrl }) => {
  // Group by child_name → course_name → rows
  const byChild: Record<string, Record<string, MaterialRow[]>> = {};
  rows.forEach(m => {
    const child  = m.child_name || '—';
    const course = m.course_name || '—';
    if (!byChild[child]) byChild[child] = {};
    if (!byChild[child][course]) byChild[child][course] = [];
    byChild[child][course].push(m);
  });

  return (
    <div className="space-y-6">
      {Object.entries(byChild).map(([childName, byCourse]) => (
        <div key={childName}>
          {/* Child header */}
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">👤</span>
            <h2 className="text-base font-bold text-gray-800">{childName}</h2>
          </div>

          <div className="space-y-4 pl-4 border-l-2 border-blue-100">
            {Object.entries(byCourse).map(([courseName, courseRows]) => (
              <div key={courseName}>
                {/* Course sub-header */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm">📚</span>
                  <span className="text-sm font-semibold text-blue-700">{courseName}</span>
                  <span className="text-xs text-gray-400">({courseRows.length})</span>
                </div>

                <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 bg-gray-50/70">
                        {[t('materials.colMaterial'), t('materials.colType'), t('materials.colDate'), t('materials.colAction')].map(h => (
                          <th key={h} className="text-left text-gray-500 font-semibold text-xs py-2.5 px-4">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {courseRows.map(m => <MaterialActionCell key={m.id} m={m} t={t} apiUrl={apiUrl} />)}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export const MaterialsPage: React.FC = () => {
  const { t } = useApp();
  const { user } = useAuth();
  const isParent = user?.role === 'parent';
  const [rows, setRows]         = useState<MaterialRow[]>([]);
  const [courses, setCourses]   = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState('');
  const [courseFilter, setCourseFilter] = useState('');
  const [typeFilter, setTypeFilter]     = useState('');

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const dash = await apiService.getDashboard();
      const dashCourses: any[] = dash.data?.courses ?? [];
      setCourses(dashCourses.map((c: any) => ({ id: c.id, name: c.name })));

      // For parent: build course_id → child_name map from children_info
      const childOfCourse: Record<string, string> = {};
      if (isParent) {
        const children: any[] = dash.data?.metrics?.children ?? [];
        children.forEach((ch: any) => {
          (ch.course_ids ?? []).forEach((cid: string) => {
            if (!childOfCourse[cid]) childOfCourse[cid] = ch.name;
          });
        });
      }

      // Fetch materials for every accessible course in parallel
      const chunks = await Promise.all(
        dashCourses.map(async (c: any) => {
          try {
            const r = await apiService.getMaterials(c.id);
            return (r.data ?? []).map((m: any) => ({
              ...m,
              course_name: c.name,
              child_name: childOfCourse[c.id] ?? '',
            }));
          } catch {
            return [];
          }
        })
      );

      const all: MaterialRow[] = (chunks.flat() as MaterialRow[]).sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setRows(all);
    } catch {
      /* silent — dashboard errors surface on the dashboard itself */
    } finally {
      setLoading(false);
    }
  };

  const filtered = rows.filter(m => {
    if (search) {
      const q = search.toLowerCase();
      if (!m.title.toLowerCase().includes(q) && !m.course_name.toLowerCase().includes(q)) return false;
    }
    if (courseFilter && m.course_id !== courseFilter) return false;
    if (typeFilter === 'file' && !m.file_url) return false;
    if (typeFilter === 'link' && !m.link_url) return false;
    return true;
  });

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{t('materials.title')}</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {filtered.length} {t('materials.colMaterial').toLowerCase()}{filtered.length !== 1 ? 's' : ''} · {courses.length} {t('nav.courses').toLowerCase()}{courses.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={load}
            className="text-xs text-gray-400 hover:text-blue-600 border border-gray-200 rounded-lg px-3 py-1.5 transition"
          >
            {t('materials.refresh')}
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-5">
          <input
            type="text"
            placeholder={t('materials.searchPlaceholder')}
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 min-w-[180px] border border-gray-200 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white"
          />
          <select
            value={courseFilter}
            onChange={e => setCourseFilter(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white"
          >
            <option value="">{t('materials.allCourses')}</option>
            {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300 bg-white"
          >
            <option value="">{t('materials.allTypes')}</option>
            <option value="file">{t('materials.files')}</option>
            <option value="link">{t('materials.links')}</option>
          </select>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex justify-center py-24">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-24 text-gray-400">
            <div className="text-5xl mb-4">📂</div>
            <p className="text-lg font-semibold text-gray-600">
              {rows.length === 0 ? t('materials.noMaterials') : t('materials.noMatch')}
            </p>
            <p className="text-sm mt-1">
              {rows.length === 0
                ? t('materials.hint')
                : t('materials.tryClearing')}
            </p>
            {(search || courseFilter || typeFilter) && (
              <button
                onClick={() => { setSearch(''); setCourseFilter(''); setTypeFilter(''); }}
                className="mt-3 text-sm text-blue-600 hover:underline"
              >
                {t('materials.clearFilters')}
              </button>
            )}
          </div>
        ) : isParent ? (
          // Parent view: grouped by child → course
          <ParentGroupedMaterials rows={filtered} t={t} apiUrl={API_URL} />
        ) : (
          <MaterialsTable rows={filtered} t={t} apiUrl={API_URL} />
        )}
      </div>
    </DashboardLayout>
  );
};
