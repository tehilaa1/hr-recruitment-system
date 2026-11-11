import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { RECRUITMENT_STATUSES, STATUS_STYLES } from '../constants/statuses';

export default function StatusSelect({ value, onChange, disabled = false }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);
  const style = STATUS_STYLES[value] ?? STATUS_STYLES['לא טופל'];

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const keyHandler = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('keydown', keyHandler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('keydown', keyHandler);
    };
  }, [open]);

  const handleSelect = (status) => {
    onChange(status);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((p) => !p)}
        className={`
          flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium
          transition-opacity select-none
          ${style.badge}
          ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:opacity-80'}
        `}
      >
        <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${style.dot}`} />
        <span className="whitespace-nowrap">{value}</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 min-w-[160px] overflow-hidden animate-fade-in">
          {RECRUITMENT_STATUSES.map((status) => {
            const s = STATUS_STYLES[status];
            return (
              <button
                key={status}
                type="button"
                onClick={() => handleSelect(status)}
                className={`
                  w-full flex items-center gap-2 px-3 py-2.5 text-sm text-right
                  transition-colors
                  ${status === value ? 'bg-gray-50 font-semibold' : 'hover:bg-gray-50'}
                `}
              >
                <span className={`h-2 w-2 rounded-full flex-shrink-0 ${s.dot}`} />
                <span className="text-gray-800">{status}</span>
                {status === value && (
                  <span className="mr-auto text-blue-500 text-xs">✓</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
