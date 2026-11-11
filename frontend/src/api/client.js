import axios from 'axios';

const BASE_URL = 'http://localhost:8000';

const http = axios.create({ baseURL: BASE_URL });

export const jobsApi = {
  list: () => http.get('/api/jobs'),
  create: (data) => http.post('/api/jobs', data),
  get: (id) => http.get(`/api/jobs/${id}`),
  update: (id, data) => http.put(`/api/jobs/${id}`, data),
  remove: (id) => http.delete(`/api/jobs/${id}`),
  exportExcel: (id) =>
    http.get(`/api/jobs/${id}/export-excel`, { responseType: 'blob' }),
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
};

/* Turn a FastAPI error response into a readable message */
export function apiErrorMessage(err, fallback = 'אירעה שגיאה. נסה שנית.') {
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

export const candidatesApi = {
  list: (jobId) => http.get(`/api/jobs/${jobId}/candidates`),

  upload: (jobId, files) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return http.post(`/api/jobs/${jobId}/candidates/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  updateStatus: (jobId, candidateId, status) =>
    http.patch(`/api/jobs/${jobId}/candidates/${candidateId}/status`, {
      recruitment_status: status,
    }),

  remove: (jobId, candidateId) =>
    http.delete(`/api/jobs/${jobId}/candidates/${candidateId}`),
};
