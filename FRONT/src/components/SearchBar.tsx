import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/apiService';

interface SearchResult {
  type: string;
  id: string;
  title: string;
  subtitle?: string;
  status?: string;
}

const TYPE_ICON: Record<string, string> = {
  course: '📚',
  student: '👨‍🎓',
  teacher: '👩‍🏫',
};

export const SearchBar: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqSeqRef = useRef(0);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const seq = ++reqSeqRef.current;
      setLoading(true);
      try {
        const r = await apiService.search(query.trim());
        if (seq !== reqSeqRef.current) return; // stale response — discard
        setResults(r.data.results);
        setOpen(true);
      } catch {
        if (seq === reqSeqRef.current) setResults([]);
      } finally {
        if (seq === reqSeqRef.current) setLoading(false);
      }
    }, 350);
  }, [query]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative w-48" ref={containerRef}>
      <div className="flex items-center gap-2 bg-gray-100 rounded-xl px-3 py-1.5">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" className="text-gray-400 flex-shrink-0">
          <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search…"
          className="bg-transparent text-xs text-gray-700 outline-none w-full placeholder:text-gray-400"
        />
        {loading && <span className="text-[10px] text-gray-400 flex-shrink-0">…</span>}
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-9 left-0 w-72 bg-white rounded-2xl shadow-xl border border-gray-100 z-50 max-h-64 overflow-y-auto">
          {results.map(r => (
            <div
              key={`${r.type}-${r.id}`}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0"
              onClick={() => { setOpen(false); setQuery(''); }}
            >
              <span className="text-base">{TYPE_ICON[r.type] ?? '🔍'}</span>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-gray-800 truncate">{r.title}</p>
                {r.subtitle && <p className="text-[10px] text-gray-400 truncate">{r.subtitle}</p>}
              </div>
              {r.status && (
                <span className={`ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${
                  r.status === 'published' ? 'bg-green-100 text-green-700' :
                  r.status === 'draft' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
                }`}>{r.status}</span>
              )}
            </div>
          ))}
        </div>
      )}
      {open && !loading && results.length === 0 && query.trim() && (
        <div className="absolute top-9 left-0 w-72 bg-white rounded-2xl shadow-xl border border-gray-100 z-50 px-4 py-4 text-xs text-gray-400 text-center">
          No results for "{query}"
        </div>
      )}
    </div>
  );
};
