/*
 * Outlook (on the web) deep links.
 *
 * Outlook on the web is used because it's the only way to open a pre-filled
 * calendar invite with the date/time left for the user to choose; a .ics file
 * or a mailto: link can't do that.
 *
 * Personal Outlook.com accounts use https://outlook.live.com instead. Set
 * VITE_OUTLOOK_BASE_URL in frontend/.env to switch.
 */
import { formatIsoDate } from '../constants/maternityColumns';
import { localDateTimeToUtc, returnFollowupDate } from './dates';

const OUTLOOK_BASE_URL =
  import.meta.env.VITE_OUTLOOK_BASE_URL || 'https://outlook.office.com';

export const REJECTION_EMAIL_BODY = `היי,
תודה רבה על הזמן שהקדשת ועל ההתעניינות במשרה אצלנו.
לאחר בחינת ההתאמה, החלטנו שלא להתקדם עם המועמדות שלך לתפקיד הספציפי הזה.
עם זאת, נשמח לשמור על קשר, ובמידה שתיפתח אצלנו בהמשך משרה שתתאים יותר לכישורייך ולניסיונך, נשמח לפנות אלייך ולבחון את האפשרות יחד.
מאחלים לך המון הצלחה בהמשך הדרך!`;

const buildQuery = (params) =>
  Object.entries(params)
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&');

const fullName = (c) => [c.full_name, c.family_name].filter(Boolean).join(' ');

const joinEmails = (list) =>
  [...new Set((Array.isArray(list) ? list : [list]).map((e) => e?.trim()).filter(Boolean))].join(',');

/* Generic pre-filled Outlook email draft; nothing is sent until you click Send */
export function buildMailComposeUrl({ to, cc, subject, body }) {
  const query = buildQuery({ to: joinEmails(to), cc: joinEmails(cc), subject, body });
  return `${OUTLOOK_BASE_URL}/mail/deeplink/compose?${query}`;
}

/* Pre-filled rejection email. Every field can still be edited in Outlook before sending. */
export function buildRejectionEmailUrl(candidate, job) {
  return buildMailComposeUrl({
    to: candidate.email,
    subject: job?.job_title
      ? `עדכון לגבי מועמדותך לתפקיד ${job.job_title}`
      : 'עדכון לגבי מועמדותך',
    body: REJECTION_EMAIL_BODY,
  });
}

/*
 * Interview invite. Attendees are the interviewers plus the candidate.
 * No start/end time is sent, so you pick the date and time in Outlook.
 */
export function buildInterviewInviteUrl(candidate, job) {
  const attendees = [...(job?.interviewer_emails ?? []), candidate.email]
    .map((e) => e?.trim())
    .filter(Boolean);
  const uniqueAttendees = [...new Set(attendees)];

  const location = job?.interview_location?.trim() || '';
  const name = fullName(candidate);

  const bodyLines = [
    `ראיון עבודה${job?.job_title ? ` לתפקיד ${job.job_title}` : ''}${name ? ` עם ${name}` : ''}.`,
    '',
    location ? `כתובת הראיון: ${location}` : null,
    job?.interviewers?.length ? `מראיינים: ${job.interviewers.join(', ')}` : null,
  ].filter((l) => l !== null);

  const query = buildQuery({
    subject: ['ראיון עבודה', job?.job_title, name].filter(Boolean).join(' - '),
    to: uniqueAttendees.join(','),
    location,
    body: bodyLines.join('\n'),
  });
  return `${OUTLOOK_BASE_URL}/calendar/0/deeplink/compose?${query}`;
}

/*
 * Calendar reminder to call an employee on maternity leave about her return.
 * Scheduled 13 weeks after the birth (moved back to Thursday if that is a
 * Friday/Saturday), 10:00–10:30 in the user's own Outlook time zone.
 * Returns '' when the record has no birth date.
 */
export function buildMaternityReminderUrl(record) {
  const date = returnFollowupDate(record?.birth_date);
  if (!date) return '';
  const name = record.name?.trim() || '';

  const body = [
    'תזכורת: ליצור קשר עם העובדת כדי לבדוק את מועד החזרה מחופשת הלידה.',
    '',
    `שם: ${name || '—'}`,
    `טלפון: ${record.phone?.trim() || '—'}`,
    `תאריך לידה: ${formatIsoDate(record.birth_date) || '—'}`,
    `תאריך חזרה משוער: ${formatIsoDate(record.expected_return_date) || '—'}`,
  ].join('\n');

  return buildCalendarEventUrl({
    subject: `יצירת קשר עם יולדת לבדיקת מועד חזרה${name ? ` - ${name}` : ''}`,
    body,
    start: localDateTimeToUtc(date, REMINDER_START),
    end: localDateTimeToUtc(date, REMINDER_END),
  });
}

const REMINDER_START = '10:00';
const REMINDER_END = '10:30';

/*
 * New-event form with a fixed date/time already filled in.
 * Uses the "add event" compose route (rru=addevent + path), which pre-fills
 * startdt/enddt reliably; times are UTC ISO strings ("…Z") so Outlook shows
 * them in the user's own time zone without guessing.
 */
export function buildCalendarEventUrl({ subject, body, start, end, location }) {
  const query = buildQuery({
    path: '/calendar/action/compose',
    rru: 'addevent',
    allday: 'false',
    startdt: start,
    enddt: end,
    subject,
    body,
    location,
  });
  return `${OUTLOOK_BASE_URL}/calendar/0/action/compose?${query}`;
}

export function openInNewTab(url) {
  window.open(url, '_blank', 'noopener,noreferrer');
}
