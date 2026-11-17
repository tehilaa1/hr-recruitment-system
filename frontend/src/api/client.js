import axios from 'axios';
import { signOut } from 'firebase/auth';
import { auth } from '../firebase';

const RENDER_API_URL = 'https://hr-backend-3zw8.onrender.com';

/* Resolve the backend URL (Vite inlines import.meta.env at build time).
   Production builds never use a localhost value, even if one was set in the
   hosting provider's env vars — they fall back to the Render backend. */
function resolveBaseUrl() {
  const fromEnv = (import.meta.env.VITE_API_BASE_URL || '').trim();
  const isLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i.test(fromEnv);
  if (import.meta.env.PROD && (!fromEnv || isLocal)) return RENDER_API_URL;
  return (fromEnv || RENDER_API_URL).replace(/\/+$/, '');
}

export const BASE_URL = resolveBaseUrl();
// Visible in the browser console — confirms which backend the deployed build uses
console.info('[api] backend:', BASE_URL);

const http = axios.create({ baseURL: BASE_URL });

// Attach the Firebase ID token to every request (getIdToken refreshes it when needed)
http.interceptors.request.use(async (config) => {
  const user = auth?.currentUser;
  if (user) {
    config.headers.Authorization = `Bearer ${await user.getIdToken()}`;
  }
  return config;
});

// Session no longer valid on the server → sign out (AuthGuard then redirects to /login)
http.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && auth?.currentUser) {
      await signOut(auth);
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  me: () => http.get('/api/auth/me'),
  /* Password reset with an SMS code (public — works signed out) */
  requestResetCode: (email) => http.post('/api/auth/password-reset/request', { email }),
  verifyResetCode: (email, code) => http.post('/api/auth/password-reset/verify', { email, code }),
  confirmReset: (data) => http.post('/api/auth/password-reset/confirm', data),
};

export const budgetsApi = {
  list: () => http.get('/api/budgets'),
  get: (year) => http.get(`/api/budgets/${year}`),
  create: (data) => http.post('/api/budgets', data),
  update: (year, data) => http.patch(`/api/budgets/${year}`, data),
  remove: (year) => http.delete(`/api/budgets/${year}`),
  createEvent: (year, data) => http.post(`/api/budgets/${year}/events`, data),
  updateEvent: (year, id, data) => http.patch(`/api/budgets/${year}/events/${id}`, data),
  removeEvent: (year, id) => http.delete(`/api/budgets/${year}/events/${id}`),
  /* Itemized expenses of one holiday / event */
  listExpenses: (year, eventId) => http.get(`/api/budgets/${year}/events/${eventId}/expenses`),
  createExpense: (year, eventId, data) => http.post(`/api/budgets/${year}/events/${eventId}/expenses`, data),
  updateExpense: (year, eventId, id, data) =>
    http.patch(`/api/budgets/${year}/events/${eventId}/expenses/${id}`, data),
  removeExpense: (year, eventId, id) => http.delete(`/api/budgets/${year}/events/${eventId}/expenses/${id}`),
  exportExpenses: (year, eventId) =>
    http.get(`/api/budgets/${year}/events/${eventId}/export-excel`, { responseType: 'blob' }),
};

export const usersApi = {
  list: () => http.get('/api/users'),
  create: (data) => http.post('/api/users', data),
  update: (email, data) => http.patch(`/api/users/${encodeURIComponent(email)}`, data),
  remove: (email) => http.delete(`/api/users/${encodeURIComponent(email)}`),
};

export const jobsApi = {
  list: () => http.get('/api/jobs'),
  create: (data) => http.post('/api/jobs', data),
  get: (id) => http.get(`/api/jobs/${id}`),
  update: (id, data) => http.put(`/api/jobs/${id}`, data),
  remove: (id) => http.delete(`/api/jobs/${id}`),
  exportExcel: (id) =>
    http.get(`/api/jobs/${id}/export-excel`, { responseType: 'blob' }),
  /* AI-ranked talent-pool candidates for this job: [{ candidate, score, match_reason }] */
  matchPool: (id) => http.post(`/api/jobs/${id}/match-pool`),
};

/* multipart upload of CV files, reporting byte-upload progress (0–100) */
const uploadFiles = (url, files, onProgress) => {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  return http.post(url, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
};

export const talentPoolApi = {
  list: () => http.get('/api/talent-pool'),
  upload: (files, onProgress) => uploadFiles('/api/talent-pool/upload', files, onProgress),
  create: (data) => http.post('/api/talent-pool', data),
  remove: (id) => http.delete(`/api/talent-pool/${id}`),
};

export const searchApi = {
  /* Global search across all jobs; returns merged person profiles */
  candidates: (q, { signal } = {}) =>
    http.get('/api/candidates/search', { params: { q }, signal }),
};

export const maternityApi = {
  list: () => http.get('/api/maternity'),
  create: (data) => http.post('/api/maternity', data),
  update: (id, data) => http.patch(`/api/maternity/${id}`, data),
  remove: (id) => http.delete(`/api/maternity/${id}`),
  getSettings: () => http.get('/api/maternity/settings'),
  saveSettings: (data) => http.put('/api/maternity/settings', data),
  /* Privacy-filtered: no gift address / delivery contact */
  exportExcel: () => http.get('/api/maternity/export-excel', { responseType: 'blob' }),
};

/* Turn a FastAPI error response into a readable message */
export function apiErrorMessage(err, fallback = 'אירעה שגיאה. נסה שנית.') {
  // No response at all: server unreachable, still waking up (Render free tier), or blocked by CORS
  if (err && !err.response && err.code !== 'ERR_CANCELED') {
    return 'לא ניתן להתחבר לשרת. ייתכן שהשרת מתעורר — נסה שוב בעוד דקה.';
  }
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => String(d.msg || '').replace(/^Value error, /, '')).join(' · ');
  }
  return fallback;
}

/* Extract the (possibly UTF-8 encoded) filename from a Content-Disposition header */
export function filenameFromDisposition(header, fallback) {
  if (!header) return fallback;
  const utf8 = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) return decodeURIComponent(utf8[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : fallback;
}

/* Save a blob response (e.g. an Excel export) using the server's filename */
export function saveDownload(res, fallbackName) {
  const filename = filenameFromDisposition(res.headers['content-disposition'], fallbackName);
  const url = URL.createObjectURL(res.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const candidatesApi = {
  list: (jobId) => http.get(`/api/jobs/${jobId}/candidates`),

  upload: (jobId, files, onProgress) =>
    uploadFiles(`/api/jobs/${jobId}/candidates/upload`, files, onProgress),

  /* Manual entry, no CV file */
  create: (jobId, data) => http.post(`/api/jobs/${jobId}/candidates`, data),

  /* Copy a talent-pool candidate into this job */
  assignFromPool: (jobId, poolCandidateId) =>
    http.post(`/api/jobs/${jobId}/candidates/from-pool/${poolCandidateId}`),

  updateStatus: (jobId, candidateId, status) =>
    http.patch(`/api/jobs/${jobId}/candidates/${candidateId}/status`, {
      recruitment_status: status,
    }),

  setCompleted: (jobId, candidateId, isCompleted) =>
    http.patch(`/api/jobs/${jobId}/candidates/${candidateId}/complete`, {
      is_completed: isCompleted,
    }),

  remove: (jobId, candidateId) =>
    http.delete(`/api/jobs/${jobId}/candidates/${candidateId}`),
};
