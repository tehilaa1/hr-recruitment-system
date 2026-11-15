import { formatIsoDate } from '../constants/maternityColumns';

const orDash = (v) => (v && String(v).trim()) || '—';

/* "הולדת בנה של דנה" / "הולדת בתה של דנה" / "הולדת התינוק/ת של דנה" */
const babyPhrase = (record) =>
  record.baby_gender === 'בן' ? 'בנה' : record.baby_gender === 'בת' ? 'בתה' : 'התינוק/ת';

/* Structured summary email for the fixed recipient list */
export function buildMaternityEmail(record) {
  const contact = [record.delivery_contact_name, record.delivery_contact_phone]
    .filter(Boolean)
    .join(' – ');

  const lines = [
    'שלום לכולם,',
    '',
    `לעדכונכם, ${record.name} יצא/ה לחופשת לידה.`,
    '',
    'פרטי העובד/ת:',
    `• שם: ${orDash(record.name)}`,
    `• תאריך לידה: ${orDash(formatIsoDate(record.birth_date))}`,
    `• הרך הנולד: ${orDash(record.baby_gender)}`,
    `• תאריך חזרה משוער: ${orDash(formatIsoDate(record.expected_return_date))}`,
    `• טלפון: ${orDash(record.phone)}`,
    `• מייל חברה: ${orDash(record.company_email)}`,
    `• עודכן בנוכחות: ${record.attendance_updated ? 'כן' : 'לא'}`,
    '',
    'משלוח מתנה:',
    `• כתובת: ${orDash(record.gift_address)}`,
    `• איש קשר לשליח: ${orDash(contact)}`,
  ];
  if (record.notes?.trim()) lines.push('', `הערות: ${record.notes.trim()}`);
  lines.push('', 'תודה,');

  return {
    subject: `עדכון חופשת לידה – ${record.name}`,
    body: lines.join('\n'),
  };
}

/* Celebratory announcement for the general Teams channel */
export function buildTeamsAnnouncement(record) {
  const date = formatIsoDate(record.birth_date);
  const heart = record.baby_gender === 'בן' ? '💙' : record.baby_gender === 'בת' ? '💗' : '💛';
  return [
    '🎉👶 מזל טוב! 👶🎉',
    '',
    `בשמחה רבה אנו מבשרים על הולדת ${babyPhrase(record)} של ${record.name}${date ? ` (${date})` : ''}!`,
    '',
    `מאחלים ל${record.name} ולכל המשפחה המון מזל טוב, בריאות, נחת ושמחה 💐`,
    `מחכים לראותך בחזרה! ${heart}`,
  ].join('\n');
}

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
