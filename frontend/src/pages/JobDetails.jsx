import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowRight,
  Calendar,
  Download,
  Loader2,
  Mail,
  MapPin,
  RefreshCw,
  UserPlus,
  Users,
} from 'lucide-react';
import { candidatesApi, jobsApi, saveDownload } from '../api/client';
import CandidateFormModal from '../components/CandidateFormModal';
import CandidatesTable from '../components/CandidatesTable';
import Navbar from '../components/Navbar';
import PoolSuggestions from '../components/PoolSuggestions';
import UploadBox from '../components/UploadBox';

/* ── Tiny helpers ── */
const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('he-IL', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

function MetaItem({ icon: Icon, label, value }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 text-gray-400 text-xs mb-1">
        <Icon className="h-3.5 w-3.5 flex-shrink-0" />
        <span>{label}</span>
      </div>
      <p className="text-sm font-medium text-gray-800 truncate" title={value}>
        {value}
      </p>
    </div>
  );
}

function SectionCard({ title, subtitle, action, children }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <h2 className="text-base font-bold text-gray-900">{title}</h2>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function LoadingPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
    </div>
  );
}

function ErrorPage({ onRetry }) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
      <p className="text-gray-500">שגיאה בטעינת הנתונים</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 text-blue-600 hover:underline text-sm"
      >
        <RefreshCw className="h-4 w-4" />
        נסה שנית
      </button>
    </div>
  );
}

function candidatesSubtitle(candidates) {
  if (!candidates.length) return null;
  const total = `${candidates.length} מועמד${candidates.length !== 1 ? 'ים' : ''}`;
  const done = candidates.filter((c) => c.is_completed).length;
  return done ? `${total} · ${done} טופלו` : total;
}

/* ── Job Details Page ── */
export default function JobDetails() {
  const { jobId } = useParams();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showManualAdd, setShowManualAdd] = useState(false);
  // Ignore responses from a previous job if the user navigated meanwhile
  const jobIdRef = useRef(jobId);
  jobIdRef.current = jobId;

  const fetchAll = async () => {
    setLoading(true);
    setFetchError(false);
    try {
      const [jobRes, candidatesRes] = await Promise.all([
        jobsApi.get(jobId),
        candidatesApi.list(jobId),
      ]);
      setJob(jobRes.data);
      setCandidates(candidatesRes.data);
    } catch {
      setFetchError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, [jobId]);

  /* Background re-fetch of the candidate list + job stats (no full-page spinner) */
  const refreshCandidates = useCallback(async () => {
    const forJob = jobId;
    setRefreshing(true);
    try {
      const [jobRes, candidatesRes] = await Promise.all([
        jobsApi.get(forJob),
        candidatesApi.list(forJob),
      ]);
      if (jobIdRef.current !== forJob) return;
      setJob(jobRes.data);
      setCandidates(candidatesRes.data);
    } catch {
      // Keep what we have; the optimistic merge already shows the new candidates
    } finally {
      if (jobIdRef.current === forJob) setRefreshing(false);
    }
  }, [jobId]);

  /* Add records returned by the server, skipping ids already in the list */
  const mergeCandidates = (incoming) => {
    if (!incoming.length) return;
    setCandidates((prev) => {
      const known = new Set(prev.map((c) => c.id));
      return [...incoming.filter((c) => !known.has(c.id)), ...prev];
    });
    setJob((prev) => (prev ? { ...prev, candidate_count: (prev.candidate_count || 0) + incoming.length } : prev));
  };

  /* Optimistic status update */
  const setCandidateStatus = (candidateId, status) =>
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, recruitment_status: status } : c))
    );

  const handleStatusChange = async (candidateId, status) => {
    // Remember the saved status *before* the optimistic update so it can be restored
    const previousStatus = candidates.find((c) => c.id === candidateId)?.recruitment_status;
    if (previousStatus === status) return;

    setCandidateStatus(candidateId, status);
    try {
      await candidatesApi.updateStatus(jobId, candidateId, status);
    } catch {
      // Only roll back if nothing newer has replaced our optimistic value meanwhile
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candidateId && c.recruitment_status === status
            ? { ...c, recruitment_status: previousStatus }
            : c
        )
      );
      alert('שגיאה בעדכון הסטטוס – הסטטוס הוחזר לערכו הקודם');
    }
  };

  /* Optimistic "סיום טיפול" toggle, rolled back on error (same pattern as status) */
  const handleToggleComplete = async (candidateId, isCompleted) => {
    setCandidates((prev) =>
      prev.map((c) => (c.id === candidateId ? { ...c, is_completed: isCompleted } : c))
    );
    try {
      await candidatesApi.setCompleted(jobId, candidateId, isCompleted);
    } catch {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candidateId && c.is_completed === isCompleted
            ? { ...c, is_completed: !isCompleted }
            : c
        )
      );
      alert('שגיאה בעדכון סיום הטיפול – השינוי בוטל');
    }
  };

  /* Inline "הובא על ידי" edit; the table cell shows errors and keeps the old value */
  const handleReferrerChange = async (candidateId, referredBy) => {
    const { data } = await candidatesApi.update(jobId, candidateId, { referred_by: referredBy });
    setCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, referred_by: data.referred_by } : c)));
  };

  const handleManualAdd = async (payload) => {
    const { data } = await candidatesApi.create(jobId, payload);
    mergeCandidates([data]);
  };

  const handleDeleteCandidate = async (candidateId) => {
    if (!window.confirm('האם למחוק מועמד זה?')) return;
    try {
      await candidatesApi.remove(jobId, candidateId);
      setCandidates((prev) => prev.filter((c) => c.id !== candidateId));
      setJob((prev) => (prev ? { ...prev, candidate_count: Math.max(0, (prev.candidate_count || 1) - 1) } : prev));
    } catch {
      alert('שגיאה במחיקת המועמד');
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      saveDownload(await jobsApi.exportExcel(jobId), 'candidates.xlsx');
    } catch {
      alert('שגיאה בייצוא לאקסל');
    } finally {
      setExporting(false);
    }
  };

  // Show the saved candidates immediately; UploadBox then calls refreshCandidates
  // (also after errors/timeouts, when some files may have been saved anyway)
  const handleUploadComplete = (newCandidates) => mergeCandidates(newCandidates);

  if (loading) return <LoadingPage />;
  if (fetchError) return <ErrorPage onRetry={fetchAll} />;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Back button */}
        <button
          onClick={() => navigate('/jobs')}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ArrowRight className="h-4 w-4" />
          חזרה לכל המשרות
        </button>

        {/* ── Job header card ── */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          {/* Top row */}
          <div className="flex items-start justify-between gap-4 mb-5">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-semibold tracking-wide ${
                    job.interview_type === 'מרוכז'
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}
                >
                  {job.interview_type}
                </span>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 leading-tight truncate">
                {job.job_title}
              </h1>
              {job.description && (
                <p className="text-gray-500 text-sm mt-2 leading-relaxed max-w-2xl">
                  {job.description}
                </p>
              )}
            </div>

            {/* Export button */}
            <button
              type="button"
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-2 border border-gray-200 text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-xl text-sm font-medium transition-colors flex-shrink-0 disabled:opacity-60 disabled:cursor-wait"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              ייצוא Excel
            </button>
          </div>

          {/* Meta grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 pt-5 border-t border-gray-100">
            <MetaItem icon={MapPin} label="מיקום ראיון" value={job.interview_location} />
            <MetaItem
              icon={Users}
              label="מראיינים"
              value={job.interviewers?.join(', ')}
            />
            <MetaItem
              icon={Mail}
              label="מייל מראיינים"
              value={job.interviewer_emails?.join(', ')}
            />
            <MetaItem
              icon={Calendar}
              label="תאריך פתיחה"
              value={formatDate(job.created_at)}
            />
          </div>
        </div>

        {/* ── Upload box ── */}
        <SectionCard
          title="העלאת קורות חיים"
          subtitle="PDF, Word (.docx), תמונה (PNG, JPG) — מספר קבצים מעובדים במקביל"
          action={
            <button
              type="button"
              onClick={() => setShowManualAdd(true)}
              className="flex items-center gap-2 border border-blue-200 text-blue-700 hover:bg-blue-50 px-3.5 py-2 rounded-xl text-sm font-medium transition-colors flex-shrink-0"
            >
              <UserPlus className="h-4 w-4" />
              הוספת מועמד ידנית
            </button>
          }
        >
          <div className="p-6">
            <UploadBox
              onUpload={(files, onProgress, fields) => candidatesApi.upload(jobId, files, onProgress, fields)}
              onUploadComplete={handleUploadComplete}
              onUploadFinished={refreshCandidates}
            />
          </div>
        </SectionCard>

        {/* ── AI suggestions from the talent pool ── */}
        <SectionCard
          title="הצעות מועמדים מהמאגר"
          subtitle="התאמה חכמה בין מאגר קורות החיים לדרישות המשרה"
        >
          <PoolSuggestions key={jobId} jobId={jobId} onAssigned={(c) => mergeCandidates([c])} />
        </SectionCard>

        {/* ── Candidates table ── */}
        <SectionCard
          title="מועמדים"
          subtitle={candidatesSubtitle(candidates)}
          action={
            refreshing && (
              <span className="flex items-center gap-1.5 text-xs text-gray-400" role="status">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                מרענן…
              </span>
            )
          }
        >
          <CandidatesTable
            candidates={candidates}
            job={job}
            onStatusChange={handleStatusChange}
            onToggleComplete={handleToggleComplete}
            onReferrerChange={handleReferrerChange}
            onDelete={handleDeleteCandidate}
          />
        </SectionCard>
      </main>

      {showManualAdd && (
        <CandidateFormModal
          title="הוספת מועמד ידנית"
          subtitle={job.job_title}
          withStatus
          onSubmit={handleManualAdd}
          onClose={() => setShowManualAdd(false)}
        />
      )}
    </div>
  );
}
