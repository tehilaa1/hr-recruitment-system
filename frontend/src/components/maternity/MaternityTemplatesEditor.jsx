import { useRef, useState } from 'react';
import { Eye, RotateCcw } from 'lucide-react';
import {
  DEFAULT_TEMPLATES,
  MESSAGE_TYPES,
  TEMPLATE_PLACEHOLDERS,
  renderTemplate,
} from '../../utils/maternityTemplates';
import { inputClass } from '../Modal';

/* Example record for the live preview */
const SAMPLE_RECORD = {
  name: 'דנה לוי',
  phone: '050-1234567',
  company_email: 'dana@company.com',
  birth_date: '2026-03-01',
  baby_gender: 'בת',
  expected_return_date: '2026-06-14',
  gift_address: 'הרצל 10, תל אביב',
  delivery_contact_name: 'יוסי לוי',
  delivery_contact_phone: '052-7654321',
  attendance_updated: true,
  notes: '',
};

const GROUPS = [
  ...MESSAGE_TYPES.map((t) => ({
    label: t.label,
    description: t.description,
    fields: [
      { key: `${t.key}_subject`, label: 'נושא', rows: 1 },
      { key: `${t.key}_body`, label: 'תוכן', rows: t.key === 'full' ? 14 : 8 },
    ],
  })),
  {
    label: 'הודעת ברכה ל-Teams',
    description: 'מועתקת ומודבקת בערוץ הכללי',
    fields: [{ key: 'teams_announcement', label: 'תוכן', rows: 7 }],
  },
];

/* {placeholders} the backend would reject */
export function unknownPlaceholders(templates) {
  const known = new Set(Object.keys(TEMPLATE_PLACEHOLDERS));
  const found = Object.values(templates).flatMap((t) =>
    [...String(t ?? '').matchAll(/\{([^{}\s]*)\}/g)].map((m) => m[1])
  );
  return [...new Set(found.filter((k) => !known.has(k)))];
}

/*
 * Controlled editor for the message templates.
 * `value` holds the *effective* text of every template (custom or default).
 */
export default function MaternityTemplatesEditor({ value, onChange }) {
  const [focused, setFocused] = useState(GROUPS[0].fields[1].key);
  const refs = useRef({});

  const set = (key, text) => onChange({ ...value, [key]: text });

  /* Insert "{placeholder}" at the cursor of the last focused field */
  const insert = (placeholder) => {
    const el = refs.current[focused];
    const text = value[focused] ?? '';
    const token = `{${placeholder}}`;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? text.length;
    set(focused, text.slice(0, start) + token + text.slice(end));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const restore = (group) =>
    onChange({
      ...value,
      ...Object.fromEntries(group.fields.map((f) => [f.key, DEFAULT_TEMPLATES[f.key]])),
    });

  return (
    <div className="space-y-5">
      {/* Placeholder legend */}
      <div className="rounded-xl bg-gray-50 border border-gray-100 p-3">
        <p className="text-xs text-gray-500 mb-2">
          לחיצה על שדה מוסיפה אותו במיקום הסמן. בעת יצירת ההודעה הוא יוחלף בפרטי העובדת (שדה ריק יוצג כ-״—״).
        </p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(TEMPLATE_PLACEHOLDERS).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onMouseDown={(e) => e.preventDefault()} // keep the textarea's cursor
              onClick={() => insert(key)}
              title={`{${key}}`}
              className="px-2 py-1 rounded-lg bg-white border border-gray-200 text-xs text-gray-700 hover:border-pink-300 hover:text-pink-700 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {GROUPS.map((group) => {
        const isDefault = group.fields.every((f) => value[f.key] === DEFAULT_TEMPLATES[f.key]);
        return (
          <section key={group.label} className="border border-gray-100 rounded-2xl p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-bold text-gray-900">{group.label}</h4>
                <p className="text-xs text-gray-400">{group.description}</p>
              </div>
              {isDefault ? (
                <span className="text-[11px] text-gray-400 whitespace-nowrap">ברירת מחדל</span>
              ) : (
                <button
                  type="button"
                  onClick={() => restore(group)}
                  className="flex items-center gap-1 text-xs text-gray-500 hover:text-pink-600 whitespace-nowrap"
                >
                  <RotateCcw className="h-3 w-3" />
                  שחזור ברירת מחדל
                </button>
              )}
            </div>

            {group.fields.map((f) => {
              const common = {
                ref: (el) => { refs.current[f.key] = el; },
                value: value[f.key] ?? '',
                onChange: (e) => set(f.key, e.target.value),
                onFocus: () => setFocused(f.key),
                'aria-label': `${group.label} – ${f.label}`,
                className: `${inputClass} ${focused === f.key ? 'ring-1 ring-pink-200' : ''}`,
              };
              return (
                <div key={f.key}>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{f.label}</label>
                  {f.rows === 1 ? (
                    <input {...common} />
                  ) : (
                    <textarea {...common} rows={f.rows} className={`${common.className} resize-y leading-relaxed`} />
                  )}
                </div>
              );
            })}

            {group.fields.some((f) => f.key === focused) && (
              <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50/60 p-3">
                <p className="flex items-center gap-1 text-[11px] font-medium text-gray-400 mb-1.5">
                  <Eye className="h-3 w-3" /> תצוגה מקדימה (עם פרטים לדוגמה)
                </p>
                <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                  {renderTemplate(value[focused], SAMPLE_RECORD)}
                </p>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
