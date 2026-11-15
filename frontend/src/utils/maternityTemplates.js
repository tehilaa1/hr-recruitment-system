import { formatIsoDate } from '../constants/maternityColumns';

/*
 * Maternity message templates.
 *
 * Templates are plain text with {placeholders}. The defaults below are used
 * unless the user saved their own text in the maternity settings
 * (settings.templates; an empty string there = "use the default").
 */

/* Placeholder -> label shown in the settings screen.
   Keys must match TEMPLATE_PLACEHOLDERS in backend/app/models/maternity.py
   (enforced by backend/tests/test_maternity_fields_sync.py). */
export const TEMPLATE_PLACEHOLDERS = {
  name: 'שם העובדת',
  phone: 'טלפון',
  company_email: 'מייל חברה',
  birth_date: 'תאריך לידה',
  baby_gender: 'בן / בת',
  baby_phrase: '״בנה״ / ״בתה״ / ״התינוק/ת״',
  baby_heart: 'לב בצבע לפי בן/בת (💙 / 💗)',
  expected_return_date: 'תאריך חזרה משוער',
  gift_address: 'כתובת למתנה',
  delivery_contact: 'איש קשר לשליח',
  attendance_updated: 'עודכן בנוכחות (כן/לא)',
  notes: 'הערות',
};

/* The two update-message types the user can choose between */
export const MESSAGE_TYPES = [
  {
    key: 'initial',
    label: 'הודעת עדכון ראשונית',
    description: 'הודעה קצרה: העובדת ילדה, ובימים הקרובים נדבר איתה לקבלת הפרטים',
  },
  {
    key: 'full',
    label: 'הודעה עם הפרטים המלאים',
    description: 'כל הפרטים: תאריך לידה, בן/בת, תאריך חזרה, פרטי קשר ומשלוח מתנה',
  },
];

/* Built-in texts. Keys must match MaternityTemplates in the backend (enforced by test). */
export const DEFAULT_TEMPLATES = {
  initial_subject: 'עדכון: {name} ילדה',
  initial_body: [
    'שלום לכולם,',
    '',
    'שמחים לעדכן ש{name} ילדה. מזל טוב! 🎉',
    '',
    'בימים הקרובים נדבר איתה כדי לקבל את כל הפרטים, ונעדכן אתכם בהמשך.',
    '',
    'תודה,',
  ].join('\n'),
  full_subject: 'עדכון חופשת לידה – {name}',
  full_body: [
    'שלום לכולם,',
    '',
    'לעדכונכם, {name} יצאה לחופשת לידה.',
    '',
    'פרטי העובדת:',
    '• שם: {name}',
    '• תאריך לידה: {birth_date}',
    '• הרך הנולד: {baby_gender}',
    '• תאריך חזרה משוער: {expected_return_date}',
    '• טלפון: {phone}',
    '• מייל חברה: {company_email}',
    '• עודכן בנוכחות: {attendance_updated}',
    '',
    'משלוח מתנה:',
    '• כתובת: {gift_address}',
    '• איש קשר לשליח: {delivery_contact}',
    '',
    'הערות: {notes}',
    '',
    'תודה,',
  ].join('\n'),
  teams_announcement: [
    '🎉👶 מזל טוב! 👶🎉',
    '',
    'בשמחה רבה אנו מבשרים על הולדת {baby_phrase} של {name} ({birth_date})!',
    '',
    'מאחלים ל{name} ולכל המשפחה המון מזל טוב, בריאות, נחת ושמחה 💐',
    'מחכים לראותך בחזרה! {baby_heart}',
  ].join('\n'),
};

const orDash = (v) => (v && String(v).trim()) || '—';

/* "בנה" / "בתה" / "התינוק/ת" — for phrases like "הולדת בנה של דנה" */
const babyPhrase = (gender) => (gender === 'בן' ? 'בנה' : gender === 'בת' ? 'בתה' : 'התינוק/ת');

/* Values for every placeholder, taken from a maternity record */
export function templateValues(record) {
  const r = record ?? {};
  return {
    name: orDash(r.name),
    phone: orDash(r.phone),
    company_email: orDash(r.company_email),
    birth_date: orDash(formatIsoDate(r.birth_date)),
    baby_gender: orDash(r.baby_gender),
    baby_phrase: babyPhrase(r.baby_gender),
    baby_heart: r.baby_gender === 'בן' ? '💙' : r.baby_gender === 'בת' ? '💗' : '💛',
    expected_return_date: orDash(formatIsoDate(r.expected_return_date)),
    gift_address: orDash(r.gift_address),
    delivery_contact: orDash(
      [r.delivery_contact_name, r.delivery_contact_phone].filter((v) => v && String(v).trim()).join(' – ')
    ),
    attendance_updated: r.attendance_updated ? 'כן' : 'לא',
    notes: orDash(r.notes),
  };
}

/* Replace {placeholders}; unknown ones are left as typed so mistakes stay visible */
export function renderTemplate(template, record) {
  const values = templateValues(record);
  return String(template ?? '').replace(/\{(\w+)\}/g, (match, key) =>
    Object.prototype.hasOwnProperty.call(values, key) ? values[key] : match
  );
}

/* The saved custom text for a template, or the built-in default */
export const effectiveTemplate = (settings, key) =>
  settings?.templates?.[key]?.trim() ? settings.templates[key] : DEFAULT_TEMPLATES[key];

/* Email for one of MESSAGE_TYPES ("initial" | "full") */
export function buildMaternityMessage(type, record, settings) {
  return {
    subject: renderTemplate(effectiveTemplate(settings, `${type}_subject`), record),
    body: renderTemplate(effectiveTemplate(settings, `${type}_body`), record),
  };
}

/* Celebratory announcement for the general Teams channel */
export const buildTeamsAnnouncement = (record, settings) =>
  renderTemplate(effectiveTemplate(settings, 'teams_announcement'), record);

/* Clipboard with a fallback for older browsers / non-secure contexts */
export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}
