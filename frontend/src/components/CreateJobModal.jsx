import { useEffect, useRef, useState } from 'react';
import { Plus, X } from 'lucide-react';
import { jobsApi } from '../api/client';

const INITIAL_FORM = {
  job_title: '',
  description: '',
  interviewers: [''],
  interview_location: '',
  interviewer_emails: [''],
  interview_type: 'יחידני',
};

function DynamicList({ label, values, placeholder, onChange }) {
  const update = (i, v) => onChange(values.map((x, idx) => (idx === i ? v : x)));
  const remove = (i) => onChange(values.filter((_, idx) => idx !== i));
  const add = () => onChange([...values, '']);

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <div className="flex flex-col gap-2">
        {values.map((val, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={val}
              placeholder={placeholder}
              onChange={(e) => update(i, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (i === values.length - 1) add();
                }
              }}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
            {values.length > 1 && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="text-gray-400 hover:text-red-500 transition-colors p-1"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={add}
          className="flex items-center gap-1 text-blue-600 hover:text-blue-700 text-sm font-medium w-fit mt-1"
        >
          <Plus className="h-3.5 w-3.5" />
          הוסף
        </button>
      </div>
    </div>
  );
}

export default function CreateJobModal({ onClose, onCreated }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const titleRef = useRef(null);

  useEffect(() => {
    titleRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const set = (key, value) => setForm((p) => ({ ...p, [key]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.job_title.trim()) { setError('שם המשרה הוא שדה חובה'); return; }
    setError('');
    setLoading(true);
    try {
      const payload = {
        ...form,
        interviewers: form.interviewers.filter(Boolean),
        interviewer_emails: form.interviewer_emails.filter(Boolean),
      };
      const { data } = await jobsApi.create(payload);
      onCreated(data);
      onClose();
    } catch {
      setError('שגיאה ביצירת המשרה. נסה שנית.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[92vh] flex flex-col shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">משרה חדשה</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal body */}
        <form
          onSubmit={handleSubmit}
          className="overflow-y-auto flex flex-col gap-5 px-6 py-5"
        >
          {/* Job title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              שם המשרה <span className="text-red-500">*</span>
            </label>
            <input
              ref={titleRef}
              type="text"
              value={form.job_title}
              onChange={(e) => set('job_title', e.target.value)}
              placeholder="לדוגמה: מנהל מוצר בכיר"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">תיאור המשרה</label>
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              placeholder="תיאור קצר של תפקיד וצוות..."
              rows={3}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition resize-none"
            />
          </div>

          {/* Interview type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">סוג ראיון</label>
            <div className="flex gap-3">
              {['יחידני', 'מרוכז'].map((type) => (
                <label
                  key={type}
                  className={`flex-1 flex items-center justify-center gap-2 border rounded-xl py-2.5 cursor-pointer transition-all text-sm font-medium ${
                    form.interview_type === type
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  <input
                    type="radio"
                    name="interview_type"
                    value={type}
                    checked={form.interview_type === type}
                    onChange={() => set('interview_type', type)}
                    className="hidden"
                  />
                  {type}
                </label>
              ))}
            </div>
          </div>

          {/* Location */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">מיקום ראיון</label>
            <input
              type="text"
              value={form.interview_location}
              onChange={(e) => set('interview_location', e.target.value)}
              placeholder="לדוגמה: תל אביב, משרדי החברה"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          {/* Interviewers */}
          <DynamicList
            label="מראיינים"
            values={form.interviewers}
            placeholder="שם המראיין"
            onChange={(v) => set('interviewers', v)}
          />

          {/* Interviewer emails */}
          <DynamicList
            label="כתובות מייל מראיינים"
            values={form.interviewer_emails}
            placeholder="email@company.com"
            onChange={(v) => set('interviewer_emails', v)}
          />

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </form>

        {/* Modal footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-gray-100">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 border border-gray-200 text-gray-600 rounded-xl py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            ביטול
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
          >
            {loading ? 'יוצר...' : 'צור משרה'}
          </button>
        </div>
      </div>
    </div>
  );
}
