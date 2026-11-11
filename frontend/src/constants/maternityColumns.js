/*
 * Maternity-leave table and form are generated from this list.
 *
 * To add a column:
 *   1. add an entry here
 *   2. add the matching field in backend/app/models/maternity.py
 *      (MaternityLeaveBase + MaternityLeaveUpdate)
 *
 * Field types: text | tel | email | date | boolean | textarea
 * A "group" entry shows several fields in one table column / one form row.
 * Options: required, placeholder, wide (full-width in the form),
 *          tableWidth (Tailwind min-width class).
 */
export const MATERNITY_COLUMNS = [
  { key: 'name', label: 'שם', type: 'text', required: true, placeholder: 'שם מלא', tableWidth: 'min-w-[140px]' },
  { key: 'phone', label: 'טלפון', type: 'tel', placeholder: '050-0000000', tableWidth: 'min-w-[120px]' },
  { key: 'company_email', label: 'מייל חברה', type: 'email', placeholder: 'name@company.com', tableWidth: 'min-w-[180px]' },
  { key: 'birth_date', label: 'תאריך לידה', type: 'date', tableWidth: 'min-w-[110px]' },
  { key: 'expected_return_date', label: 'תאריך חזרה משוער', type: 'date', tableWidth: 'min-w-[130px]' },
  { key: 'gift_address', label: 'כתובת לשליחת מתנה', type: 'text', wide: true, placeholder: 'רחוב, מספר, עיר', tableWidth: 'min-w-[170px]' },
  {
    key: 'delivery_contact',
    label: 'איש קשר לשליח',
    type: 'group',
    tableWidth: 'min-w-[150px]',
    fields: [
      { key: 'delivery_contact_name', label: 'שם איש קשר', type: 'text', placeholder: 'שם' },
      { key: 'delivery_contact_phone', label: 'טלפון איש קשר', type: 'tel', placeholder: '050-0000000' },
    ],
  },
  { key: 'attendance_updated', label: 'עודכן בנוכחות', type: 'boolean', tableWidth: 'min-w-[100px]' },
  { key: 'notes', label: 'הערות', type: 'textarea', wide: true, placeholder: 'הערות חופשיות...', tableWidth: 'min-w-[160px]' },
];

/* Flat list of the actual data fields (groups expanded) */
export const MATERNITY_FIELDS = MATERNITY_COLUMNS.flatMap((c) =>
  c.type === 'group' ? c.fields : [c]
);

const EMPTY_BY_TYPE = { boolean: false };

export const emptyMaternityRecord = () =>
  Object.fromEntries(MATERNITY_FIELDS.map((f) => [f.key, EMPTY_BY_TYPE[f.type] ?? '']));

/* Form state -> API payload (trim strings, empty dates become null) */
export function toMaternityPayload(form) {
  return Object.fromEntries(
    MATERNITY_FIELDS.map((f) => {
      const v = form[f.key];
      if (f.type === 'boolean') return [f.key, Boolean(v)];
      if (f.type === 'date') return [f.key, v || null];
      return [f.key, typeof v === 'string' ? v.trim() : v ?? ''];
    })
  );
}

/* "2026-10-30" -> "30/10/2026" (string-based, so no timezone shifts) */
export function formatIsoDate(iso) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return y && m && d ? `${d}/${m}/${y}` : String(iso);
}
