// Must stay identical, in the same order, to EVENT_STATUSES in
// backend/app/models/budget.py; enforced by backend/tests/test_budgets.py.
// Every status also needs an entry in EVENT_STATUS_STYLES below.
export const EVENT_STATUSES = [
  'מתוכנן',
  'בביצוע',
  'הסתיים',
  'בוטל',
];

export const EVENT_STATUS_STYLES = {
  'מתוכנן': 'bg-sky-50 text-sky-700 border-sky-200',
  'בביצוע': 'bg-amber-50 text-amber-700 border-amber-200',
  'הסתיים': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'בוטל': 'bg-gray-100 text-gray-500 border-gray-200',
};

/* Quick-pick names in the "new event" form */
export const COMMON_EVENTS = [
  'ראש השנה',
  'סוכות',
  'חנוכה',
  'ט״ו בשבט',
  'פורים',
  'פסח',
  'יום העצמאות',
  'שבועות',
  'אירוע קיץ',
  'אירוע סוף שנה',
  'יום הולדת לחברה',
];

const ILS = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 0 });
const ILS_EXACT = new Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS', maximumFractionDigits: 2 });

/* ₪ formatting: whole shekels unless there are agorot */
export const formatIls = (value) => {
  const n = Number(value) || 0;
  return (Number.isInteger(n) ? ILS : ILS_EXACT).format(n);
};
