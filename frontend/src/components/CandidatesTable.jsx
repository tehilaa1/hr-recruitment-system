import { useMemo, useState } from 'react';
import { CalendarPlus, Mail, Trash2, UserX } from 'lucide-react';
import CompleteToggle from './CompleteToggle';
import StatusSelect from './StatusSelect';
import {
  buildInterviewInviteUrl,
  buildRejectionEmailUrl,
  openInNewTab,
} from '../utils/outlook';

/* Outlook action shown next to the status badge for specific statuses */
function OutlookAction({ candidate, job }) {
  const status = candidate.recruitment_status;

  if (status === 'שלילי') {
    const noEmail = !candidate.email;
    return (
      <button
        type="button"
        disabled={noEmail}
        onClick={() => openInNewTab(buildRejectionEmailUrl(candidate, job))}
        title={noEmail ? 'למועמד אין כתובת מייל' : 'פתח מייל דחייה ב-Outlook'}
        className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <Mail className="h-3.5 w-3.5" />
        מייל דחייה
      </button>
    );
  }

  if (status === 'לשלוח זימון') {
    return (
      <button
        type="button"
        onClick={() => openInNewTab(buildInterviewInviteUrl(candidate, job))}
        title="פתח זימון לראיון ביומן Outlook"
        className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium border border-violet-200 text-violet-600 hover:bg-violet-50 transition-colors"
      >
        <CalendarPlus className="h-3.5 w-3.5" />
        זימון ב-Outlook
      </button>
    );
  }

  return null;
}

const COLUMNS = [
  { key: 'full_name',            label: 'שם פרטי',       width: 'min-w-[110px]' },
  { key: 'family_name',          label: 'שם משפחה',      width: 'min-w-[110px]' },
  { key: 'phone',                label: 'טלפון',         width: 'min-w-[120px]' },
  { key: 'email',                label: 'מייל',          width: 'min-w-[180px]' },
  { key: 'address',              label: 'כתובת מגורים',  width: 'min-w-[150px]' },
  { key: 'profession',           label: 'מקצוע',         width: 'min-w-[120px]' },
  { key: 'years_of_experience',  label: 'שנות ניסיון',   width: 'min-w-[90px]'  },
  { key: 'recruitment_status',   label: 'סטטוס גיוס',    width: 'min-w-[160px]' },
  { key: 'is_completed',         label: 'סיום טיפול',    width: 'min-w-[120px]' },
];

/* Active candidates first; completed ones sink to the bottom (order otherwise kept) */
const activeFirst = (list) =>
  list
    .map((c, i) => [c, i])
    .sort(([a, ai], [b, bi]) => Number(!!a.is_completed) - Number(!!b.is_completed) || ai - bi)
    .map(([c]) => c);

export default function CandidatesTable({ candidates, job, onStatusChange, onToggleComplete, onDelete }) {
  const [updatingId, setUpdatingId] = useState(null);
  const [completingIds, setCompletingIds] = useState(() => new Set());
  const sorted = useMemo(() => activeFirst(candidates), [candidates]);
  const completedCount = useMemo(() => candidates.filter((c) => c.is_completed).length, [candidates]);

  const handleStatusChange = async (candidateId, status) => {
    setUpdatingId(candidateId);
    await onStatusChange(candidateId, status);
    setUpdatingId(null);
  };

  const handleToggleComplete = async (candidate) => {
    setCompletingIds((prev) => new Set(prev).add(candidate.id));
    try {
      await onToggleComplete(candidate.id, !candidate.is_completed);
    } finally {
      setCompletingIds((prev) => {
        const next = new Set(prev);
        next.delete(candidate.id);
        return next;
      });
    }
  };

  if (candidates.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
        <div className="bg-gray-100 rounded-full p-4">
          <UserX className="h-8 w-8 text-gray-300" />
        </div>
        <div>
          <p className="text-gray-500 font-medium">אין מועמדים עדיין</p>
          <p className="text-sm text-gray-400 mt-1">העלו קורות חיים או הוסיפו מועמד ידנית כדי להתחיל</p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        {/* Head */}
        <thead>
          <tr className="bg-gray-50/80 border-b border-gray-200">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={`px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap ${col.width}`}
              >
                {col.label}
              </th>
            ))}
            <th className="px-4 py-3 w-10" />
          </tr>
        </thead>

        {/* Body */}
        <tbody className="divide-y divide-gray-100">
          {sorted.map((c, idx) => (
            <tr
              key={c.id}
              className={`transition-colors group ${
                c.is_completed
                  ? 'bg-gray-50/80 text-gray-400 [&>td:not(.keep-color)]:opacity-60 hover:bg-gray-100/70'
                  : 'hover:bg-blue-50/30'
              } ${
                // Visual divider between active and completed candidates
                c.is_completed && idx === sorted.length - completedCount && idx > 0
                  ? 'border-t-2 border-t-gray-200'
                  : ''
              }`}
            >
              {/* שם פרטי */}
              <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                {c.full_name || <span className="text-gray-300">—</span>}
              </td>

              {/* שם משפחה */}
              <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                {c.family_name || <span className="text-gray-300">—</span>}
              </td>

              {/* טלפון */}
              <td className="px-4 py-3 whitespace-nowrap">
                {c.phone ? (
                  <a
                    href={`tel:${c.phone}`}
                    className="text-gray-700 hover:text-blue-600 font-mono text-xs tracking-wider"
                  >
                    {c.phone}
                  </a>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>

              {/* מייל */}
              <td className="px-4 py-3 max-w-[200px] truncate">
                {c.email ? (
                  <a
                    href={`mailto:${c.email}`}
                    title={c.email}
                    className="text-blue-600 hover:underline text-xs"
                  >
                    {c.email}
                  </a>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>

              {/* כתובת */}
              <td
                className="px-4 py-3 text-gray-600 max-w-[160px] truncate"
                title={c.address}
              >
                {c.address || <span className="text-gray-300">—</span>}
              </td>

              {/* מקצוע */}
              <td
                className="px-4 py-3 text-gray-700 max-w-[140px] truncate"
                title={c.profession}
              >
                {c.profession || <span className="text-gray-300">—</span>}
              </td>

              {/* שנות ניסיון */}
              <td className="px-4 py-3 text-center whitespace-nowrap">
                {c.years_of_experience > 0 ? (
                  <span className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs font-medium">
                    {c.years_of_experience}
                  </span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>

              {/* סטטוס גיוס */}
              <td className="px-4 py-3 whitespace-nowrap">
                <div className="flex items-center gap-2">
                  <StatusSelect
                    value={c.recruitment_status}
                    onChange={(status) => handleStatusChange(c.id, status)}
                    disabled={updatingId === c.id}
                  />
                  <OutlookAction candidate={c} job={job} />
                </div>
              </td>

              {/* סיום טיפול */}
              <td className="keep-color px-4 py-3 whitespace-nowrap">
                <CompleteToggle
                  completed={!!c.is_completed}
                  title="סמן שהטיפול במועמד הסתיים"
                  disabled={completingIds.has(c.id)}
                  onToggle={() => handleToggleComplete(c)}
                />
              </td>

              {/* Delete */}
              <td className="px-4 py-3">
                <button
                  onClick={() => onDelete(c.id)}
                  className="text-gray-200 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-red-50"
                  title="מחק מועמד"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
