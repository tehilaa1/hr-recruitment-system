import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  ChevronLeft,
  FileText,
  Library,
  Mail,
  MapPin,
  Phone,
  User,
  X,
} from 'lucide-react';
import StatusBadge from './StatusBadge';

const formatDate = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString('he-IL', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    : '—';

function ContactRow({ icon: Icon, children }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-700 min-w-0">
      <Icon className="h-4 w-4 text-gray-400 flex-shrink-0" />
      <div className="min-w-0 flex flex-wrap gap-x-3 gap-y-1">{children}</div>
    </div>
  );
}

/* Candidate profile: contact details + every position they applied to */
export default function CandidateProfileModal({ profile, onClose }) {
  const navigate = useNavigate();

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

  const goToPool = () => {
    onClose();
    navigate('/talent-pool');
  };

  const goToJob = (jobId) => {
    onClose();
    navigate(`/jobs/${jobId}`);
  };

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
              <div className="flex items-center gap-2 min-w-0">
                <h2 className="text-lg font-bold text-gray-900 truncate">{name}</h2>
                {profile.in_talent_pool && (
                  <span className="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-200">
                    <Library className="h-3 w-3" />
                    במאגר המועמדים
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                {[
                  profile.profession,
                  profile.years_of_experience > 0 && `${profile.years_of_experience} שנות ניסיון`,
                ]
                  .filter(Boolean)
                  .join(' · ') || 'פרופיל מועמד'}
              </p>
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

        {/* Talent pool */}
        {pool.length > 0 && (
          <div className="px-6 py-4 border-b border-gray-100">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
              <Library className="h-4 w-4 text-teal-500" />
              מאגר המועמדים
            </h3>
            <button
              type="button"
              onClick={goToPool}
              title="מעבר למאגר המועמדים"
              className="w-full flex flex-col gap-1.5 rounded-xl border border-teal-100 bg-teal-50/50 hover:bg-teal-50 px-4 py-3 text-right transition-colors"
            >
              {pool.map((e) => (
                <span key={e.pool_id} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-1.5 text-gray-700 min-w-0">
                    <FileText className="h-3.5 w-3.5 text-teal-500 flex-shrink-0" />
                    <span className="truncate">{e.file_name || 'הוזן ידנית'}</span>
                  </span>
                  <span className="flex items-center gap-1 text-xs text-gray-500 whitespace-nowrap">
                    נוסף {formatDate(e.created_at)}
                    <ChevronLeft className="h-4 w-4 text-gray-300" />
                  </span>
                </span>
              ))}
            </button>
          </div>
        )}

        {/* Applications */}
        <div className="px-6 py-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800 mb-3">
            <Briefcase className="h-4 w-4 text-gray-400" />
            משרות שהמועמד הגיש אליהן ({apps.length})
          </h3>
          {apps.length === 0 ? (
            <p className="text-sm text-gray-500 bg-gray-50 rounded-xl px-4 py-3">
              המועמד עדיין לא שויך לאף משרה. ניתן לשייך אותו מתוך עמוד המשרה, בלחיצה על
              {' '}״הצעות מועמדים מהמאגר״.
            </p>
          ) : (
          <div className="border border-gray-100 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-500">
                  <th className="px-4 py-2.5 text-right font-semibold">משרה</th>
                  <th className="px-4 py-2.5 text-right font-semibold">סוג ראיון</th>
                  <th className="px-4 py-2.5 text-right font-semibold">סטטוס</th>
                  <th className="px-4 py-2.5 text-right font-semibold">נוסף בתאריך</th>
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
                      <td className="px-4 py-3 font-medium text-gray-900">{a.job_title}</td>
                      <td className="px-4 py-3 text-gray-600">{a.interview_type || '—'}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={a.recruitment_status} />
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
