import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  ChevronLeft,
  Download,
  ExternalLink,
  FileText,
  FileX,
  Library,
  Loader2,
  Mail,
  MapPin,
  Paperclip,
  Phone,
  Trash2,
  User,
  UserPlus,
  X,
} from 'lucide-react';
import { apiErrorMessage, candidatesApi, jobsApi, searchApi, talentPoolApi } from '../api/client';
import { REFERRER_LABEL } from '../constants/referrals';
import {
  CV_ACCEPT,
  attachCv,
  cvSources,
  downloadCv,
  formatBytes,
  missingCvNames,
  openCv,
  primaryRecord,
} from '../utils/candidateCv';
import { ReferrerCell } from './ReferrerInput';
import StatusBadge from './StatusBadge';

const formatDate = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString('he-IL', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : '—';

function Referrer({ name }) {
  return name ? (
    <span className="inline-flex items-center gap-1 max-w-[160px] rounded-full bg-violet-50 border border-violet-100 px-2 py-0.5 text-xs text-violet-700" title={`${REFERRER_LABEL} ${name}`}>
      <UserPlus className="h-3 w-3 flex-shrink-0" />
      <span className="truncate">{name}</span>
    </span>
  ) : (
    <span className="text-gray-300">—</span>
  );
}

function ContactRow({ icon: Icon, children }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-700 min-w-0">
      <Icon className="h-4 w-4 text-gray-400 flex-shrink-0" />
      <div className="min-w-0 flex flex-wrap gap-x-3 gap-y-1">{children}</div>
    </div>
  );
}

function SectionTitle({ icon: Icon, className, children }) {
  return (
    <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
      <Icon className={`h-4 w-4 ${className}`} />
      {children}
    </h3>
  );
}

const recordIds = (p) => [
  ...(p?.talent_pool_entries ?? []).map((e) => e.pool_id),
  ...(p?.applications ?? []).map((a) => a.candidate_id),
];

/* "קורות חיים": open / download every stored file, or a clear fallback + attach */
function CvSection({ profile, onAttached }) {
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const fileRef = useRef(null);
  const sources = useMemo(() => cvSources(profile), [profile]);
  const missing = useMemo(() => missingCvNames(profile), [profile]);
  const target = primaryRecord(profile);

  const run = async (key, fn) => {
    setBusy(key);
    setError('');
    try {
      await fn();
    } catch (err) {
      setError(apiErrorMessage(err, 'פתיחת קובץ קורות החיים נכשלה'));
    } finally {
      setBusy('');
    }
  };

  const handleAttach = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !target) return;
    run('attach', async () => {
      await attachCv(target, file);
      await onAttached(target.id);
    });
  };

  return (
    <div className="px-6 py-4 border-b border-gray-100">
      <SectionTitle icon={FileText} className="text-blue-500">קורות חיים</SectionTitle>

      {sources.length > 0 ? (
        <ul className="space-y-2">
          {sources.map((s, i) => (
            <li
              key={`${s.kind}:${s.id}`}
              className={`flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 ${
                i === 0 ? 'border-blue-200 bg-blue-50/60' : 'border-gray-100 bg-gray-50/60'
              }`}
            >
              <FileText className="h-5 w-5 text-blue-500 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900 truncate" title={s.cv.file_name}>{s.cv.file_name}</p>
                <p className="text-xs text-gray-500">
                  {[s.label, formatDate(s.created_at), formatBytes(s.cv.size)].filter(Boolean).join(' · ')}
                </p>
              </div>
              <button
                type="button"
                onClick={() => run(`open:${s.id}`, () => openCv(s))}
                disabled={!!busy}
                className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-lg px-3 py-1.5 text-xs font-semibold"
              >
                {busy === `open:${s.id}` ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
                פתיחה
              </button>
              <button
                type="button"
                onClick={() => run(`dl:${s.id}`, () => downloadCv(s))}
                disabled={!!busy}
                title="הורדת הקובץ"
                className="p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-white disabled:opacity-60"
              >
                {busy === `dl:${s.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-gray-200 bg-gray-50/60 px-4 py-3">
          <FileX className="h-5 w-5 text-gray-400 flex-shrink-0" />
          <p className="flex-1 min-w-[200px] text-sm text-gray-600">
            {missing.length
              ? `הקובץ ${missing.map((n) => `״${n}״`).join(', ')} נקלט לפני ששמירת קבצי קורות חיים הופעלה, ולכן אינו זמין לצפייה. ניתן לצרף אותו מחדש.`
              : 'לא צורף קובץ קורות חיים למועמד זה (הוזן ידנית).'}
          </p>
          {target && (
            <>
              <input ref={fileRef} type="file" accept={CV_ACCEPT} className="hidden" onChange={handleAttach} />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={!!busy}
                className="flex items-center gap-1.5 border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-60 rounded-lg px-3 py-1.5 text-xs font-semibold text-gray-700"
              >
                {busy === 'attach' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Paperclip className="h-3.5 w-3.5" />}
                צירוף קובץ קורות חיים
              </button>
            </>
          )}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

/* Copy a pool entry into a job the person hasn't applied to yet */
function AssignToJob({ profile, poolId, onAssigned }) {
  const [jobs, setJobs] = useState(null);
  const [jobId, setJobId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    jobsApi
      .list()
      .then(({ data }) => alive && setJobs(data))
      .catch((err) => alive && setError(apiErrorMessage(err, 'שגיאה בטעינת המשרות')));
    return () => { alive = false; };
  }, []);

  const appliedTo = new Set((profile.applications ?? []).map((a) => a.job_id));
  const available = (jobs ?? []).filter((j) => !appliedTo.has(j.id));

  const assign = async () => {
    if (!jobId) return;
    setSaving(true);
    setError('');
    try {
      const { data } = await candidatesApi.assignFromPool(jobId, poolId);
      setJobId('');
      await onAssigned(data.id);
    } catch (err) {
      setError(apiErrorMessage(err, 'השיוך למשרה נכשל'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500">שיוך למשרה:</span>
        <select
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          disabled={!jobs || saving || !available.length}
          className="flex-1 min-w-[180px] border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-teal-500"
          aria-label="בחירת משרה לשיוך"
        >
          <option value="">
            {!jobs ? 'טוען משרות…' : available.length ? 'בחרו משרה…' : 'המועמד כבר שויך לכל המשרות'}
          </option>
          {available.map((j) => <option key={j.id} value={j.id}>{j.job_title}</option>)}
        </select>
        <button
          type="button"
          onClick={assign}
          disabled={!jobId || saving}
          className="flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white rounded-lg px-3 py-1.5 text-xs font-semibold"
        >
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Briefcase className="h-3.5 w-3.5" />}
          שיוך
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
    </div>
  );
}

/*
 * Candidate profile: contact details, CV, talent-pool entry and application history
 * (job, date, current status and referrer of every application, newest first).
 *
 * The modal performs its own edits (referrers, CV, pool assignment / removal) and
 * re-fetches the profile afterwards. Parents may listen:
 *   onChanged(updatedProfile, previousKey) — a record of this person changed
 *   onRemoved(previousKey)                 — the person no longer has any record
 */
export default function CandidateProfileModal({ profile: initial, onClose, onChanged, onRemoved }) {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(initial);

  useEffect(() => { setProfile(initial); }, [initial]);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!profile) return null;

  const name =
    [profile.full_name, profile.family_name].filter(Boolean).join(' ') || 'ללא שם';
  const apps = profile.applications ?? [];
  const pool = profile.talent_pool_entries ?? [];

  /* Re-fetch this person via a record that still exists */
  const refresh = async (recordId) => {
    const { data } = await searchApi.person(recordId);
    const previousKey = profile.key;
    setProfile(data);
    onChanged?.(data, previousKey);
  };

  const saveAppReferrer = async (a, value) => {
    await candidatesApi.update(a.job_id, a.candidate_id, { referred_by: value });
    await refresh(a.candidate_id);
  };

  const savePoolReferrer = async (e, value) => {
    await talentPoolApi.update(e.pool_id, { referred_by: value });
    await refresh(e.pool_id);
  };

  const removeFromPool = async (entry) => {
    if (!window.confirm(`להסיר את ${name} ממאגר המועמדים? המועמדויות למשרות לא יימחקו.`)) return;
    try {
      await talentPoolApi.remove(entry.pool_id);
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה בהסרה מהמאגר'));
      return;
    }
    const remaining = recordIds(profile).filter((id) => id !== entry.pool_id);
    if (!remaining.length) {
      onRemoved?.(profile.key);
      onClose();
      return;
    }
    try {
      await refresh(remaining[0]);
    } catch {
      onClose();
    }
  };

  const goToJob = (jobId) => {
    onClose();
    navigate(`/jobs/${jobId}`);
  };

  const cvCount = cvSources(profile).length;
  const stop = (e) => e.stopPropagation();

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-start justify-center p-4 pt-20 overflow-y-auto"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`פרופיל מועמד: ${name}`}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden animate-fade-in"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-3 min-w-0">
            <div className="bg-blue-100 text-blue-600 rounded-full p-2.5 flex-shrink-0">
              <User className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 min-w-0">
                <h2 className="text-lg font-bold text-gray-900 truncate">{name}</h2>
                {profile.in_talent_pool && (
                  <span className="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-200">
                    <Library className="h-3 w-3" />
                    במאגר המועמדים
                  </span>
                )}
                <span
                  className={`flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
                    cvCount ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-gray-50 text-gray-500 border-gray-200'
                  }`}
                >
                  {cvCount ? <FileText className="h-3 w-3" /> : <FileX className="h-3 w-3" />}
                  {cvCount ? 'קו״ח מצורפים' : 'ללא קו״ח'}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                {[
                  profile.profession,
                  profile.years_of_experience > 0 && `${profile.years_of_experience} שנות ניסיון`,
                ]
                  .filter(Boolean)
                  .join(' · ') || 'פרופיל מועמד'}
              </p>
              {profile.referrers?.length > 0 && (
                <p className="flex flex-wrap items-center gap-1.5 mt-1.5 text-xs text-gray-500">
                  הובא/ה על ידי:
                  {profile.referrers.map((r) => <Referrer key={r} name={r} />)}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 p-1 rounded-lg hover:bg-gray-100"
            title="סגור"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Contact details */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 px-6 py-4 bg-gray-50/60 border-b border-gray-100">
          <ContactRow icon={Mail}>
            {profile.emails?.length ? (
              profile.emails.map((e) => (
                <a key={e} href={`mailto:${e}`} className="text-blue-600 hover:underline truncate">
                  {e}
                </a>
              ))
            ) : (
              <span className="text-gray-300">—</span>
            )}
          </ContactRow>
          <ContactRow icon={Phone}>
            {profile.phones?.length ? (
              profile.phones.map((p) => (
                <a key={p} href={`tel:${p}`} className="font-mono text-xs tracking-wider hover:text-blue-600">
                  {p}
                </a>
              ))
            ) : (
              <span className="text-gray-300">—</span>
            )}
          </ContactRow>
          {profile.address && (
            <ContactRow icon={MapPin}>
              <span className="truncate">{profile.address}</span>
            </ContactRow>
          )}
        </div>

        <CvSection profile={profile} onAttached={refresh} />

        {/* Talent pool */}
        {pool.length > 0 && (
          <div className="px-6 py-4 border-b border-gray-100">
            <SectionTitle icon={Library} className="text-teal-500">מאגר המועמדים</SectionTitle>
            <ul className="space-y-2">
              {pool.map((e) => (
                <li
                  key={e.pool_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-teal-100 bg-teal-50/50 px-4 py-3 text-sm"
                >
                  <span className="flex items-center gap-1.5 text-gray-700 min-w-0">
                    <Library className="h-3.5 w-3.5 text-teal-500 flex-shrink-0" />
                    <span className="truncate">נוסף למאגר {formatDate(e.created_at)}</span>
                    {!e.file_name && <span className="text-xs text-gray-400">· הוזן ידנית</span>}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-gray-500">
                    {REFERRER_LABEL}:
                    <ReferrerCell value={e.referred_by} onSave={(v) => savePoolReferrer(e, v)} />
                    <button
                      type="button"
                      onClick={() => removeFromPool(e)}
                      title="הסרה מהמאגר"
                      className="p-1 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <AssignToJob profile={profile} poolId={pool[0].pool_id} onAssigned={refresh} />
          </div>
        )}

        {/* Applications */}
        <div className="px-6 py-4">
          <SectionTitle icon={Briefcase} className="text-gray-400">
            היסטוריית מועמדויות ({apps.length})
          </SectionTitle>
          {apps.length === 0 ? (
            <p className="text-sm text-gray-500 bg-gray-50 rounded-xl px-4 py-3">
              המועמד עדיין לא שויך לאף משרה.
              {pool.length > 0 && ' ניתן לשייך אותו למשרה מתוך ״מאגר המועמדים״ למעלה.'}
            </p>
          ) : (
          <div className="border border-gray-100 rounded-xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-500">
                  <th className="px-4 py-2.5 text-right font-semibold">משרה</th>
                  <th className="px-4 py-2.5 text-right font-semibold">סוג ראיון</th>
                  <th className="px-4 py-2.5 text-right font-semibold">סטטוס במשרה</th>
                  <th className="px-4 py-2.5 text-right font-semibold">{REFERRER_LABEL}</th>
                  <th className="px-4 py-2.5 text-right font-semibold">תאריך הגשה</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {apps.map((a) => {
                  const jobExists = a.job_exists !== false;
                  return (
                    <tr
                      key={a.candidate_id}
                      onClick={() => jobExists && goToJob(a.job_id)}
                      className={jobExists ? 'hover:bg-blue-50/40 cursor-pointer' : 'opacity-60'}
                      title={jobExists ? 'מעבר לעמוד המשרה' : undefined}
                    >
                      <td className="px-4 py-3 font-medium text-gray-900">
                        <span className="flex items-center gap-1.5">
                          {a.job_title}
                          {a.cv_file && <FileText className="h-3.5 w-3.5 text-blue-400 flex-shrink-0" aria-label="קו״ח מצורפים" />}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{a.interview_type || '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <StatusBadge status={a.recruitment_status} />
                          {a.is_completed && <span className="text-[11px] text-gray-400 whitespace-nowrap">· טיפול הסתיים</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3" onClick={stop}>
                        {jobExists ? (
                          <ReferrerCell value={a.referred_by} onSave={(v) => saveAppReferrer(a, v)} />
                        ) : (
                          <Referrer name={a.referred_by} />
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        {formatDate(a.created_at)}
                      </td>
                      <td className="px-2 py-3 text-gray-300">
                        {jobExists && <ChevronLeft className="h-4 w-4" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          )}
        </div>
      </div>
    </div>
  );
}
