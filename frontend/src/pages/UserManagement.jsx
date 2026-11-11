import { useEffect, useState } from 'react';
import { KeyRound, Loader2, RefreshCw, ShieldCheck, Trash2, UserPlus } from 'lucide-react';
import { apiErrorMessage, usersApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import Navbar from '../components/Navbar';
import RoleBadge from '../components/RoleBadge';
import { ROLES } from '../constants/roles';

const inputClass =
  'border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition';

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('he-IL', { year: 'numeric', month: 'short', day: 'numeric' }) : '—';

function AddUserForm({ onAdded }) {
  const { resetPassword } = useAuth();
  const [form, setForm] = useState({ email: '', display_name: '', role: 'editor' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.email.trim()) {
      setError('יש להזין כתובת מייל');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await usersApi.create(form);
      let message;
      if (data.created_account) {
        // New account has a random password; Firebase emails a "set your password" link
        try {
          await resetPassword(data.user.email);
          message = `${data.user.email} נוסף/ה. נשלח אליו/ה מייל להגדרת סיסמה.`;
        } catch {
          message = `${data.user.email} נוסף/ה, אך שליחת מייל הגדרת הסיסמה נכשלה – השתמשו בכפתור "שליחת איפוס סיסמה".`;
        }
      } else {
        message = `${data.user.email} נוסף/ה (חשבון קיים – ניתן להתחבר עם הסיסמה הקיימת).`;
      }
      onAdded(data.user, message);
      setForm({ email: '', display_name: '', role: 'editor' });
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בהוספת המשתמש'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="p-6 border-b border-gray-100 space-y-3">
      <h2 className="flex items-center gap-2 text-sm font-bold text-gray-900">
        <UserPlus className="h-4 w-4 text-indigo-500" />
        הוספת משתמש מורשה
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-[2fr_1.5fr_1fr_auto] gap-3">
        <input
          type="email"
          dir="ltr"
          placeholder="name@company.com"
          value={form.email}
          onChange={(e) => set('email', e.target.value)}
          className={inputClass}
          aria-label="מייל"
        />
        <input
          placeholder="שם לתצוגה"
          value={form.display_name}
          onChange={(e) => set('display_name', e.target.value)}
          className={inputClass}
          aria-label="שם"
        />
        <select
          value={form.role}
          onChange={(e) => set('role', e.target.value)}
          className={inputClass}
          aria-label="תפקיד"
        >
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={saving}
          className="flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
          הוספה
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </form>
  );
}

export default function UserManagement() {
  const { profile, resetPassword } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busyEmail, setBusyEmail] = useState(null);
  const [notice, setNotice] = useState(null); // { type: 'ok' | 'error', text }

  const fetchUsers = async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const { data } = await usersApi.list();
      setUsers(data);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const flash = (type, text) => setNotice({ type, text });

  const handleRoleChange = async (user, role) => {
    setBusyEmail(user.email);
    try {
      const { data } = await usersApi.update(user.email, { role });
      setUsers((prev) => prev.map((u) => (u.email === user.email ? data : u)));
      flash('ok', `התפקיד של ${user.email} עודכן`);
    } catch (err) {
      flash('error', apiErrorMessage(err, 'שגיאה בעדכון התפקיד'));
    } finally {
      setBusyEmail(null);
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`להסיר את הגישה של ${user.email}? חשבון ההתחברות שלו/ה יימחק.`)) return;
    setBusyEmail(user.email);
    try {
      await usersApi.remove(user.email);
      setUsers((prev) => prev.filter((u) => u.email !== user.email));
      flash('ok', `הגישה של ${user.email} הוסרה`);
    } catch (err) {
      flash('error', apiErrorMessage(err, 'שגיאה בהסרת המשתמש'));
    } finally {
      setBusyEmail(null);
    }
  };

  const handleSendReset = async (user) => {
    try {
      await resetPassword(user.email);
      flash('ok', `נשלח מייל לאיפוס סיסמה אל ${user.email}`);
    } catch {
      flash('error', 'שליחת המייל נכשלה');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
            <ShieldCheck className="h-6 w-6 text-indigo-500" />
            ניהול משתמשים והרשאות
          </h1>
          <p className="text-sm text-gray-400 mt-1">רק משתמשים ברשימה זו יכולים להתחבר למערכת</p>
        </div>

        {notice && (
          <div
            role="status"
            className={`flex items-center justify-between text-sm rounded-xl px-4 py-3 border ${
              notice.type === 'ok'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-red-50 border-red-200 text-red-700'
            }`}
          >
            <span>{notice.text}</span>
            <button onClick={() => setNotice(null)} className="text-xs opacity-70 hover:opacity-100">
              סגירה
            </button>
          </div>
        )}

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <AddUserForm
            onAdded={(user, message) => {
              setUsers((prev) => [...prev, user]);
              flash('ok', message);
            }}
          />

          {loading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-7 w-7 text-indigo-500 animate-spin" />
            </div>
          ) : loadError ? (
            <div className="flex flex-col items-center py-16 gap-3">
              <p className="text-gray-500">שגיאה בטעינת המשתמשים</p>
              <button onClick={fetchUsers} className="flex items-center gap-2 text-sm text-indigo-600 hover:underline">
                <RefreshCw className="h-4 w-4" />
                נסה שנית
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200 text-xs text-gray-500">
                    <th className="px-4 py-3 text-right font-semibold">משתמש</th>
                    <th className="px-4 py-3 text-right font-semibold">תפקיד</th>
                    <th className="px-4 py-3 text-right font-semibold">נוסף</th>
                    <th className="px-4 py-3 text-right font-semibold">פעולות</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {users.map((u) => {
                    const isSelf = u.email === profile?.email;
                    const busy = busyEmail === u.email;
                    return (
                      <tr key={u.email} className="hover:bg-gray-50/60">
                        <td className="px-4 py-3">
                          <p className="font-medium text-gray-900">
                            {u.display_name || u.email}
                            {isSelf && <span className="text-xs text-gray-400 font-normal"> (את/ה)</span>}
                          </p>
                          {u.display_name && (
                            <p className="text-xs text-gray-500" dir="ltr">
                              {u.email}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isSelf ? (
                            <RoleBadge role={u.role} />
                          ) : (
                            <select
                              value={u.role}
                              disabled={busy}
                              onChange={(e) => handleRoleChange(u, e.target.value)}
                              className={`${inputClass} py-1.5`}
                              aria-label={`תפקיד של ${u.email}`}
                            >
                              {ROLES.map((r) => (
                                <option key={r.value} value={r.value}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {formatDate(u.created_at)}
                          {u.created_by && <p className="text-xs text-gray-400">ע״י {u.created_by}</p>}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleSendReset(u)}
                              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100"
                              title="שליחת מייל לאיפוס / הגדרת סיסמה"
                            >
                              <KeyRound className="h-3.5 w-3.5" />
                              שליחת איפוס סיסמה
                            </button>
                            {!isSelf && (
                              <button
                                onClick={() => handleDelete(u)}
                                disabled={busy}
                                className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 disabled:opacity-50"
                                title="הסרת גישה"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="text-xs text-gray-500 bg-white border border-gray-100 rounded-xl p-4 space-y-1">
          {ROLES.map((r) => (
            <p key={r.value}>
              <RoleBadge role={r.value} /> <span className="mr-1">{r.description}</span>
            </p>
          ))}
        </div>
      </main>
    </div>
  );
}
