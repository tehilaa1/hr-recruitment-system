import { useEffect, useRef, useState } from 'react';
import { Loader2, Search, X } from 'lucide-react';
import { searchApi } from '../api/client';
import CandidateProfileModal from './CandidateProfileModal';
import StatusBadge from './StatusBadge';

const MIN_CHARS = 2;
const DEBOUNCE_MS = 300;

const fullName = (p) =>
  [p.full_name, p.family_name].filter(Boolean).join(' ') || 'ללא שם';

/* Search candidates across all jobs; selecting a result opens their profile */
export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [selected, setSelected] = useState(null);
  const containerRef = useRef(null);

  const trimmed = query.trim();

  // Debounced search; aborts the previous request when the query changes
  useEffect(() => {
    if (trimmed.length < MIN_CHARS) {
      setResults([]);
      setLoading(false);
      setError(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const { data } = await searchApi.candidates(trimmed, { signal: controller.signal });
        setResults(data);
        setError(false);
        setActiveIndex(-1);
      } catch (e) {
        if (e.name !== 'CanceledError') setError(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const select = (profile) => {
    setSelected(profile);
    setOpen(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setOpen(false);
      e.currentTarget.blur();
      return;
    }
    if (!results.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setOpen(true);
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      select(results[activeIndex >= 0 ? activeIndex : 0]);
    }
  };

  const showDropdown = open && trimmed.length >= MIN_CHARS;

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="חיפוש מועמד בכל המשרות – שם, מייל או טלפון"
          aria-label="חיפוש מועמדים גלובלי"
          className="w-full bg-gray-100 focus:bg-white border border-transparent focus:border-blue-300 focus:ring-2 focus:ring-blue-100 rounded-xl py-2 pr-9 pl-9 text-sm outline-none transition-colors [&::-webkit-search-cancel-button]:hidden"
        />
        {loading ? (
          <Loader2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-500 animate-spin" />
        ) : (
          query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700"
              title="נקה"
            >
              <X className="h-4 w-4" />
            </button>
          )
        )}
      </div>

      {showDropdown && (
        <div className="absolute top-full mt-2 w-full bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden animate-fade-in">
          {error ? (
            <p className="px-4 py-3 text-sm text-red-600">שגיאה בחיפוש. נסה שנית.</p>
          ) : results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-gray-500">
              {loading ? 'מחפש...' : `לא נמצאו מועמדים עבור "${trimmed}"`}
            </p>
          ) : (
            <ul className="max-h-96 overflow-y-auto divide-y divide-gray-50">
              {results.map((p, i) => {
                const latest = p.applications?.[0];
                return (
                  <li key={p.key}>
                    <button
                      type="button"
                      onMouseEnter={() => setActiveIndex(i)}
                      onClick={() => select(p)}
                      className={`w-full text-right px-4 py-3 flex items-center justify-between gap-3 transition-colors ${
                        i === activeIndex ? 'bg-blue-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">{fullName(p)}</p>
                        <p className="text-xs text-gray-500 truncate mt-0.5">
                          {[p.emails?.[0], p.phones?.[0]].filter(Boolean).join(' · ') || '—'}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 flex-shrink-0">
                        {latest && <StatusBadge status={latest.recruitment_status} />}
                        <span className="text-[11px] text-gray-400">
                          {p.applications.length === 1
                            ? latest.job_title
                            : `${p.applications.length} משרות`}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {selected && (
        <CandidateProfileModal profile={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
