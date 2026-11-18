import { forwardRef, useEffect, useId, useRef, useState } from 'react';
import { Check, Loader2, Pencil, UserPlus, X } from 'lucide-react';
import { apiErrorMessage, searchApi } from '../api/client';
import { REFERRER_LABEL, REFERRER_MAX_LENGTH, cleanReferrer } from '../constants/referrals';

/* Names already used as referrers, fetched once per page load and shared by every input */
let suggestionsPromise = null;
function loadSuggestions() {
  suggestionsPromise ??= searchApi
    .referrers()
    .then(({ data }) => data)
    .catch(() => {
      suggestionsPromise = null; // retry next time
      return [];
    });
  return suggestionsPromise;
}

/* A newly saved name becomes a suggestion everywhere without refetching */
export function rememberReferrer(name) {
  const clean = cleanReferrer(name);
  if (!clean) return;
  suggestionsPromise = (suggestionsPromise ?? Promise.resolve([])).then((list) =>
    list.some((n) => n.toLowerCase() === clean.toLowerCase()) ? list : [clean, ...list]
  );
}

function useSuggestions() {
  const [names, setNames] = useState([]);
  useEffect(() => {
    let alive = true;
    loadSuggestions().then((list) => alive && setNames(list));
    return () => { alive = false; };
  }, []);
  return names;
}

/* Free-text referrer field with autocomplete from names used before */
export const ReferrerInput = forwardRef(function ReferrerInput(
  { value, onChange, className = '', placeholder = 'שם העובד/ת שהמליצ/ה (חבר מביא חבר)', ...rest },
  ref
) {
  const listId = useId();
  const names = useSuggestions();
  return (
    <>
      <input
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        list={listId}
        maxLength={REFERRER_MAX_LENGTH}
        placeholder={placeholder}
        autoComplete="off"
        className={className}
        {...rest}
      />
      <datalist id={listId}>
        {names.map((n) => <option key={n} value={n} />)}
      </datalist>
    </>
  );
});

/*
 * Table cell: shows the referrer; click to edit inline (Enter / ✓ saves, Esc cancels).
 * onSave(newValue) must return a promise; on failure the old value stays.
 */
export function ReferrerCell({ value, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const start = () => { setDraft(value || ''); setEditing(true); };
  const cancel = () => setEditing(false);
  const save = async () => {
    const next = cleanReferrer(draft);
    if (next === (value || '')) { setEditing(false); return; }
    setSaving(true);
    try {
      await onSave(next);
      rememberReferrer(next);
      setEditing(false);
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה בשמירת הממליץ/ה'));
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1 min-w-[180px]">
        <ReferrerInput
          ref={inputRef}
          value={draft}
          onChange={setDraft}
          placeholder="שם הממליץ/ה"
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); save(); }
            if (e.key === 'Escape') { e.stopPropagation(); cancel(); }
          }}
          disabled={saving}
          className="w-full border border-gray-200 rounded-md px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-violet-400"
        />
        <button type="button" onClick={save} disabled={saving} className="p-1 rounded text-emerald-600 hover:bg-emerald-50" title="שמירה">
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
        </button>
        <button type="button" onClick={cancel} disabled={saving} className="p-1 rounded text-gray-400 hover:bg-gray-100" title="ביטול">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return value ? (
    <button
      type="button"
      onClick={start}
      title={`${REFERRER_LABEL}: ${value} – לחצו לעריכה`}
      className="group/ref inline-flex items-center gap-1 max-w-[170px] rounded-full bg-violet-50 border border-violet-100 px-2 py-0.5 text-xs text-violet-700 hover:bg-violet-100"
    >
      <UserPlus className="h-3 w-3 flex-shrink-0" />
      <span className="truncate">{value}</span>
      <Pencil className="h-3 w-3 flex-shrink-0 opacity-0 group-hover/ref:opacity-60" />
    </button>
  ) : (
    <button
      type="button"
      onClick={start}
      title={`הוספת ${REFERRER_LABEL}`}
      className="text-gray-300 hover:text-violet-600 text-xs px-1 rounded"
    >
      —<span className="sr-only">הוספת {REFERRER_LABEL}</span>
    </button>
  );
}
