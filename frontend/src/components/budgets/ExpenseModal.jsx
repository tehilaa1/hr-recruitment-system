import { useRef, useState } from 'react';
import { Eye, FileText, Image as ImageIcon, Trash2, Upload } from 'lucide-react';
import { apiErrorMessage, budgetsApi, openFileInNewTab } from '../../api/client';
import {
  DEFAULT_EXPENSE_STATUS,
  EXPENSE_STATUSES,
  EXPENSE_STATUS_STYLES,
  INVOICE_ACCEPT,
  formatFileSize,
  formatIls,
  invoiceFileError,
} from '../../constants/budgets';
import Modal, { secondaryButtonClass } from '../Modal';
import { MoneyInput, amberInput, amberPrimary } from './budgetUi';

const PAID = EXPENSE_STATUSES[0];
const round2 = (n) => Math.round(n * 100) / 100;
const numOrNull = (v) => (v === '' || v === null || v === undefined ? null : Number(v));

/* Add (expense = null) or edit an expense item of a holiday / event.
   The total follows quantity × unit price until it is typed by hand. */
export default function ExpenseModal({ year, event, expense, onClose, onSaved }) {
  const isEdit = Boolean(expense);
  const [form, setForm] = useState(() => ({
    item_name: expense?.item_name ?? '',
    quantity: String(expense?.quantity ?? 1),
    unit_price: expense?.unit_price != null ? String(expense.unit_price) : '',
    total_price: expense ? String(expense.total_price ?? 0) : '',
    status: expense?.status ?? DEFAULT_EXPENSE_STATUS,
    invoice_reference: expense?.invoice_reference ?? '',
    notes: expense?.notes ?? '',
  }));
  // An existing total that isn't quantity × unit price was entered by hand: don't overwrite it
  const [totalManual, setTotalManual] = useState(
    () => isEdit && (expense.unit_price == null || round2(expense.unit_price * expense.quantity) !== expense.total_price)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  // Invoice file: a newly picked File, and/or removal of the stored one
  const [newFile, setNewFile] = useState(null);
  const [removeStored, setRemoveStored] = useState(false);
  const [fileError, setFileError] = useState('');
  const fileInput = useRef(null);
  const storedFile = isEdit && !removeStored ? expense.invoice_file : null;
  const hasInvoice = Boolean(newFile || storedFile || form.invoice_reference.trim());

  const pickFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // picking the same file again still fires onChange
    if (!file) return;
    const problem = invoiceFileError(file);
    setFileError(problem || '');
    if (!problem) setNewFile(file);
  };

  const viewStored = () =>
    openFileInNewTab(() => budgetsApi.getInvoice(year, event.id, expense.id), expense.invoice_file.file_name).catch(
      (err) => setFileError(apiErrorMessage(err, 'שגיאה בפתיחת הקובץ'))
    );

  const set = (k) => (v) => setForm((p) => ({ ...p, [k]: v?.target ? v.target.value : v }));

  /* Quantity / unit price changed: recompute the total unless it was typed by hand */
  const setPricing = (k) => (v) =>
    setForm((p) => {
      const next = { ...p, [k]: v?.target ? v.target.value : v };
      const q = numOrNull(next.quantity);
      const u = numOrNull(next.unit_price);
      if (!totalManual && q > 0 && u !== null && Number.isFinite(q * u)) next.total_price = String(round2(q * u));
      return next;
    });

  const handleTotal = (v) => {
    setTotalManual(v !== '');
    set('total_price')(v);
  };

  const quantity = numOrNull(form.quantity);
  const unitPrice = numOrNull(form.unit_price);
  const total = numOrNull(form.total_price) ?? 0;
  const computed = quantity > 0 && unitPrice !== null ? round2(quantity * unitPrice) : null;

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!form.item_name.trim()) { setError('שם המוצר / הספק הוא שדה חובה'); return; }
    if (!(quantity > 0)) { setError('הכמות חייבת להיות גדולה מ-0'); return; }
    if (![unitPrice ?? 0, total].every((n) => Number.isFinite(n) && n >= 0)) {
      setError('המחירים חייבים להיות מספרים חיוביים');
      return;
    }
    const payload = {
      item_name: form.item_name.trim(),
      quantity,
      unit_price: unitPrice,
      total_price: total,
      status: form.status,
      invoice_reference: form.invoice_reference.trim(),
      notes: form.notes.trim(),
    };
    setSaving(true);
    setError('');
    try {
      const { data } = isEdit
        ? await budgetsApi.updateExpense(year, event.id, expense.id, payload)
        : await budgetsApi.createExpense(year, event.id, payload);
      // The expense itself is saved; the file is a second request
      try {
        if (newFile) await budgetsApi.uploadInvoice(year, event.id, data.id, newFile);
        else if (isEdit && removeStored && expense.invoice_file) await budgetsApi.removeInvoice(year, event.id, data.id);
      } catch (err) {
        alert(`ההוצאה נשמרה, אך ${newFile ? 'העלאת' : 'הסרת'} קובץ החשבונית נכשלה: ${apiErrorMessage(err)}`);
      }
      onSaved(data, isEdit);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירת ההוצאה'));
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEdit ? `עריכת הוצאה – ${expense.item_name}` : `הוצאה חדשה – ${event.name}`}
      subtitle={`${event.name} ${year}`}
      onClose={onClose}
      maxWidth="max-w-xl"
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>ביטול</button>
          <button type="button" onClick={handleSubmit} disabled={saving} className={amberPrimary}>
            {saving ? 'שומר...' : isEdit ? 'שמירה' : 'הוספת הוצאה'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4" noValidate>
        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">שם המוצר / ספק <span className="text-red-500">*</span></span>
          <input value={form.item_name} onChange={set('item_name')} autoFocus className={amberInput} placeholder="לדוגמה: סופגניות" />
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">כמות</span>
          <input
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            dir="ltr"
            value={form.quantity}
            onChange={setPricing('quantity')}
            className={`${amberInput} text-right`}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">מחיר ליחידה</span>
          <MoneyInput value={form.unit_price} onChange={setPricing('unit_price')} />
        </label>

        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">סכום כולל</span>
          <MoneyInput value={form.total_price} onChange={handleTotal} />
          <span className="block text-xs text-gray-500 mt-1">
            {computed !== null && !totalManual
              ? `מחושב אוטומטית: ${form.quantity} × ${formatIls(unitPrice)}`
              : computed !== null && computed !== total
                ? (
                  <>
                    הסכום הוזן ידנית (כמות × מחיר = {formatIls(computed)}).{' '}
                    <button
                      type="button"
                      className="text-amber-700 hover:underline"
                      onClick={() => { setTotalManual(false); set('total_price')(String(computed)); }}
                    >
                      חישוב מחדש
                    </button>
                  </>
                )
                : 'אפשר להזין מחיר ליחידה והסכום יחושב, או להזין סכום כולל ישירות'}
          </span>
        </label>

        <div className="col-span-2">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">סטטוס תשלום</span>
          <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="סטטוס תשלום">
            {EXPENSE_STATUSES.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={form.status === s}
                onClick={() => set('status')(s)}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                  form.status === s ? `${EXPENSE_STATUS_STYLES[s]} ring-2 ring-offset-1 ring-amber-300` : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="col-span-2">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">קובץ חשבונית</span>
          {newFile || storedFile ? (
            <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
              {(newFile?.type || storedFile?.content_type || '').startsWith('image/') ? (
                <ImageIcon className="h-5 w-5 text-amber-600 flex-shrink-0" />
              ) : (
                <FileText className="h-5 w-5 text-amber-600 flex-shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm text-gray-800 truncate" dir="auto" title={newFile?.name ?? storedFile.file_name}>
                  {newFile?.name ?? storedFile.file_name}
                </p>
                <p className="text-xs text-gray-400">
                  {formatFileSize(newFile?.size ?? storedFile.size)}
                  {newFile ? ' · יועלה בשמירה' : ''}
                </p>
              </div>
              {!newFile && (
                <button type="button" onClick={viewStored} className="p-1.5 rounded-lg text-gray-500 hover:text-amber-700 hover:bg-white" title="צפייה בקובץ">
                  <Eye className="h-4 w-4" />
                </button>
              )}
              <button type="button" onClick={() => fileInput.current?.click()} className="text-xs text-amber-700 hover:underline px-1">
                החלפה
              </button>
              <button
                type="button"
                onClick={() => { setNewFile(null); if (storedFile && !newFile) setRemoveStored(true); }}
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-white"
                title={newFile ? 'ביטול הבחירה' : 'הסרת הקובץ'}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="w-full flex items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-200 px-3 py-3 text-sm text-gray-500 hover:border-amber-300 hover:text-amber-700 hover:bg-amber-50/40 transition-colors"
            >
              <Upload className="h-4 w-4" />
              בחירת קובץ מהמחשב (PDF, PNG, JPG · עד 5MB)
            </button>
          )}
          <input ref={fileInput} type="file" accept={INVOICE_ACCEPT} onChange={pickFile} className="hidden" />
          {removeStored && !newFile && (
            <span className="block text-xs text-gray-500 mt-1">
              הקובץ יוסר בשמירה.{' '}
              <button type="button" className="text-amber-700 hover:underline" onClick={() => setRemoveStored(false)}>ביטול</button>
            </span>
          )}
          {fileError && <span className="block text-xs text-red-600 mt-1">{fileError}</span>}
        </div>

        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">מס׳ חשבונית / אסמכתא</span>
          <input
            value={form.invoice_reference}
            onChange={set('invoice_reference')}
            className={amberInput}
            placeholder="מס׳ חשבונית או קישור (אופציונלי)"
          />
          {form.status === PAID && !hasInvoice && (
            <span className="block text-xs text-amber-700 mt-1">ההוצאה שולמה — מומלץ לצרף את קובץ החשבונית</span>
          )}
        </label>

        <label className="col-span-2 block">
          <span className="block text-sm font-medium text-gray-700 mb-1.5">הערות</span>
          <textarea value={form.notes} onChange={set('notes')} rows={2} className={`${amberInput} resize-none`} />
        </label>

        {error && <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
        <button type="submit" className="hidden" />
      </form>
    </Modal>
  );
}
