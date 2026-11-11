import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

/*
 * Firebase web config, read from frontend/.env (see .env.example).
 * Values come from Firebase Console → Project settings → Your apps → Web app.
 * These are public identifiers, not secrets; access is enforced by the backend.
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId
);

export const auth = isFirebaseConfigured ? getAuth(initializeApp(firebaseConfig)) : null;
