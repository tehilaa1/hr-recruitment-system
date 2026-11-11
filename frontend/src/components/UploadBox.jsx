import { useRef, useState } from 'react';
import { CheckCircle, Copy, FileText, Image, Loader2, Upload, X, XCircle } from 'lucide-react';
import { candidatesApi } from '../api/client';

const ACCEPTED = '.pdf,.docx,.doc,.png,.jpg,.jpeg';
const ACCEPT_LABEL = 'PDF, Word (.docx), תמונה (PNG, JPG)';

const fileIcon = (name) => {
  const ext = name.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return Image;
  return FileText;
};

const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};

export default function UploadBox({ jobId, onUploadComplete }) {
  const [files, setFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState(null);
  const dragCounter = useRef(0);
  const inputRef = useRef(null);

  const addFiles = (incoming) => {
    const valid = Array.from(incoming).filter((f) => {
      const ext = f.name.split('.').pop().toLowerCase();
      return ['pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg'].includes(ext);
    });
    setFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name + f.size));
      return [...prev, ...valid.filter((f) => !existing.has(f.name + f.size))];
    });
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    dragCounter.current++;
    setIsDragging(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    dragCounter.current--;
    if (dragCounter.current === 0) setIsDragging(false);
  };
  const handleDragOver = (e) => e.preventDefault();
  const handleDrop = (e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const removeFile = (i) => setFiles((prev) => prev.filter((_, idx) => idx !== i));

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    try {
      const { data } = await candidatesApi.upload(jobId, files);
      setResults(data);
      setFiles([]);
      const successful = data.filter((r) => r.success && r.candidate).map((r) => r.candidate);
      onUploadComplete(successful);
    } catch {
      setResults([{ file_name: 'שגיאה', success: false, error: 'שגיאה בהעלאה. נסה שנית.' }]);
    } finally {
      setUploading(false);
    }
  };

  const reset = () => {
    setResults(null);
    setFiles([]);
  };

  /* ── Results view ── */
  if (results) {
    const successCount = results.filter((r) => r.success).length;
    const duplicateCount = results.filter((r) => r.duplicate).length;
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-gray-700">
            {successCount} מתוך {results.length} קבצים עובדו בהצלחה
            {duplicateCount > 0 && (
              <span className="text-amber-600">
                {' '}· {duplicateCount} {duplicateCount === 1 ? 'מועמד כפול דולג' : 'מועמדים כפולים דולגו'}
              </span>
            )}
          </p>
          <button
            onClick={reset}
            className="text-sm text-blue-600 hover:underline font-medium"
          >
            העלה עוד
          </button>
        </div>
        <div className="flex flex-col gap-2 max-h-64 overflow-y-auto">
          {results.map((r, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 p-3 rounded-xl text-sm border ${
                r.success
                  ? 'bg-emerald-50 border-emerald-200'
                  : r.duplicate
                    ? 'bg-amber-50 border-amber-200'
                    : 'bg-red-50 border-red-200'
              }`}
            >
              {r.success ? (
                <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
              ) : r.duplicate ? (
                <Copy className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
              )}
              <div className="min-w-0">
                <p className="font-medium text-gray-800 truncate">{r.file_name}</p>
                {r.success && r.candidate ? (
                  <p className="text-gray-500 text-xs mt-0.5">
                    {[r.candidate.full_name, r.candidate.family_name].filter(Boolean).join(' ')}
                    {r.candidate.profession ? ` — ${r.candidate.profession}` : ''}
                  </p>
                ) : (
                  <p className={`text-xs mt-0.5 ${r.duplicate ? 'text-amber-700' : 'text-red-600'}`}>
                    {r.error}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ── Drop zone / file list ── */
  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
          transition-all duration-200
          ${isDragging
            ? 'border-blue-400 bg-blue-50 scale-[1.01]'
            : 'border-gray-200 bg-gray-50 hover:border-blue-300 hover:bg-blue-50/40'}
          ${uploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
          className="hidden"
        />
        <div className="flex flex-col items-center gap-3 pointer-events-none">
          <div className={`p-3 rounded-full ${isDragging ? 'bg-blue-100' : 'bg-gray-100'}`}>
            <Upload className={`h-6 w-6 ${isDragging ? 'text-blue-500' : 'text-gray-400'}`} />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700">
              {isDragging ? 'שחרר כאן להעלאה' : 'גרור קבצים לכאן'}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              או{' '}
              <span className="text-blue-600 font-medium">לחץ לבחירת קבצים</span>
            </p>
          </div>
          <p className="text-xs text-gray-400">{ACCEPT_LABEL}</p>
        </div>
      </div>

      {/* Selected files */}
      {files.length > 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-100 divide-y divide-gray-100 overflow-hidden">
          {files.map((file, i) => {
            const Icon = fileIcon(file.name);
            return (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                <Icon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                <span className="flex-1 text-sm text-gray-700 truncate">{file.name}</span>
                <span className="text-xs text-gray-400 flex-shrink-0">{formatBytes(file.size)}</span>
                <button
                  onClick={() => removeFile(i)}
                  className="text-gray-300 hover:text-red-500 transition-colors p-0.5 flex-shrink-0"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Upload button */}
      {files.length > 0 && (
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
        >
          {uploading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              מעבד קורות חיים...
            </>
          ) : (
            <>
              <Upload className="h-4 w-4" />
              העלה {files.length} {files.length === 1 ? 'קובץ' : 'קבצים'}
            </>
          )}
        </button>
      )}
    </div>
  );
}
