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

// Expense payment status. Must stay identical, in the same order, to
// EXPENSE_STATUSES in backend/app/models/budget.py (backend/tests/test_budgets.py).
export const EXPENSE_STATUSES = [
  'שולם',
  'ישולם בהעברה',
];
export const DEFAULT_EXPENSE_STATUS = 'ישולם בהעברה';

export const EXPENSE_STATUS_STYLES = {
  'שולם': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'ישולם בהעברה': 'bg-orange-50 text-orange-700 border-orange-200',
};

// Invoice files of expenses. INVOICE_MAX_BYTES must match backend/app/models/budget.py
// (backend/tests/test_budgets.py); the server re-checks size and real file type.
export const INVOICE_MAX_BYTES = 5 * 1024 * 1024;
export const INVOICE_ACCEPT = '.pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg';
const INVOICE_EXTENSIONS = /\.(pdf|png|jpe?g)$/i;

/* null if the file can be uploaded, else a Hebrew error message */
export function invoiceFileError(file) {
  if (!file) return 'לא נבחר קובץ';
  if (!INVOICE_EXTENSIONS.test(file.name)) return 'ניתן לצרף קובץ PDF, PNG או JPG בלבד';
  if (file.size === 0) return 'הקובץ ריק';
  if (file.size > INVOICE_MAX_BYTES) return `הקובץ גדול מדי (${formatFileSize(file.size)}; עד 5MB)`;
  return null;
}

export const formatFileSize = (bytes) =>
  bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)}MB` : `${Math.max(1, Math.round(bytes / 1024))}KB`;

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
