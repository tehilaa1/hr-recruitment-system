import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, Library, Loader2, RefreshCw, Search, UserPlus, Users } from 'lucide-react';
import { apiErrorMessage, searchApi } from '../api/client';
import CandidateProfileModal from '../components/CandidateProfileModal';
import Navbar from '../components/Navbar';
import StatusBadge from '../components/StatusBadge';
import { REFERRER_LABEL } from '../constants/referrals';

const Empty = () => <span className="text-gray-300">—</span>;

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('he-IL', { year: 'numeric', month: 'short', day: 'numeric' });

const digits = (v) => String(v || '').replace(/\D/g, '');

const SOURCE_FILTERS = [
  { value: '', label: 'כל המועמדים' },
  { value: 'applied', label: 'הגישו למשרה' },
  { value: 'pool-only', label: 'במאגר בלבד' },
  { value: 'referred', label: 'הגיעו בהמלצה' },
];

const SELECT =
  'border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent';

function matchesQuery(p, q) {
  if (!q) return true;
  const text = [p.full_name, p.family_name, p.profession, ...(p.emails ?? []), ...(p.referrers ?? []),
    ...(p.applications ?? []).map((a) => a.job_title)]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  if (text.includes(q.toLowerCase())) return true;
  const qDigits = digits(q);
  return qDigits.length >= 3 && (p.phones ?? []).some((ph) => digits(ph).includes(qDigits));
}

function matchesSource(p, source) {
  const applied = (p.applications ?? []).length > 0;
  if (source === 'applied') return applied;
  if (source === 'pool-only') return !applied && p.in_talent_pool;
  if (source === 'referred') return (p.referrers ?? []).length > 0;
  return true;
}

/* Every person once: job applications + talent pool, merged by email / phone */
export default function AllCandidates() {
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('');
  const [referrer, setReferrer] = useState('');
  const [selected, setSelected] = useState(null);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true); else setLoading(true);
    setError('');
    try {
      const { data } = await searchApi.people();
      setPeople(data);
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בטעינת המועמדים'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const referrers = useMemo(() => {
    const counts = new Map();
    people.forEach((p) => (p.referrers ?? []).forEach((r) => counts.set(r, (counts.get(r) || 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'he'));
  }, [people]);

  const filtered = useMemo(
    () =>
      people.filter(
        (p) =>
          matchesQuery(p, query.trim()) &&
          matchesSource(p, source) &&
          (!referrer || (p.referrers ?? []).includes(referrer))
      ),
    [people, query, source, referrer]
  );

  const stats = useMemo(() => ({
    applications: people.reduce((n, p) => n + (p.applications?.length ?? 0), 0),
    referred: people.filter((p) => p.referrers?.length).length,
  }), [people]);

  const filtersActive = query.trim() || source || referrer;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl p-3 bg-indigo-100 text-indigo-600">
              <Users className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">כל המועמדים</h1>
              <p className="text-sm text-gray-400 mt-0.5">
                כל אדם פעם אחת – מכל המשרות וממאגר המועמדים, מאוחד לפי מייל או טלפון
              </p>
            </div>
          </div>
          {!loading && !error && (
            <p className="text-sm text-gray-500 tabular-nums">
              {people.length} מועמדים · {stats.applications} מועמדויות · {stats.referred} בהמלצת עובד/ת
            </p>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 px-6 py-4 border-b border-gray-100">
            <div className="relative flex-1 min-w-[220px] max-w-sm">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="חיפוש לפי שם, מייל, טלפון, משרה, ממליץ…"
                className="w-full border border-gray-200 rounded-lg pr-9 pl-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <select value={source} onChange={(e) => setSource(e.target.value)} className={SELECT} aria-label="סינון לפי מקור">
              {SOURCE_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            <select value={referrer} onChange={(e) => setReferrer(e.target.value)} className={SELECT} aria-label={`סינון לפי ${REFERRER_LABEL}`}>
              <option value="">{REFERRER_LABEL}: כולם</option>
              {referrers.map(([name, count]) => <option key={name} value={name}>{name} ({count})</option>)}
            </select>
            {filtersActive && (
              <button
                onClick={() => { setQuery(''); setSource(''); setReferrer(''); }}
                className="text-xs text-indigo-600 hover:underline"
              >
                ניקוי סינון
              </button>
            )}
            <button
              onClick={() => load({ silent: true })}
              disabled={refreshing || loading}
              className="mr-auto p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              title="רענון"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center py-20"><Loader2 className="h-7 w-7 text-indigo-500 animate-spin" /></div>
          ) : error ? (
            <div className="flex flex-col items-center py-16 gap-3">
              <p className="text-gray-500">{error}</p>
              <button onClick={() => load()} className="flex items-center gap-2 text-sm text-indigo-600 hover:underline">
                <RefreshCw className="h-4 w-4" /> נסה שנית
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center py-16 gap-2 text-center">
              <Users className="h-8 w-8 text-gray-300" />
              <p className="text-gray-500">{people.length ? 'אין מועמדים התואמים לסינון' : 'אין מועמדים עדיין'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200 text-xs text-gray-500">
                    {['שם', 'טלפון', 'מייל', 'מקצוע', 'מועמדות אחרונה', 'מועמדויות', REFERRER_LABEL, 'פעילות אחרונה'].map((h) => (
                      <th key={h} className="px-4 py-3 text-right font-semibold whitespace-nowrap">{h}</th>
                    ))}
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((p) => {
                    const latest = p.applications?.[0];
                    const refs = p.referrers ?? [];
                    return (
                      <tr
                        key={p.key}
                        onClick={() => setSelected(p)}
                        className="hover:bg-indigo-50/40 cursor-pointer"
                        title="פתיחת פרופיל והיסטוריית מועמדויות"
                      >
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="font-semibold text-gray-900">
                            {[p.full_name, p.family_name].filter(Boolean).join(' ') || 'ללא שם'}
                          </span>
                          {p.in_talent_pool && (
                            <Library className="inline h-3.5 w-3.5 text-teal-500 mr-1.5 align-[-2px]" aria-label="במאגר המועמדים" />
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap font-mono text-xs text-gray-700" dir="ltr">
                          {p.phones?.[0] || <Empty />}
                        </td>
                        <td className="px-4 py-3 max-w-[200px] truncate text-xs text-gray-700" title={p.emails?.join(', ')}>
                          {p.emails?.[0] || <Empty />}
                        </td>
                        <td className="px-4 py-3 max-w-[150px] truncate text-gray-700" title={p.profession}>
                          {p.profession || <Empty />}
                        </td>
                        <td className="px-4 py-3">
                          {latest ? (
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="truncate max-w-[160px] text-gray-800" title={latest.job_title}>{latest.job_title}</span>
                              <StatusBadge status={latest.recruitment_status} />
                            </div>
                          ) : (
                            <span className="text-xs text-gray-400">במאגר בלבד</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center tabular-nums">
                          {p.applications?.length ? (
                            <span className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs font-medium">{p.applications.length}</span>
                          ) : <Empty />}
                        </td>
                        <td className="px-4 py-3">
                          {refs.length ? (
                            <span className="inline-flex items-center gap-1 text-xs text-violet-700" title={refs.join(', ')}>
                              <UserPlus className="h-3 w-3 flex-shrink-0" />
                              <span className="truncate max-w-[130px]">{refs[0]}</span>
                              {refs.length > 1 && <span className="text-violet-400">+{refs.length - 1}</span>}
                            </span>
                          ) : <Empty />}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                          {p.last_activity ? formatDate(p.last_activity) : <Empty />}
                        </td>
                        <td className="px-2 py-3 text-gray-300"><ChevronLeft className="h-4 w-4" /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {selected && <CandidateProfileModal profile={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
