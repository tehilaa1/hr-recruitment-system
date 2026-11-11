// Must stay identical, in the same order, to VALID_STATUSES in
// backend/app/models/candidate.py; enforced by backend/tests/test_status_sync.py.
// Every status also needs an entry in STATUS_STYLES below.
export const RECRUITMENT_STATUSES = [
  'לא טופל',
  'לא עונה',
  'נשלח זימון',
  'לשלוח זימון',
  'גויס/ה',
  'שלילי',
  'לא רלוונטי',
];

export const STATUS_STYLES = {
  'לא טופל': {
    badge: 'bg-slate-100 text-slate-600 border border-slate-200',
    dot: 'bg-slate-400',
    hover: 'hover:bg-slate-200',
  },
  'לא עונה': {
    badge: 'bg-amber-100 text-amber-700 border border-amber-200',
    dot: 'bg-amber-400',
    hover: 'hover:bg-amber-200',
  },
  'נשלח זימון': {
    badge: 'bg-sky-100 text-sky-700 border border-sky-200',
    dot: 'bg-sky-400',
    hover: 'hover:bg-sky-200',
  },
  'לשלוח זימון': {
    badge: 'bg-violet-100 text-violet-700 border border-violet-200',
    dot: 'bg-violet-400',
    hover: 'hover:bg-violet-200',
  },
  'גויס/ה': {
    badge: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
    dot: 'bg-emerald-500',
    hover: 'hover:bg-emerald-200',
  },
  'שלילי': {
    badge: 'bg-red-100 text-red-700 border border-red-200',
    dot: 'bg-red-400',
    hover: 'hover:bg-red-200',
  },
  'לא רלוונטי': {
    badge: 'bg-gray-100 text-gray-500 border border-gray-200',
    dot: 'bg-gray-400',
    hover: 'hover:bg-gray-200',
  },
};
