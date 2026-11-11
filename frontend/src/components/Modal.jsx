import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

/* Shared modal shell: backdrop click / Escape closes, header + scrollable body + optional footer */
export default function Modal({ title, subtitle, onClose, footer, maxWidth = 'max-w-lg', children }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      // With stacked modals, only the topmost one closes
      const dialogs = document.querySelectorAll('[role="dialog"]');
      if (dialogs[dialogs.length - 1] === dialogRef.current) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`bg-white rounded-2xl w-full ${maxWidth} max-h-[92vh] flex flex-col shadow-2xl animate-fade-in`}
      >
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-gray-100">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900 truncate">{title}</h2>
            {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded-lg hover:bg-gray-100"
            title="סגור"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex gap-3 px-6 py-4 border-t border-gray-100">{footer}</div>}
      </div>
    </div>
  );
}

export const inputClass =
  'w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-pink-400 focus:border-transparent transition';

export const secondaryButtonClass =
  'flex-1 border border-gray-200 text-gray-600 rounded-xl py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors';

export const primaryButtonClass =
  'flex-1 bg-pink-600 hover:bg-pink-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors';
