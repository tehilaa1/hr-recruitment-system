import { EVENT_STATUS_STYLES } from '../../constants/budgets';

export const amberInput =
  'w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent transition';

export const amberPrimary =
  'flex-1 bg-amber-500 hover:bg-amber-600 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors';

/* Shekel amount input (digits + up to 2 decimals) */
export function MoneyInput({ value, onChange, autoFocus, id }) {
  return (
    <div className="relative">
      <input
        id={id}
        type="number"
        inputMode="decimal"
        min="0"
        step="0.01"
        dir="ltr"
        autoFocus={autoFocus}
        value={value}
        placeholder="0"
        onChange={(e) => onChange(e.target.value)}
        className={`${amberInput} pl-8 text-right`}
      />
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-400 pointer-events-none">₪</span>
    </div>
  );
}

export function EventStatusBadge({ status }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap ${EVENT_STATUS_STYLES[status] ?? EVENT_STATUS_STYLES['מתוכנן']}`}>
      {status}
    </span>
  );
}
