import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { authApi } from '../api/client';
import { auth } from '../firebase';

const AuthContext = createContext(null);

/*
 * Signing in to Firebase only proves who the user is. Access is decided by the
 * backend (/api/auth/me): the email must be in the Firestore `users`
 * collection. Until that check passes, the user is treated as signed out.
 */
export function AuthProvider({ children }) {
  const [profile, setProfile] = useState(null); // { email, display_name, role, ... }
  const [loading, setLoading] = useState(Boolean(auth));
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    if (!auth) return undefined;
    return onAuthStateChanged(auth, async (firebaseUser) => {
      if (!firebaseUser) {
        setProfile(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const { data } = await authApi.me();
        setProfile(data);
        setAuthError('');
      } catch (err) {
        const status = err.response?.status;
        setAuthError(
          status === 403
            ? 'למשתמש זה אין הרשאת גישה למערכת. פנו למנהל/ת המערכת.'
            : status === 401
              ? 'פג תוקף ההתחברות. התחברו מחדש.'
              : 'לא ניתן להתחבר לשרת. ודאו שהשרת פועל ונסו שוב.'
        );
        setProfile(null);
        await signOut(auth);
      } finally {
        setLoading(false);
      }
    });
  }, []);

  const value = useMemo(
    () => ({
      profile,
      loading,
      authError,
      isAdmin: profile?.role === 'admin',
      login: async (email, password) => {
        setAuthError('');
        await signInWithEmailAndPassword(auth, email.trim(), password);
      },
      logout: () => signOut(auth),
      resetPassword: (email) => sendPasswordResetEmail(auth, email.trim()),
    }),
    [profile, loading, authError]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

/* Firebase Auth error code → Hebrew message */
export function firebaseErrorMessage(err) {
  switch (err?.code) {
    case 'auth/invalid-credential':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
    case 'auth/invalid-login-credentials':
      return 'מייל או סיסמה שגויים';
    case 'auth/invalid-email':
      return 'כתובת מייל לא תקינה';
    case 'auth/too-many-requests':
      return 'יותר מדי ניסיונות. נסו שוב בעוד כמה דקות או אפסו סיסמה.';
    case 'auth/user-disabled':
      return 'המשתמש הושבת';
    case 'auth/network-request-failed':
      return 'בעיית רשת. בדקו את החיבור לאינטרנט.';
    case 'auth/operation-not-allowed':
    case 'auth/configuration-not-found':
      return 'התחברות במייל וסיסמה אינה מופעלת בפרויקט ה-Firebase';
    default:
      return 'ההתחברות נכשלה. נסו שוב.';
  }
}
