import { useState } from 'react';
import { apiErrorMessage, maternityApi } from '../../api/client';
import {
  MATERNITY_COLUMNS,
  emptyMaternityRecord,
  toMaternityPayload,
} from '../../constants/maternityColumns';
import Modal, { inputClass, primaryButtonClass, secondaryButtonClass } from '../Modal';

function FieldInput({ field, value, onChange, autoFocus }) {
  const common = {
    id: `mat-${field.key}`,
    placeholder: field.placeholder,
    autoFocus,
    className: inputClass,
  };

  switch (field.type) {
    case 'boolean':
      return (
        <div className="flex gap-2">
          {[
            [true, 'כן'],
            [false, 'לא'],
          ].map(([val, label]) => (
            <button
              key={label}
              type="button"
              onClick={() => onChange(val)}
              className={`flex-1 border rounded-lg py-2 text-sm font-medium transition-colors ${
                Boolean(value) === val
                  ? val
                    ? 'border-emerald-400 bg-emerald-50 text-emerald-700'
                    : 'border-gray-400 bg-gray-50 text-gray-700'
                  : 'border-gray-200 text-gray-500 hover:border-gray-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      );
    case 'textarea':
      return (
        <textarea
          {...common}
          rows={3}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className={`${inputClass} resize-none`}
        />
      );
    default:
      return (
        <input
          {...common}
          type={field.type === 'tel' ? 'tel' : field.type}
          dir={['tel', 'email'].includes(field.type) ? 'ltr' : undefined}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

function Label({ field }) {
  return (
    <label htmlFor={`mat-${field.key}`} className="block text-sm font-medium text-gray-700 mb-1.5">
      {field.label}
      {field.required && <span className="text-red-500"> *</span>}
    </label>
  );
}

/* Add / edit a maternity-leave record. `record` = null for a new one. */
export default function MaternityFormModal({ record, onClose, onSaved }) {
  const isEdit = Boolean(record?.id);
  const [form, setForm] = useState(() => ({ ...emptyMaternityRecord(), ...(record ?? {}) }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (key, value) => setForm((p) => ({ ...p, [key]: value }));

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.name?.trim()) {
      setError('שם הוא שדה חובה');
      return;
    }
    if (
      form.birth_date &&
      form.expected_return_date &&
      form.expected_return_date < form.birth_date
    ) {
      setError('תאריך החזרה המשוער לא יכול להיות לפני תאריך הלידה');
      return;
    }
    setError('');
    setSaving(true);
    try {
      const payload = toMaternityPayload(form);
      const { data } = isEdit
        ? await maternityApi.update(record.id, payload)
        : await maternityApi.create(payload);
      onSaved(data, isEdit);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירה. נסה שנית.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? `עריכת פרטים – ${record.name}` : 'הוספת עובד/ת לחופשת לידה'}
      onClose={onClose}
      maxWidth="max-w-2xl"
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            ביטול
          </button>
          <button type="button" onClick={handleSubmit} disabled={saving} className={primaryButtonClass}>
            {saving ? 'שומר...' : isEdit ? 'שמירת שינויים' : 'הוספה לטבלה'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MATERNITY_COLUMNS.map((col, i) =>
          col.type === 'group' ? (
            <fieldset key={col.key} className="sm:col-span-2">
              <legend className="text-sm font-medium text-gray-700 mb-1.5">{col.label}</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {col.fields.map((f) => (
                  <FieldInput key={f.key} field={f} value={form[f.key]} onChange={(v) => set(f.key, v)} />
                ))}
              </div>
            </fieldset>
          ) : (
            <div key={col.key} className={col.wide ? 'sm:col-span-2' : ''}>
              <Label field={col} />
              <FieldInput
                field={col}
                value={form[col.key]}
                onChange={(v) => set(col.key, v)}
                autoFocus={i === 0}
              />
            </div>
          )
        )}

        {error && (
          <p className="sm:col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        {/* Enables Enter-to-submit */}
        <button type="submit" className="hidden" />
      </form>
    </Modal>
  );
}
