import { useEffect, useState } from 'react';
import { Briefcase, Plus, RefreshCw, Users } from 'lucide-react';
import { jobsApi } from '../api/client';
import CreateJobModal from '../components/CreateJobModal';
import JobCard from '../components/JobCard';
import Navbar from '../components/Navbar';

/* ── Stat card ── */
function StatCard({ title, value, icon: Icon, colorClass }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
      <div className={`rounded-xl p-3 ${colorClass}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500 font-medium">{title}</p>
        <p className="text-2xl font-bold text-gray-900 leading-tight">{value}</p>
      </div>
    </div>
  );
}

/* ── Skeleton card ── */
function SkeletonCard() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 animate-pulse space-y-4">
      <div className="flex justify-between">
        <div className="h-5 bg-gray-100 rounded-full w-16" />
        <div className="h-4 w-4 bg-gray-100 rounded" />
      </div>
      <div className="h-5 bg-gray-200 rounded w-3/4" />
      <div className="space-y-2">
        <div className="h-3 bg-gray-100 rounded w-full" />
        <div className="h-3 bg-gray-100 rounded w-5/6" />
      </div>
      <div className="flex justify-between items-center pt-2 border-t border-gray-100">
        <div className="h-7 w-14 bg-gray-100 rounded-full" />
        <div className="h-4 w-10 bg-gray-100 rounded" />
      </div>
    </div>
  );
}

/* ── Empty state ── */
function EmptyState({ onAdd }) {
  return (
    <div className="flex flex-col items-center justify-center py-28 text-center gap-5">
      <div className="bg-blue-50 rounded-full p-6">
        <Briefcase className="h-10 w-10 text-blue-400" />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-gray-700">אין משרות פתוחות עדיין</h3>
        <p className="text-sm text-gray-400 mt-1 max-w-xs">
          צור את המשרה הראשונה כדי להתחיל לנהל מועמדים
        </p>
      </div>
      <button
        onClick={onAdd}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-semibold text-sm transition-colors shadow-sm"
      >
        <Plus className="h-4 w-4" />
        צור משרה חדשה
      </button>
    </div>
  );
}

/* ── Error state ── */
function ErrorState({ onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <p className="text-gray-500">שגיאה בטעינת המשרות</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
      >
        <RefreshCw className="h-4 w-4" />
        נסה שנית
      </button>
    </div>
  );
}

/* ── Jobs dashboard ── */
export default function JobsDashboard() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const fetchJobs = async () => {
    setLoading(true);
    setError(false);
    try {
      const { data } = await jobsApi.list();
      setJobs(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleDelete = async (id) => {
    if (!window.confirm('האם למחוק את המשרה וכל המועמדים שלה?')) return;
    try {
      await jobsApi.remove(id);
      setJobs((prev) => prev.filter((j) => j.id !== id));
    } catch {
      alert('שגיאה במחיקת המשרה');
    }
  };

  const totalCandidates = jobs.reduce((s, j) => s + (j.candidate_count ?? 0), 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">משרות פתוחות</h1>
            <p className="text-sm text-gray-400 mt-1">ניהול תהליכי גיוס ומועמדים</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            משרה חדשה
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          <StatCard
            title="סה״כ משרות"
            value={jobs.length}
            icon={Briefcase}
            colorClass="bg-blue-50 text-blue-500"
          />
          <StatCard
            title="סה״כ מועמדים"
            value={totalCandidates}
            icon={Users}
            colorClass="bg-violet-50 text-violet-500"
          />
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : error ? (
          <ErrorState onRetry={fetchJobs} />
        ) : jobs.length === 0 ? (
          <EmptyState onAdd={() => setShowModal(true)} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} onDelete={handleDelete} />
            ))}
          </div>
        )}
      </main>

      {showModal && (
        <CreateJobModal
          onClose={() => setShowModal(false)}
          onCreated={(newJob) => setJobs((prev) => [newJob, ...prev])}
        />
      )}
    </div>
  );
}
