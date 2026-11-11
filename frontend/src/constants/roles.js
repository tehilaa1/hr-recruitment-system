// Must stay identical to VALID_ROLES in backend/app/models/user.py
// (enforced by backend/tests/test_roles_sync.py).
export const ROLES = [
  {
    value: 'admin',
    label: 'מנהל/ת מערכת',
    description: 'גישה מלאה + ניהול משתמשים',
    badge: 'bg-indigo-100 text-indigo-700 border border-indigo-200',
  },
  {
    value: 'editor',
    label: 'עורך/ת',
    description: 'גישה מלאה למשרות, מועמדים וחופשות לידה',
    badge: 'bg-sky-100 text-sky-700 border border-sky-200',
  },
];

export const ROLE_BY_VALUE = Object.fromEntries(ROLES.map((r) => [r.value, r]));
