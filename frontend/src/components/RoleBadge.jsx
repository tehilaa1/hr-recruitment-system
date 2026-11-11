import { ROLE_BY_VALUE } from '../constants/roles';

export default function RoleBadge({ role }) {
  const r = ROLE_BY_VALUE[role];
  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
        r?.badge ?? 'bg-gray-100 text-gray-600'
      }`}
    >
      {r?.label ?? role}
    </span>
  );
}
