import { useState } from 'react';
import { apiErrorMessage, budgetsApi } from '../../api/client';
import Modal, { secondaryButtonClass } from '../Modal';
import { MoneyInput, amberInput, amberPrimary } from './budgetUi';

/* Create a year's budget (budget = null) or edit an existing one */
export default function BudgetYearModal({ budget, suggestedYear, onClose, onSaved }) {
  const isEdit = Boolean(budget);
  const [year, setYear] = useState(String(budget?.year ?? suggestedYear));
  const [total, setTotal] = useState(budget ? String(budget.total_budget) : '');
  const [notes, setNotes] = useState(budget?.notes ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const y = Number(year);
    const amount = total === '' ? 0 : Number(total);
    if (!isEdit && (!Number.isInteger(y) || y < 2000 || y > 2100)) {
      setError('שנה לא תקינה (2000–2100)');
      return;
    }
    if (!Number.isFinite(amount) || amount < 0) {
      setError('סכום התקציב חייב להיות מספר חיובי');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = isEdit
        ? await budgetsApi.update(budget.year, { total_budget: amount, notes: notes.trim() })
        : await budgetsApi.create({ year: y, total_budget: amount, notes: notes.trim() });
      onSaved(data);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירת התקציב'));
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? `עריכת תקציב ${budget.year}` : 'תקציב שנתי חדש'}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>ביטול</button>
          <button type="button" onClick={handleSubmit} disabled={saving} className={amberPrimary}>
            {saving ? 'שומר...' : isEdit ? 'שמירה' : 'יצירת תקציב'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {!isEdit && (
          <label className="block">
            <span className="block text-sm font-medium text-gray-700 mb-1.5">שנה <span className="text-red-500">*</span></span>
            <input
              type="number"
              min="2000"
              max="2100"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              autoFocus
              className={amberInput}
            />
          </label>
        )}
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">תקציב שנתי כולל (₪)</span>
          <MoneyInput value={total} onChange={setTotal} autoFocus={isEdit} />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">הערות</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className={`${amberInput} resize-none`} />
        </label>
        {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
        <button type="submit" className="hidden" />
      </form>
    </Modal>
  );
}
