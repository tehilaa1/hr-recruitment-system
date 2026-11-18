import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FileText,
  Library,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  UserPlus,
  UserX,
} from 'lucide-react';
import { apiErrorMessage, talentPoolApi } from '../api/client';
import CandidateFormModal from '../components/CandidateFormModal';
import Navbar from '../components/Navbar';
import { ReferrerCell } from '../components/ReferrerInput';
import UploadBox from '../components/UploadBox';

const Empty = () => <span className="text-gray-300">—</span>;

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('he-IL', { year: 'numeric', month: 'short', day: 'numeric' });

const EXPERIENCE_FILTERS = [
  { value: 0, label: 'כל רמות הניסיון' },
  { value: 1, label: 'שנה ומעלה' },
  { value: 3, label: '3 שנים ומעלה' },
  { value: 5, label: '5 שנים ומעלה' },
  { value: 10, label: '10 שנים ומעלה' },
];

const digits = (v) => String(v || '').replace(/\D/g, '');

function matchesQuery(c, q) {
  if (!q) return true;
  const text = [c.full_name, c.family_name, c.email, c.profession, c.address, c.file_name, c.referred_by]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  if (text.includes(q.toLowerCase())) return true;
  const qDigits = digits(q);
  return qDigits.length >= 3 && digits(c.phone).includes(qDigits);
}

const SELECT =
  'border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent';

export default function TalentPool() {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [showManualAdd, setShowManualAdd] = useState(false);
  const [query, setQuery] = useState('');
  const [profession, setProfession] = useState('');
  const [minYears, setMinYears] = useState(0);

  const fetchPool = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true); else setLoading(true);
    setFetchError('');
    try {
      const { data } = await talentPoolApi.list();
      setCandidates(data);
    } catch (err) {
      if (!silent) setFetchError(apiErrorMessage(err, 'שגיאה בטעינת המאגר'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchPool(); }, [fetchPool]);

  const mergeCandidates = (incoming) => {
    if (!incoming.length) return;
    setCandidates((prev) => {
      const known = new Set(prev.map((c) => c.id));
      return [...incoming.filter((c) => !known.has(c.id)), ...prev];
    });
  };

  const handleManualAdd = async (payload) => {
    const { data } = await talentPoolApi.create(payload);
    mergeCandidates([data]);
  };

  const handleReferrerChange = async (candidateId, referredBy) => {
    const { data } = await talentPoolApi.update(candidateId, { referred_by: referredBy });
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, referred_by: data.referred_by } : c)));
  };

  const handleDelete = async (candidate) => {
    const name = [candidate.full_name, candidate.family_name].filter(Boolean).join(' ') || 'מועמד זה';
    if (!window.confirm(`למחוק את ${name} מהמאגר?`)) return;
    try {
      await talentPoolApi.remove(candidate.id);
      setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה במחיקת המועמד'));
    }
  };

  const professions = useMemo(
    () =>
      [...new Set(candidates.map((c) => (c.profession || '').trim()).filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, 'he')
      ),
    [candidates]
  );

  const filtered = useMemo(
    () =>
      candidates.filter(
        (c) =>
          matchesQuery(c, query.trim()) &&
          (!profession || (c.profession || '').trim() === profession) &&
          (c.years_of_experience || 0) >= minYears
      ),
    [candidates, query, profession, minYears]
  );

  const filtersActive = query.trim() || profession || minYears;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl p-3 bg-teal-100 text-teal-600">
              <Library className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">מאגר מועמדים</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                קורות חיים שאינם משויכים למשרה. בכל משרה אפשר לקבל הצעות מתאימות מהמאגר.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowManualAdd(true)}
            className="flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors"
          >
            <UserPlus className="h-4 w-4" />
            הוספת מועמד ידנית
          </button>
        </div>

        {/* Upload */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-base font-bold text-gray-900">העלאת קורות חיים למאגר</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              PDF, Word (.docx), תמונה (PNG, JPG) — מועמדים שכבר קיימים במאגר (לפי מייל או טלפון) ידולגו
            </p>
          </div>
          <div className="p-6">
            <UploadBox
              onUpload={(files, onProgress, fields) => talentPoolApi.upload(files, onProgress, fields)}
              onUploadComplete={mergeCandidates}
              onUploadFinished={() => fetchPool({ silent: true })}
            />
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 px-6 py-4 border-b border-gray-100">
            <div>
              <h2 className="text-base font-bold text-gray-900">מועמדים במאגר</h2>
              <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1.5">
                {filtersActive
                  ? `מוצגים ${filtered.length} מתוך ${candidates.length}`
                  : `${candidates.length} מועמדים`}
                {refreshing && <Loader2 className="h-3 w-3 animate-spin" />}
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="חיפוש לפי שם, מייל, טלפון, מקצוע, ממליץ…"
                  className="w-full sm:w-72 border border-gray-200 rounded-lg pr-9 pl-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
                />
              </div>
              <select value={profession} onChange={(e) => setProfession(e.target.value)} className={SELECT}>
                <option value="">כל המקצועות</option>
                {professions.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
              <select value={minYears} onChange={(e) => setMinYears(Number(e.target.value))} className={SELECT}>
                {EXPERIENCE_FILTERS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-7 w-7 text-teal-500 animate-spin" />
            </div>
          ) : fetchError ? (
            <div className="flex flex-col items-center gap-3 py-16 text-sm">
              <p className="text-gray-500">{fetchError}</p>
              <button
                type="button"
                onClick={() => fetchPool()}
                className="flex items-center gap-2 text-teal-600 hover:underline"
              >
                <RefreshCw className="h-4 w-4" /> נסה שנית
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
              <div className="bg-gray-100 rounded-full p-4">
                <UserX className="h-8 w-8 text-gray-300" />
              </div>
              <div>
                <p className="text-gray-500 font-medium">
                  {candidates.length ? 'אין מועמדים שתואמים לחיפוש' : 'המאגר ריק עדיין'}
                </p>
                {!candidates.length && (
                  <p className="text-sm text-gray-400 mt-1">העלו קורות חיים או הוסיפו מועמד ידנית</p>
                )}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200">
                    {['שם', 'טלפון', 'מייל', 'כתובת מגורים', 'מקצוע', 'שנות ניסיון', 'הובא על ידי', 'מקור', 'נוסף בתאריך'].map((h) => (
                      <th key={h} className="px-4 py-3 text-right text-xs font-semibold text-gray-500 whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                    <th className="px-4 py-3 w-10" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((c) => (
                    <tr key={c.id} className="hover:bg-teal-50/30 transition-colors group">
                      <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                        {[c.full_name, c.family_name].filter(Boolean).join(' ') || <Empty />}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {c.phone ? (
                          <a href={`tel:${c.phone}`} dir="ltr" className="text-gray-700 hover:text-teal-600 font-mono text-xs tracking-wider">
                            {c.phone}
                          </a>
                        ) : <Empty />}
                      </td>
                      <td className="px-4 py-3 max-w-[200px] truncate">
                        {c.email ? (
                          <a href={`mailto:${c.email}`} title={c.email} className="text-blue-600 hover:underline text-xs">
                            {c.email}
                          </a>
                        ) : <Empty />}
                      </td>
                      <td className="px-4 py-3 text-gray-600 max-w-[160px] truncate" title={c.address}>
                        {c.address || <Empty />}
                      </td>
                      <td className="px-4 py-3 text-gray-700 max-w-[160px] truncate" title={c.profession}>
                        {c.profession || <Empty />}
                      </td>
                      <td className="px-4 py-3 text-center whitespace-nowrap">
                        {c.years_of_experience > 0 ? (
                          <span className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs font-medium">
                            {c.years_of_experience}
                          </span>
                        ) : <Empty />}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <ReferrerCell value={c.referred_by} onSave={(v) => handleReferrerChange(c.id, v)} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 max-w-[160px] truncate" title={c.file_name}>
                        {c.file_name ? (
                          <span className="flex items-center gap-1">
                            <FileText className="h-3.5 w-3.5 flex-shrink-0" />
                            {c.file_name}
                          </span>
                        ) : (
                          'הוזן ידנית'
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                        {c.created_at ? formatDate(c.created_at) : <Empty />}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => handleDelete(c)}
                          className="text-gray-200 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded-lg hover:bg-red-50"
                          title="מחק מהמאגר"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {showManualAdd && (
        <CandidateFormModal
          title="הוספת מועמד למאגר"
          onSubmit={handleManualAdd}
          onClose={() => setShowManualAdd(false)}
        />
      )}
    </div>
  );
}
