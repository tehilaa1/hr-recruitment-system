import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowRight,
  Briefcase,
  Check,
  CheckCircle2,
  Circle,
  Eye,
  EyeOff,
  FlaskConical,
  KeyRound,
  Loader2,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react';
import { apiErrorMessage, authApi } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { isStrongPassword, passwordChecks } from '../utils/passwordPolicy';

const inputClass =
  'w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition';
const primaryClass =
  'w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors';

const STEPS = [
  { key: 'email', label: 'זיהוי' },
  { key: 'code', label: 'קוד SMS' },
  { key: 'password', label: 'סיסמה חדשה' },
];

function StepIndicator({ current }) {
  const index = STEPS.findIndex((s) => s.key === current);
  return (
    <ol className="flex items-center justify-between mb-6" aria-label="שלבי איפוס הסיסמה">
      {STEPS.map((s, i) => {
        const done = i < index || current === 'done';
        const active = i === index;
        return (
          <li key={s.key} className="flex-1 flex items-center gap-2 last:flex-none">
            <span
              className={`flex items-center justify-center h-7 w-7 rounded-full text-xs font-bold flex-shrink-0 ${
                done ? 'bg-emerald-500 text-white' : active ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-400'
              }`}
              aria-current={active ? 'step' : undefined}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </span>
            <span className={`text-xs font-medium ${active ? 'text-gray-900' : 'text-gray-400'}`}>{s.label}</span>
            {i < STEPS.length - 1 && <span className="flex-1 h-px bg-gray-200 mx-1" />}
          </li>
        );
      })}
    </ol>
  );
}

function ErrorBox({ children }) {
  return children ? (
    <p role="alert" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
      {children}
    </p>
  ) : null;
}

function PasswordInput({ id, label, value, onChange, show, autoFocus }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        id={id}
        type={show ? 'text' : 'password'}
        dir="ltr"
        autoComplete="new-password"
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </div>
  );
}

/* Multi-step reset: email → SMS code → new password + confirmation */
export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { profile, logout } = useAuth();

  const [step, setStep] = useState('email');
  const [email, setEmail] = useState(params.get('email') || '');
  const [code, setCode] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [devCode, setDevCode] = useState('');
  const [resendIn, setResendIn] = useState(0);
  const codeRef = useRef(null);

  // Resend countdown
  useEffect(() => {
    if (resendIn <= 0) return undefined;
    const id = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [resendIn]);

  const run = async (fn) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sendCode = () =>
    run(async () => {
      const { data } = await authApi.requestResetCode(email.trim());
      setInfo(data.message);
      setDevCode(data.dev_code || '');
      setResendIn(data.resend_after || 60);
      setCode('');
      setStep('code');
      setTimeout(() => codeRef.current?.focus(), 0);
    });

  const handleEmail = (e) => {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('הזינו כתובת מייל תקינה');
      return;
    }
    sendCode();
  };

  const handleCode = (e) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError('הקוד מכיל 6 ספרות');
      return;
    }
    run(async () => {
      const { data } = await authApi.verifyResetCode(email.trim(), code);
      setToken(data.reset_token);
      setInfo('');
      setStep('password');
    });
  };

  const checks = passwordChecks(password, email);
  const matches = confirm.length > 0 && password === confirm;

  const handlePassword = (e) => {
    e.preventDefault();
    if (!isStrongPassword(password, email)) {
      setError('הסיסמה אינה עומדת בכל הדרישות');
      return;
    }
    if (password !== confirm) {
      setError('הסיסמאות אינן תואמות');
      return;
    }
    run(async () => {
      await authApi.confirmReset({
        email: email.trim(),
        reset_token: token,
        new_password: password,
        confirm_password: confirm,
      });
      setPassword('');
      setConfirm('');
      setStep('done');
      // All sessions were revoked on the server; sign this tab out too
      if (profile) await logout();
    });
  };

  const tokenExpired = step === 'password' && /פג/.test(error);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-gray-50 to-pink-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-blue-600 text-white p-3 rounded-2xl shadow-lg shadow-blue-200 mb-4">
            <Briefcase className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">איפוס סיסמה</h1>
          <p className="text-sm text-gray-500 mt-1">אימות באמצעות קוד שנשלח לטלפון הנייד</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-xl p-7">
          {step !== 'done' && <StepIndicator current={step} />}

          {devCode && step === 'code' && (
            <div className="flex gap-2 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3 mb-4">
              <FlaskConical className="h-5 w-5 flex-shrink-0" />
              <p>
                מצב פיתוח (SMS לא נשלח באמת): הקוד הוא{' '}
                <code dir="ltr" className="font-mono font-bold tracking-widest">{devCode}</code>
              </p>
            </div>
          )}

          {step === 'email' && (
            <form onSubmit={handleEmail} className="space-y-4" noValidate>
              <div>
                <label htmlFor="reset-email" className="block text-sm font-medium text-gray-700 mb-1.5">
                  מייל המשתמש
                </label>
                <input
                  id="reset-email"
                  type="email"
                  dir="ltr"
                  autoComplete="username"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
                <p className="text-xs text-gray-400 mt-1.5">
                  קוד אימות יישלח ב-SMS למספר הטלפון שמוגדר לחשבון. אם לא מוגדר מספר, פנו למנהל/ת המערכת.
                </p>
              </div>
              <ErrorBox>{error}</ErrorBox>
              <button type="submit" disabled={busy} className={primaryClass}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquare className="h-4 w-4" />}
                שליחת קוד ב-SMS
              </button>
            </form>
          )}

          {step === 'code' && (
            <form onSubmit={handleCode} className="space-y-4" noValidate>
              {info && (
                <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                  {info}
                </p>
              )}
              <div>
                <label htmlFor="reset-code" className="block text-sm font-medium text-gray-700 mb-1.5">
                  קוד אימות (6 ספרות)
                </label>
                <input
                  id="reset-code"
                  ref={codeRef}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  dir="ltr"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className={`${inputClass} text-center font-mono text-xl tracking-[0.5em]`}
                />
              </div>
              <ErrorBox>{error}</ErrorBox>
              <button type="submit" disabled={busy || code.length !== 6} className={primaryClass}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                אימות הקוד
              </button>
              <div className="flex items-center justify-between text-sm">
                <button
                  type="button"
                  onClick={() => { setStep('email'); setError(''); setDevCode(''); }}
                  className="text-gray-500 hover:text-gray-800"
                >
                  שינוי מייל
                </button>
                <button
                  type="button"
                  onClick={sendCode}
                  disabled={busy || resendIn > 0}
                  className="text-blue-600 hover:underline disabled:text-gray-400 disabled:no-underline"
                >
                  {resendIn > 0 ? `שליחה חוזרת בעוד ${resendIn} שנ׳` : 'שליחת קוד חדש'}
                </button>
              </div>
            </form>
          )}

          {step === 'password' && (
            <form onSubmit={handlePassword} className="space-y-4" noValidate>
              <PasswordInput id="new-password" label="סיסמה חדשה" value={password} onChange={setPassword} show={showPw} autoFocus />
              <ul className="grid grid-cols-2 gap-x-3 gap-y-1" aria-label="דרישות הסיסמה">
                {checks.map((c) => (
                  <li key={c.label} className={`flex items-center gap-1.5 text-xs ${c.ok ? 'text-emerald-600' : 'text-gray-400'}`}>
                    {c.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
                    {c.label}
                  </li>
                ))}
              </ul>
              <PasswordInput id="confirm-password" label="אימות סיסמה" value={confirm} onChange={setConfirm} show={showPw} />
              {confirm.length > 0 && (
                <p className={`text-xs ${matches ? 'text-emerald-600' : 'text-red-600'}`}>
                  {matches ? '✓ הסיסמאות תואמות' : 'הסיסמאות אינן תואמות'}
                </p>
              )}
              <button
                type="button"
                onClick={() => setShowPw((s) => !s)}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800"
              >
                {showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                {showPw ? 'הסתרת הסיסמה' : 'הצגת הסיסמה'}
              </button>
              <ErrorBox>{error}</ErrorBox>
              {tokenExpired ? (
                <button type="button" onClick={() => { setStep('email'); setError(''); }} className={primaryClass}>
                  התחלה מחדש
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={busy || !isStrongPassword(password, email) || !matches}
                  className={primaryClass}
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                  עדכון הסיסמה
                </button>
              )}
            </form>
          )}

          {step === 'done' && (
            <div className="flex flex-col items-center text-center gap-3 py-2">
              <div className="bg-emerald-100 text-emerald-600 rounded-full p-3">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <h2 className="text-lg font-bold text-gray-900">הסיסמה עודכנה</h2>
              <p className="text-sm text-gray-500">מטעמי אבטחה נותקו כל החיבורים הקיימים. התחברו עם הסיסמה החדשה.</p>
              <button type="button" onClick={() => navigate('/login', { replace: true })} className={`${primaryClass} mt-2`}>
                מעבר להתחברות
              </button>
            </div>
          )}
        </div>

        {step !== 'done' && (
          <Link to={profile ? '/' : '/login'} className="flex items-center justify-center gap-1 text-sm text-gray-500 hover:text-gray-800 mt-6">
            <ArrowRight className="h-4 w-4" />
            {profile ? 'חזרה למערכת' : 'חזרה להתחברות'}
          </Link>
        )}
      </div>
    </div>
  );
}
