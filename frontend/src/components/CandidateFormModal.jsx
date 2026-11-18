import { useEffect, useRef, useState } from 'react';
import { apiErrorMessage } from '../api/client';
import { REFERRER_LABEL } from '../constants/referrals';
import { RECRUITMENT_STATUSES } from '../constants/statuses';
import Modal, { secondaryButtonClass } from './Modal';
import { ReferrerInput, rememberReferrer } from './ReferrerInput';

const INPUT =
  'w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition';

const EMPTY = {
  full_name: '',
  family_name: '',
  phone: '',
  email: '',
  address: '',
  profession: '',
  years_of_experience: '',
  referred_by: '',
  recruitment_status: RECRUITMENT_STATUSES[0],
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function Field({ label, required, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-sm font-medium text-gray-700 mb-1.5">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
    </label>
  );
}

/*
 * Manual candidate entry (no CV file).
 * onSubmit(payload) must return a promise; its rejection (e.g. 409 duplicate)
 * is shown inside the form. `withStatus` adds the initial recruitment status.
 */
export default function CandidateFormModal({ title, subtitle, withStatus = false, onSubmit, onClose }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const firstRef = useRef(null);

  useEffect(() => { firstRef.current?.focus(); }, []);

  const set = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving) return;
    if (!form.full_name.trim()) { setError('שם פרטי הוא שדה חובה'); return; }
    if (form.email.trim() && !EMAIL_RE.test(form.email.trim())) {
      setError('כתובת המייל אינה תקינה');
      return;
    }
    const years = form.years_of_experience === '' ? 0 : Number(form.years_of_experience);
    if (!Number.isInteger(years) || years < 0 || years > 70) {
      setError('שנות ניסיון חייבות להיות מספר שלם בין 0 ל-70');
      return;
    }

    const { recruitment_status, ...person } = form;
    const payload = {
      ...Object.fromEntries(Object.entries(person).map(([k, v]) => [k, String(v).trim()])),
      years_of_experience: years,
      ...(withStatus ? { recruitment_status } : {}),
    };

    setError('');
    setSaving(true);
    try {
      await onSubmit(payload);
      rememberReferrer(payload.referred_by);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירת המועמד. נסה שנית.'));
      setSaving(false);
    }
  };

  return (
    <Modal
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            ביטול
          </button>
          <button
            type="submit"
            form="candidate-form"
            disabled={saving}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
          >
            {saving ? 'שומר...' : 'הוספת מועמד'}
          </button>
        </>
      }
    >
      <form id="candidate-form" onSubmit={handleSubmit} className="grid grid-cols-2 gap-4" noValidate>
        <Field label="שם פרטי" required>
          <input ref={firstRef} value={form.full_name} onChange={set('full_name')} className={INPUT} />
        </Field>
        <Field label="שם משפחה">
          <input value={form.family_name} onChange={set('family_name')} className={INPUT} />
        </Field>
        <Field label="טלפון">
          <input type="tel" dir="ltr" value={form.phone} onChange={set('phone')} placeholder="050-0000000" className={`${INPUT} text-right`} />
        </Field>
        <Field label="מייל">
          <input type="email" dir="ltr" value={form.email} onChange={set('email')} placeholder="name@example.com" className={`${INPUT} text-right`} />
        </Field>
        <Field label="כתובת מגורים" className="col-span-2">
          <input value={form.address} onChange={set('address')} className={INPUT} />
        </Field>
        <Field label="מקצוע">
          <input value={form.profession} onChange={set('profession')} className={INPUT} />
        </Field>
        <Field label="שנות ניסיון">
          <input
            type="number"
            min="0"
            max="70"
            step="1"
            value={form.years_of_experience}
            onChange={set('years_of_experience')}
            placeholder="0"
            className={INPUT}
          />
        </Field>
        <Field label={`${REFERRER_LABEL} (חבר מביא חבר)`} className="col-span-2">
          <ReferrerInput
            value={form.referred_by}
            onChange={(v) => setForm((p) => ({ ...p, referred_by: v }))}
            className={INPUT}
          />
        </Field>
        {withStatus && (
          <Field label="סטטוס התחלתי" className="col-span-2">
            <select value={form.recruitment_status} onChange={set('recruitment_status')} className={INPUT}>
              {RECRUITMENT_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </Field>
        )}

        {error && (
          <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}
