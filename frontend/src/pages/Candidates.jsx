import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  FileText,
  Library,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  UserPlus,
  Users,
} from 'lucide-react';
import { apiErrorMessage, candidatesApi, jobsApi, searchApi, talentPoolApi } from '../api/client';
import CandidateFormModal from '../components/CandidateFormModal';
import CandidateProfileModal from '../components/CandidateProfileModal';
import Navbar from '../components/Navbar';
import { ReferrerCell } from '../components/ReferrerInput';
import StatusBadge from '../components/StatusBadge';
import UploadBox from '../components/UploadBox';
import { REFERRER_LABEL } from '../constants/referrals';
import { cvSources, openCv } from '../utils/candidateCv';

const Empty = () => <span className="text-gray-300">—</span>;

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('he-IL', { year: 'numeric', month: 'short', day: 'numeric' });

const digits = (v) => String(v || '').replace(/\D/g, '');

const fullName = (p) => [p.full_name, p.family_name].filter(Boolean).join(' ');

const POOL = 'pool'; // upload / manual-add destination: the talent pool (no job)

const VIEWS = [
  { value: '', label: 'הכל', test: () => true },
  { value: 'pool-only', label: 'במאגר בלבד (לא שויכו)', test: (p) => !p.applications?.length },
  { value: 'applied', label: 'שויכו למשרות', test: (p) => p.applications?.length > 0 },
  { value: 'referred', label: 'בהמלצת עובד/ת', test: (p) => p.referrers?.length > 0 },
];

const EXPERIENCE_FILTERS = [
  { value: 0, label: 'כל רמות הניסיון' },
  { value: 1, label: 'שנה ומעלה' },
  { value: 3, label: '3 שנים ומעלה' },
  { value: 5, label: '5 שנים ומעלה' },
  { value: 10, label: '10 שנים ומעלה' },
];

const SELECT =
  'border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent';

function matchesQuery(p, q) {
  if (!q) return true;
  const text = [
    p.full_name, p.family_name, p.profession, p.address,
    ...(p.emails ?? []), ...(p.referrers ?? []),
    ...(p.applications ?? []).flatMap((a) => [a.job_title, a.file_name]),
    ...(p.talent_pool_entries ?? []).map((e) => e.file_name),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  if (text.includes(q.toLowerCase())) return true;
  const qDigits = digits(q);
  return qDigits.length >= 3 && (p.phones ?? []).some((ph) => digits(ph).includes(qDigits));
}

/* The one record whose referrer the table edits inline: the pool entry, or a single application.
   People with several applications edit each one in their profile. */
function editableReferrer(p) {
  const pool = p.talent_pool_entries?.[0];
  if (pool) return { id: pool.pool_id, value: pool.referred_by, save: (v) => talentPoolApi.update(pool.pool_id, { referred_by: v }) };
  const apps = p.applications ?? [];
  if (apps.length === 1 && apps[0].job_exists !== false) {
    const a = apps[0];
    return { id: a.candidate_id, value: a.referred_by, save: (v) => candidatesApi.update(a.job_id, a.candidate_id, { referred_by: v }) };
  }
  return null;
}

/* Add candidates (CV upload or manual entry) to the pool or straight into a job */
function AddCandidatesPanel({ jobs, onAdded }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(POOL);
  const [showManual, setShowManual] = useState(false);
  const job = jobs.find((j) => j.id === target);
  const toPool = target === POOL || !job;

  const upload = (files, onProgress, fields) =>
    toPool ? talentPoolApi.upload(files, onProgress, fields) : candidatesApi.upload(job.id, files, onProgress, fields);

  const createManual = async (payload) => {
    if (toPool) await talentPoolApi.create(payload);
    else await candidatesApi.create(job.id, payload);
    onAdded();
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-6 py-4 text-right hover:bg-gray-50/60"
      >
        <span className="flex items-center gap-2">
          <Plus className="h-4 w-4 text-indigo-600" />
          <span className="text-base font-bold text-gray-900">הוספת מועמדים</span>
          <span className="hidden sm:inline text-xs text-gray-400">העלאת קורות חיים או הזנה ידנית – למאגר או ישירות למשרה</span>
        </span>
        <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-gray-100 p-6 space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex-1 min-w-[240px] max-w-md">
              <span className="block text-sm font-medium text-gray-700 mb-1.5">לאן להוסיף?</span>
              <select value={target} onChange={(e) => setTarget(e.target.value)} className={`${SELECT} w-full`}>
                <option value={POOL}>מאגר המועמדים (ללא שיוך למשרה)</option>
                {jobs.length > 0 && (
                  <optgroup label="ישירות למשרה">
                    {jobs.map((j) => <option key={j.id} value={j.id}>{j.job_title}</option>)}
                  </optgroup>
                )}
              </select>
            </label>
            <button
              type="button"
              onClick={() => setShowManual(true)}
              className="flex items-center justify-center gap-2 border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg text-sm font-semibold"
            >
              <UserPlus className="h-4 w-4" />
              הוספה ידנית
            </button>
          </div>
          <p className="text-xs text-gray-400">
            PDF, Word (.docx), תמונה (PNG, JPG) — הקובץ המקורי נשמר ונגיש מכרטיס המועמד.
            {toPool
              ? ' מועמדים שכבר קיימים במאגר (לפי מייל או טלפון) ידולגו.'
              : ` מועמדים שכבר קיימים במשרה ״${job.job_title}״ ידולגו.`}
          </p>
          <UploadBox key={target} onUpload={upload} onUploadFinished={onAdded} />
        </div>
      )}

      {showManual && (
        <CandidateFormModal
          title={toPool ? 'הוספת מועמד למאגר' : 'הוספת מועמד למשרה'}
          subtitle={toPool ? undefined : job.job_title}
          withStatus={!toPool}
          onSubmit={createManual}
          onClose={() => setShowManual(false)}
        />
      )}
    </div>
  );
}

/*
 * The candidates module: everyone once — talent pool + every job's applicants,
 * merged by email / phone — with adding, referrer editing, CV access and
 * assignment to jobs (in the profile).
 */
export default function Candidates() {
  const [people, setPeople] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [view, setView] = useState('');
  const [referrer, setReferrer] = useState('');
  const [jobFilter, setJobFilter] = useState('');
  const [profession, setProfession] = useState('');
  const [minYears, setMinYears] = useState(0);
  const [selected, setSelected] = useState(null);
  const [openingCv, setOpeningCv] = useState('');

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true); else setLoading(true);
    setError('');
    try {
      const { data } = await searchApi.people();
      setPeople(data);
    } catch (err) {
      if (!silent) setError(apiErrorMessage(err, 'שגיאה בטעינת המועמדים'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    jobsApi.list().then(({ data }) => setJobs(data)).catch(() => setJobs([]));
  }, []);

  const replacePerson = useCallback((updated, previousKey) => {
    setPeople((prev) => prev.map((p) => (p.key === previousKey ? updated : p)));
    setSelected((s) => (s && s.key === previousKey ? updated : s));
  }, []);

  const removePerson = useCallback((key) => {
    setPeople((prev) => prev.filter((p) => p.key !== key));
  }, []);

  const saveRowReferrer = async (p, editable, value) => {
    await editable.save(value);
    const { data } = await searchApi.person(editable.id);
    replacePerson(data, p.key);
  };

  const openRowCv = async (p) => {
    const source = cvSources(p)[0];
    if (!source) return;
    setOpeningCv(p.key);
    try {
      await openCv(source);
    } catch (err) {
      alert(apiErrorMessage(err, 'פתיחת קובץ קורות החיים נכשלה'));
    } finally {
      setOpeningCv('');
    }
  };

  const referrers = useMemo(() => {
    const counts = new Map();
    people.forEach((p) => (p.referrers ?? []).forEach((r) => counts.set(r, (counts.get(r) || 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'he'));
  }, [people]);

  const professions = useMemo(
    () =>
      [...new Set(people.map((p) => (p.profession || '').trim()).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, 'he')
      ),
    [people]
  );

  const counts = useMemo(
    () => Object.fromEntries(VIEWS.map((v) => [v.value, people.filter(v.test).length])),
    [people]
  );

  const filtered = useMemo(() => {
    const viewTest = (VIEWS.find((v) => v.value === view) ?? VIEWS[0]).test;
    return people.filter(
      (p) =>
        viewTest(p) &&
        matchesQuery(p, query.trim()) &&
        (!referrer || (p.referrers ?? []).includes(referrer)) &&
        (!jobFilter || (p.applications ?? []).some((a) => a.job_id === jobFilter)) &&
        (!profession || (p.profession || '').trim() === profession) &&
        (p.years_of_experience || 0) >= minYears
    );
  }, [people, view, query, referrer, jobFilter, profession, minYears]);

  const stats = useMemo(() => ({
    inPool: people.filter((p) => p.in_talent_pool).length,
    applications: people.reduce((n, p) => n + (p.applications?.length ?? 0), 0),
  }), [people]);

  const filtersActive = query.trim() || view || referrer || jobFilter || profession || minYears;
  const clearFilters = () => {
    setQuery(''); setView(''); setReferrer(''); setJobFilter(''); setProfession(''); setMinYears(0);
  };

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
              <h1 className="text-2xl font-bold text-gray-900">מאגר המועמדים</h1>
              <p className="text-sm text-gray-400 mt-0.5">
                כל המועמדים במקום אחד – מהמאגר ומכל המשרות, כל אדם פעם אחת (מאוחד לפי מייל או טלפון)
              </p>
            </div>
          </div>
          {!loading && !error && (
            <p className="text-sm text-gray-500 tabular-nums">
              {people.length} מועמדים · {stats.inPool} במאגר · {stats.applications} מועמדויות
            </p>
          )}
        </div>

        <AddCandidatesPanel jobs={jobs} onAdded={() => load({ silent: true })} />

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {/* View tabs */}
          <div className="flex flex-wrap items-center gap-1 px-6 pt-4" role="tablist" aria-label="תצוגה">
            {VIEWS.map((v) => (
              <button
                key={v.value}
                type="button"
                role="tab"
                aria-selected={view === v.value}
                onClick={() => setView(v.value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  view === v.value ? 'bg-indigo-50 text-indigo-700' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
                }`}
              >
                {v.label}
                {!loading && <span className="mr-1.5 text-xs text-gray-400 tabular-nums">{counts[v.value]}</span>}
              </button>
            ))}
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 px-6 py-4 border-b border-gray-100">
            <div className="relative flex-1 min-w-[220px] max-w-sm">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="חיפוש לפי שם, מייל, טלפון, מקצוע, משרה, ממליץ…"
                className="w-full border border-gray-200 rounded-lg pr-9 pl-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <select value={referrer} onChange={(e) => setReferrer(e.target.value)} className={SELECT} aria-label={`סינון לפי ${REFERRER_LABEL}`}>
              <option value="">{REFERRER_LABEL}: כולם</option>
              {referrers.map(([name, count]) => <option key={name} value={name}>{name} ({count})</option>)}
            </select>
            <select value={jobFilter} onChange={(e) => setJobFilter(e.target.value)} className={SELECT} aria-label="סינון לפי משרה">
              <option value="">כל המשרות</option>
              {jobs.map((j) => <option key={j.id} value={j.id}>{j.job_title}</option>)}
            </select>
            <select value={profession} onChange={(e) => setProfession(e.target.value)} className={SELECT} aria-label="סינון לפי מקצוע">
              <option value="">כל המקצועות</option>
              {professions.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={minYears} onChange={(e) => setMinYears(Number(e.target.value))} className={SELECT} aria-label="סינון לפי ניסיון">
              {EXPERIENCE_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            {filtersActive && (
              <button onClick={clearFilters} className="text-xs text-indigo-600 hover:underline">
                ניקוי סינון
              </button>
            )}
            <span className="mr-auto flex items-center gap-2 text-xs text-gray-400 tabular-nums">
              {filtersActive && !loading && `מוצגים ${filtered.length} מתוך ${people.length}`}
              <button
                onClick={() => load({ silent: true })}
                disabled={refreshing || loading}
                className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                title="רענון"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </span>
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
              {!people.length && <p className="text-sm text-gray-400">העלו קורות חיים או הוסיפו מועמד ידנית</p>}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200 text-xs text-gray-500">
                    {['שם', 'טלפון', 'מייל', 'מקצוע', 'ניסיון', 'מועמדות אחרונה', 'מועמדויות', REFERRER_LABEL, 'קו״ח', 'פעילות אחרונה'].map((h) => (
                      <th key={h} className="px-4 py-3 text-right font-semibold whitespace-nowrap">{h}</th>
                    ))}
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((p) => {
                    const latest = p.applications?.[0];
                    const refs = p.referrers ?? [];
                    const editable = editableReferrer(p);
                    const hasCv = cvSources(p).length > 0;
                    const stop = (e) => e.stopPropagation();
                    return (
                      <tr
                        key={p.key}
                        onClick={() => setSelected(p)}
                        className="hover:bg-indigo-50/40 cursor-pointer"
                        title="פתיחת כרטיס המועמד: קורות חיים, מאגר והיסטוריית מועמדויות"
                      >
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="font-semibold text-gray-900">{fullName(p) || 'ללא שם'}</span>
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
                        <td className="px-4 py-3 text-center">
                          {p.years_of_experience > 0 ? (
                            <span className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs font-medium">{p.years_of_experience}</span>
                          ) : <Empty />}
                        </td>
                        <td className="px-4 py-3">
                          {latest ? (
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="truncate max-w-[160px] text-gray-800" title={latest.job_title}>{latest.job_title}</span>
                              <StatusBadge status={latest.recruitment_status} />
                            </div>
                          ) : (
                            <span className="text-xs text-teal-600">במאגר – לא שויך</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center tabular-nums">
                          {p.applications?.length ? (
                            <span className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs font-medium">{p.applications.length}</span>
                          ) : <Empty />}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap" onClick={editable ? stop : undefined}>
                          {editable ? (
                            <span className="inline-flex items-center gap-1">
                              <ReferrerCell value={editable.value} onSave={(v) => saveRowReferrer(p, editable, v)} />
                              {refs.filter((r) => r !== editable.value).length > 0 && (
                                <span className="text-xs text-violet-400" title={refs.join(', ')}>
                                  +{refs.filter((r) => r !== editable.value).length}
                                </span>
                              )}
                            </span>
                          ) : refs.length ? (
                            <span className="inline-flex items-center gap-1 text-xs text-violet-700" title={`${refs.join(', ')} – עריכה בכרטיס המועמד`}>
                              <UserPlus className="h-3 w-3 flex-shrink-0" />
                              <span className="truncate max-w-[130px]">{refs[0]}</span>
                              {refs.length > 1 && <span className="text-violet-400">+{refs.length - 1}</span>}
                            </span>
                          ) : <Empty />}
                        </td>
                        <td className="px-4 py-3" onClick={hasCv ? stop : undefined}>
                          {hasCv ? (
                            <button
                              type="button"
                              onClick={() => openRowCv(p)}
                              disabled={openingCv === p.key}
                              title="פתיחת קורות החיים"
                              className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 disabled:opacity-60"
                            >
                              {openingCv === p.key ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                              <span className="sr-only">פתיחת קורות החיים</span>
                            </button>
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

      {selected && (
        <CandidateProfileModal
          profile={selected}
          onClose={() => setSelected(null)}
          onChanged={replacePerson}
          onRemoved={removePerson}
        />
      )}
    </div>
  );
}
