import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, KeyRound, LogOut, ShieldCheck, User } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import RoleBadge from './RoleBadge';

export default function UserMenu() {
  const { profile, isAdmin, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  if (!profile) return null;
  const name = profile.display_name || profile.email;

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-gray-100 transition-colors"
      >
        <span className="bg-gray-100 text-gray-500 rounded-full p-1.5">
          <User className="h-4 w-4" />
        </span>
        <span className="hidden lg:block text-sm font-medium text-gray-700 max-w-[140px] truncate">{name}</span>
        <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-2 w-64 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden animate-fade-in">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900 truncate">{name}</p>
            <p className="text-xs text-gray-500 truncate mb-2" dir="ltr">
              {profile.email}
            </p>
            <RoleBadge role={profile.role} />
          </div>
          {isAdmin && (
            <Link
              to="/admin/users"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
            >
              <ShieldCheck className="h-4 w-4 text-indigo-500" />
              ניהול משתמשים
            </Link>
          )}
          <Link
            to={`/reset-password?email=${encodeURIComponent(profile.email)}`}
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            <KeyRound className="h-4 w-4 text-gray-400" />
            שינוי סיסמה (אימות SMS)
          </Link>
          <button
            type="button"
            onClick={logout}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50"
          >
            <LogOut className="h-4 w-4" />
            התנתקות
          </button>
        </div>
      )}
    </div>
  );
}
