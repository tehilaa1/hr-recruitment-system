import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { AlertTriangle, Briefcase, Loader2, LogIn } from 'lucide-react';
import { firebaseErrorMessage, useAuth } from '../auth/AuthContext';
import { isFirebaseConfigured } from '../firebase';

const inputClass =
  'w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition';

export default function Login() {
  const { profile, loading, authError, login, resetPassword } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  // Already signed in and authorized → go where the user was heading
  if (profile) {
    const from = location.state?.from;
    return <Navigate to={from ? `${from.pathname}${from.search ?? ''}` : '/'} replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    if (!email.trim() || !password) {
      setError('יש להזין מייל וסיסמה');
      return;
    }
    setSubmitting(true);
    try {
      await login(email, password);
      // On success, AuthProvider checks authorization and this page redirects
    } catch (err) {
      setError(firebaseErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = async () => {
    setError('');
    setInfo('');
    if (!email.trim()) {
      setError('הזינו את כתובת המייל ואז לחצו על "שכחתי סיסמה"');
      return;
    }
    try {
      await resetPassword(email);
    } catch {
      // Don't reveal whether the account exists
    }
    setInfo('אם קיים חשבון עם כתובת זו, נשלח אליה מייל לאיפוס סיסמה.');
  };

  const busy = submitting || loading;
  const shownError = error || authError;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-gray-50 to-pink-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-blue-600 text-white p-3 rounded-2xl shadow-lg shadow-blue-200 mb-4">
            <Briefcase className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">HireTrack</h1>
          <p className="text-sm text-gray-500 mt-1">מערכת ניהול משאבי אנוש</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-7">
          {!isFirebaseConfigured ? (
            <div className="flex gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3">
              <AlertTriangle className="h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-semibold">Firebase לא מוגדר</p>
                <p className="mt-1">
                  העתיקו את <code dir="ltr">frontend/.env.example</code> ל-<code dir="ltr">frontend/.env</code>,
                  מלאו את פרטי ה-Web App מ-Firebase והפעילו מחדש את שרת ה-frontend.
                </p>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <h2 className="text-lg font-bold text-gray-900 mb-1">התחברות</h2>
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                  מייל
                </label>
                <input
                  id="email"
                  type="email"
                  dir="ltr"
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                  סיסמה
                </label>
                <input
                  id="password"
                  type="password"
                  dir="ltr"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                />
              </div>

              {shownError && (
                <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {shownError}
                </p>
              )}
              {info && (
                <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                  {info}
                </p>
              )}

              <button
                type="submit"
                disabled={busy}
                className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                כניסה
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="w-full text-center text-sm text-blue-600 hover:underline"
              >
                שכחתי סיסמה
              </button>
            </form>
          )}
        </div>
        <p className="text-center text-xs text-gray-400 mt-6">הגישה למערכת מותנית בהרשאה ממנהל/ת המערכת</p>
      </div>
    </div>
  );
}
