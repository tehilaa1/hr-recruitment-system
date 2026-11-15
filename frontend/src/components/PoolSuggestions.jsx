import { useState } from 'react';
import { Briefcase, Check, Loader2, MapPin, RefreshCw, Sparkles, UserPlus } from 'lucide-react';
import { apiErrorMessage, candidatesApi, jobsApi } from '../api/client';

const scoreStyle = (score) =>
  score >= 80
    ? 'bg-emerald-100 text-emerald-700'
    : score >= 65
      ? 'bg-sky-100 text-sky-700'
      : 'bg-amber-100 text-amber-700';

function SuggestionCard({ match, assigned, assigning, error, onAssign }) {
  const c = match.candidate;
  const name = [c.full_name, c.family_name].filter(Boolean).join(' ') || 'ללא שם';
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 flex flex-col gap-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-gray-900 truncate">{name}</p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-xs text-gray-500">
            {c.profession && (
              <span className="flex items-center gap-1">
                <Briefcase className="h-3 w-3" />
                {c.profession}
                {c.years_of_experience > 0 && ` · ${c.years_of_experience} שנות ניסיון`}
              </span>
            )}
            {c.address && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" />
                {c.address}
              </span>
            )}
          </div>
        </div>
        <span
          className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${scoreStyle(match.score)}`}
          title="ציון התאמה"
        >
          {match.score}%
        </span>
      </div>

      <p className="text-sm text-gray-700 leading-relaxed bg-violet-50/60 border border-violet-100 rounded-lg px-3 py-2">
        <Sparkles className="inline h-3.5 w-3.5 text-violet-500 ml-1 -mt-0.5" />
        {match.match_reason}
      </p>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <button
        type="button"
        onClick={onAssign}
        disabled={assigned || assigning}
        className={`self-start flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
          assigned
            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 cursor-default'
            : 'bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-60 disabled:cursor-wait'
        }`}
      >
        {assigned ? (
          <><Check className="h-4 w-4" /> שויך למשרה</>
        ) : assigning ? (
          <><Loader2 className="h-4 w-4 animate-spin" /> משייך…</>
        ) : (
          <><UserPlus className="h-4 w-4" /> שייך למשרה</>
        )}
      </button>
    </div>
  );
}

/*
 * "הצעות מועמדים מהמאגר" — asks the backend (Gemini) for the best talent-pool
 * fits for this job and lets the recruiter copy one into the job in one click.
 * onAssigned(candidate) receives the new job-candidate record.
 */
export default function PoolSuggestions({ jobId, onAssigned }) {
  const [matches, setMatches] = useState(null); // null = not requested yet
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [assigned, setAssigned] = useState(() => new Set());
  const [assigning, setAssigning] = useState(() => new Set());
  const [assignErrors, setAssignErrors] = useState({});

  const fetchMatches = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await jobsApi.matchPool(jobId);
      setMatches(data);
      setAssigned(new Set());
      setAssignErrors({});
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בחיפוש מועמדים מתאימים. נסה שנית.'));
    } finally {
      setLoading(false);
    }
  };

  const update = (setter, id, add) =>
    setter((prev) => {
      const next = new Set(prev);
      if (add) next.add(id); else next.delete(id);
      return next;
    });

  const handleAssign = async (poolId) => {
    update(setAssigning, poolId, true);
    setAssignErrors((p) => ({ ...p, [poolId]: '' }));
    try {
      const { data } = await candidatesApi.assignFromPool(jobId, poolId);
      update(setAssigned, poolId, true);
      onAssigned(data);
    } catch (err) {
      setAssignErrors((p) => ({ ...p, [poolId]: apiErrorMessage(err, 'השיוך נכשל. נסה שנית.') }));
    } finally {
      update(setAssigning, poolId, false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      {matches === null && !loading && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <p className="text-sm text-gray-500">
            ה-AI יסרוק את מאגר המועמדים וימליץ על המתאימים ביותר למשרה, עם הסבר קצר לכל המלצה.
            מועמדים שכבר הגישו מועמדות למשרה זו לא יוצגו.
          </p>
          <button
            type="button"
            onClick={fetchMatches}
            className="flex-shrink-0 flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-semibold transition-colors"
          >
            <Sparkles className="h-4 w-4" />
            הצעות מועמדים מהמאגר
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-violet-700" role="status">
          <Loader2 className="h-5 w-5 animate-spin" />
          ה-AI בוחן את מאגר המועמדים מול דרישות המשרה…
        </div>
      )}

      {error && !loading && (
        <div className="flex items-center justify-between gap-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <span>{error}</span>
          <button type="button" onClick={fetchMatches} className="flex items-center gap-1 font-medium hover:underline">
            <RefreshCw className="h-3.5 w-3.5" /> נסה שנית
          </button>
        </div>
      )}

      {matches !== null && !loading && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {matches.length
                ? `נמצאו ${matches.length} מועמדים מתאימים מהמאגר`
                : 'לא נמצאו במאגר מועמדים מתאימים למשרה זו.'}
            </p>
            <button
              type="button"
              onClick={fetchMatches}
              className="flex items-center gap-1 text-sm text-violet-600 hover:underline font-medium"
            >
              <RefreshCw className="h-3.5 w-3.5" /> חיפוש מחדש
            </button>
          </div>
          {matches.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {matches.map((m) => (
                <SuggestionCard
                  key={m.candidate.id}
                  match={m}
                  assigned={assigned.has(m.candidate.id)}
                  assigning={assigning.has(m.candidate.id)}
                  error={assignErrors[m.candidate.id]}
                  onAssign={() => handleAssign(m.candidate.id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
