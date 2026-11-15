import { useState } from 'react';
import { apiErrorMessage, budgetsApi } from '../../api/client';
import { COMMON_EVENTS, EVENT_STATUSES, formatIls } from '../../constants/budgets';
import Modal, { secondaryButtonClass } from '../Modal';
import { MoneyInput, amberInput, amberPrimary } from './budgetUi';

const toNumber = (v) => (v === '' || v === null || v === undefined ? 0 : Number(v));

/* Add (event = null) or edit a holiday / event under a year's budget */
export default function BudgetEventModal({ year, event, existingNames = [], onClose, onSaved }) {
  const isEdit = Boolean(event);
  const [form, setForm] = useState(() => ({
    name: event?.name ?? '',
    event_date: event?.event_date ?? '',
    status: event?.status ?? EVENT_STATUSES[0],
    allocated_budget: event ? String(event.allocated_budget ?? 0) : '',
    actual_spent: event ? String(event.actual_spent ?? 0) : '',
    notes: event?.notes ?? '',
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (v) => setForm((p) => ({ ...p, [k]: v?.target ? v.target.value : v }));

  const allocated = toNumber(form.allocated_budget);
  const spent = toNumber(form.actual_spent);
  const variance = allocated - spent;
  const outsideYear = form.event_date && !form.event_date.startsWith(String(year));
  const suggestions = COMMON_EVENTS.filter((n) => !existingNames.includes(n));

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.name.trim()) { setError('שם האירוע הוא שדה חובה'); return; }
    if (![allocated, spent].every((n) => Number.isFinite(n) && n >= 0)) {
      setError('הסכומים חייבים להיות מספרים חיוביים');
      return;
    }
    const payload = {
      name: form.name.trim(),
      event_date: form.event_date || null,
      status: form.status,
      allocated_budget: allocated,
      actual_spent: spent,
      notes: form.notes.trim(),
    };
    setSaving(true);
    setError('');
    try {
      const { data } = isEdit
        ? await budgetsApi.updateEvent(year, event.id, payload)
        : await budgetsApi.createEvent(year, payload);
      onSaved(data, isEdit);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירת האירוע'));
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? `עריכת ${event.name}` : `אירוע חדש – ${year}`}
      onClose={onClose}
      maxWidth="max-w-xl"
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>ביטול</button>
          <button type="button" onClick={handleSubmit} disabled={saving} className={amberPrimary}>
            {saving ? 'שומר...' : isEdit ? 'שמירה' : 'הוספת אירוע'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4" noValidate>
        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">שם החג / האירוע <span className="text-red-500">*</span></span>
          <input value={form.name} onChange={set('name')} autoFocus className={amberInput} placeholder="לדוגמה: ראש השנה" />
        </label>
        {!isEdit && suggestions.length > 0 && (
          <div className="col-span-2 -mt-2 flex flex-wrap gap-1.5">
            {suggestions.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => set('name')(n)}
                className={`px-2 py-0.5 rounded-full text-xs border transition-colors ${
                  form.name === n ? 'bg-amber-100 border-amber-300 text-amber-800' : 'border-gray-200 text-gray-500 hover:border-amber-300 hover:text-amber-700'
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        )}
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">תאריך</span>
          <input type="date" value={form.event_date} onChange={set('event_date')} className={amberInput} />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">סטטוס</span>
          <select value={form.status} onChange={set('status')} className={amberInput}>
            {EVENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {outsideYear && (
          <p className="col-span-2 -mt-2 text-xs text-amber-700">שימו לב: התאריך אינו בשנת {year}.</p>
        )}
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">תקציב מוקצה</span>
          <MoneyInput value={form.allocated_budget} onChange={set('allocated_budget')} />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">הוצאה בפועל</span>
          <MoneyInput value={form.actual_spent} onChange={set('actual_spent')} />
        </label>
        <p className={`col-span-2 -mt-1 text-xs ${variance < 0 ? 'text-red-600' : 'text-gray-500'}`}>
          {variance < 0 ? `חריגה של ${formatIls(-variance)} מהתקציב המוקצה` : `יתרה באירוע: ${formatIls(variance)}`}
        </p>
        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">הערות</span>
          <textarea value={form.notes} onChange={set('notes')} rows={3} className={`${amberInput} resize-none`} />
        </label>
        {error && <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
        <button type="submit" className="hidden" />
      </form>
    </Modal>
  );
}
