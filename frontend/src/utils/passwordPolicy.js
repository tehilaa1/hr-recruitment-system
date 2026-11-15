/*
 * Password rules shown as a live checklist. The server enforces the same rules
 * (backend/app/services/password_policy.py) — the two lengths below must match
 * there (enforced by backend/tests/test_password_reset.py).
 */
export const PASSWORD_MIN_LENGTH = 10;
export const PASSWORD_MAX_LENGTH = 128;

const COMMON = new Set([
  'password1', 'password12', 'password123', 'password1234', 'passw0rd123',
  'qwerty1234', 'qwerty12345', '1q2w3e4r5t', 'abc1234567', 'abcd123456',
  'a123456789', '1234567890a', 'iloveyou123', 'welcome123', 'admin12345',
  'letmein123', 'shalom1234', 'israel1234',
]);

/* [{ label, ok }] for the checklist; `email` hides the "no username" rule when unknown */
export function passwordChecks(password, email = '') {
  const pw = password || '';
  const local = (email || '').split('@')[0].toLowerCase();
  const checks = [
    { label: `לפחות ${PASSWORD_MIN_LENGTH} תווים`, ok: pw.length >= PASSWORD_MIN_LENGTH && pw.length <= PASSWORD_MAX_LENGTH },
    { label: 'לפחות אות אחת', ok: /[A-Za-z֐-׿]/.test(pw) },
    { label: 'לפחות ספרה אחת', ok: /\d/.test(pw) },
    {
      label: 'לא פשוטה או נפוצה מדי',
      ok: pw.length > 0 && new Set(pw).size >= 4 && !COMMON.has(pw.toLowerCase()) && pw === pw.trim(),
    },
  ];
  if (local.length >= 3) {
    checks.push({ label: 'לא מכילה את שם המשתמש', ok: pw.length > 0 && !pw.toLowerCase().includes(local) });
  }
  return checks;
}

export const isStrongPassword = (password, email) => passwordChecks(password, email).every((c) => c.ok);
