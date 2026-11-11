import { Calendar, ChevronLeft, MapPin, Trash2, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('he-IL', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });

export default function JobCard({ job, onDelete }) {
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-all duration-200 flex flex-col p-6 gap-4 group">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <span
            className={`inline-block mb-2 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide ${
              job.interview_type === 'מרוכז'
                ? 'bg-purple-100 text-purple-700'
                : 'bg-blue-100 text-blue-700'
            }`}
          >
            {job.interview_type}
          </span>
          <h3 className="text-base font-bold text-gray-900 leading-snug truncate">{job.job_title}</h3>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(job.id);
          }}
          className="text-gray-300 hover:text-red-500 transition-colors p-1 opacity-0 group-hover:opacity-100 flex-shrink-0"
          title="מחק משרה"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {/* Description */}
      {job.description && (
        <p className="text-sm text-gray-500 leading-relaxed line-clamp-2">{job.description}</p>
      )}

      {/* Meta */}
      <div className="flex flex-col gap-2 text-sm text-gray-500 flex-1">
        {job.interview_location && (
          <div className="flex items-center gap-2">
            <MapPin className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
            <span className="truncate">{job.interview_location}</span>
          </div>
        )}
        {job.interviewers?.length > 0 && (
          <div className="flex items-center gap-2">
            <Users className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
            <span className="truncate">{job.interviewers.join(', ')}</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <Calendar className="h-3.5 w-3.5 flex-shrink-0 text-gray-400" />
          <span>{formatDate(job.created_at)}</span>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="flex items-center gap-2">
          <div className="bg-blue-50 text-blue-600 rounded-full h-7 px-2.5 flex items-center justify-center text-xs font-bold">
            {job.candidate_count ?? 0}
          </div>
          <span className="text-xs text-gray-400">מועמדים</span>
        </div>
        <button
          onClick={() => navigate(`/jobs/${job.id}`)}
          className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-sm font-semibold transition-colors"
        >
          פתח
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
