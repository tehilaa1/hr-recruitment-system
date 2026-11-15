import { CheckCircle2, Circle } from 'lucide-react';

/*
 * "סיום טיפול" toggle shared by the candidates and maternity tables.
 * Not done: outline button with `label`. Done: green badge with `doneLabel`;
 * hovering it shows `reopenLabel`, and clicking reopens the record.
 */
export default function CompleteToggle({
  completed,
  disabled,
  onToggle,
  label = 'סיום טיפול',
  doneLabel = 'טופל',
  reopenLabel = 'החזרה לטיפול',
  title = 'סמן שהטיפול הסתיים',
}) {
  return completed ? (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      title={reopenLabel}
      aria-pressed="true"
      className="group/done flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium whitespace-nowrap bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-white hover:text-gray-600 hover:border-gray-200 transition-colors disabled:opacity-50 disabled:cursor-wait"
    >
      <CheckCircle2 className="h-3.5 w-3.5" />
      <span className="group-hover/done:hidden">{doneLabel}</span>
      <span className="hidden group-hover/done:inline">{reopenLabel}</span>
    </button>
  ) : (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      title={title}
      aria-pressed="false"
      className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium whitespace-nowrap border border-gray-200 text-gray-500 hover:border-emerald-300 hover:text-emerald-700 hover:bg-emerald-50 transition-colors disabled:opacity-50 disabled:cursor-wait"
    >
      <Circle className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}
