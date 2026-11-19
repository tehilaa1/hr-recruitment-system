import { candidatesApi, openFileInNewTab, saveDownload, talentPoolApi } from '../api/client';

/* Same formats the backend stores (see backend/app/services/cv_file_service.py) */
export const CV_ACCEPT = '.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp';

// The browser can show these itself; Word files are downloaded instead
const VIEWABLE = /^(application\/pdf|image\/)/;

/*
 * Every stored CV file of a person (pool entries + job applications), newest first.
 * A pool candidate assigned to a job carries a copy of the same file, so files with
 * the same name and size are listed once.
 */
export function cvSources(profile) {
  const pool = (profile?.talent_pool_entries ?? []).map((e) => ({
    kind: 'pool',
    id: e.pool_id,
    label: 'מאגר המועמדים',
    cv: e.cv_file,
    created_at: e.created_at,
  }));
  const apps = (profile?.applications ?? []).map((a) => ({
    kind: 'application',
    id: a.candidate_id,
    jobId: a.job_id,
    label: a.job_title,
    cv: a.cv_file,
    created_at: a.created_at,
  }));
  const seen = new Set();
  return [...pool, ...apps]
    .filter((s) => s.cv)
    .sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
    .filter((s) => {
      const k = `${s.cv.file_name}|${s.cv.size}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
}

/* File names recorded at upload time on records whose file wasn't kept (uploaded before CV storage) */
export function missingCvNames(profile) {
  const records = [...(profile?.talent_pool_entries ?? []), ...(profile?.applications ?? [])];
  return [...new Set(records.filter((r) => r.file_name && !r.cv_file).map((r) => r.file_name))];
}

/* The record a newly attached CV goes to: the newest pool entry, else the newest application */
export function primaryRecord(profile) {
  const pool = profile?.talent_pool_entries?.[0];
  if (pool) return { kind: 'pool', id: pool.pool_id };
  const app = profile?.applications?.[0];
  return app ? { kind: 'application', id: app.candidate_id, jobId: app.job_id } : null;
}

const request = (source) =>
  source.kind === 'pool' ? talentPoolApi.getCv(source.id) : candidatesApi.getCv(source.jobId, source.id);

export function attachCv(record, file) {
  return record.kind === 'pool'
    ? talentPoolApi.attachCv(record.id, file)
    : candidatesApi.attachCv(record.jobId, record.id, file);
}

/* PDF / images open in a new tab; Word files are downloaded */
export function openCv(source) {
  const name = source.cv?.file_name || 'cv';
  if (VIEWABLE.test(source.cv?.content_type || '')) return openFileInNewTab(() => request(source), name);
  return downloadCv(source);
}

export async function downloadCv(source) {
  saveDownload(await request(source), source.cv?.file_name || 'cv');
}

export const formatBytes = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};
