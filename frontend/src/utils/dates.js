/*
 * Date-only helpers working on "YYYY-MM-DD" strings.
 * All math is done in UTC so local time zones / DST never shift the day.
 */

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})/;

const parseIso = (iso) => {
  const m = ISO_RE.exec(String(iso || ''));
  if (!m) return null;
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return Number.isNaN(d.getTime()) ? null : d;
};

const toIso = (d) => d.toISOString().slice(0, 10);

/* "2026-01-01" + 105 -> "2026-04-16"; returns '' for a missing/invalid date */
export function addDaysIso(iso, days) {
  const d = parseIso(iso);
  if (!d) return '';
  d.setUTCDate(d.getUTCDate() + days);
  return toIso(d);
}

/* 0 = Sunday … 6 = Saturday, or null for an invalid date */
export function weekdayOfIso(iso) {
  const d = parseIso(iso);
  return d ? d.getUTCDay() : null;
}

/*
 * Israeli work week (Sunday–Thursday): Friday and Saturday move back to Thursday.
 */
export function toIsraeliWorkday(iso) {
  const day = weekdayOfIso(iso);
  if (day === 5) return addDaysIso(iso, -1); // Friday -> Thursday
  if (day === 6) return addDaysIso(iso, -2); // Saturday -> Thursday
  return iso;
}

/* Maternity leave in Israel: 15 weeks from the birth date */
export const MATERNITY_LEAVE_DAYS = 15 * 7;
/* Follow-up call with the employee about her return: 13 weeks after the birth */
export const RETURN_FOLLOWUP_DAYS = 13 * 7;

export const expectedReturnDate = (birthIso) => addDaysIso(birthIso, MATERNITY_LEAVE_DAYS);

/* 13 weeks after the birth, moved back to Thursday if it lands on a weekend */
export const returnFollowupDate = (birthIso) => {
  const target = addDaysIso(birthIso, RETURN_FOLLOWUP_DAYS);
  return target ? toIsraeliWorkday(target) : '';
};
