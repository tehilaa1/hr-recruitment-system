import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Download,
  ExternalLink,
  FileText,
  Image as ImageIcon,
  Loader2,
  Paperclip,
  Pencil,
  Plus,
  ReceiptText,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';
import { apiErrorMessage, budgetsApi, openFileInNewTab, saveDownload } from '../../api/client';
import {
  EXPENSE_STATUSES,
  EXPENSE_STATUS_STYLES,
  INVOICE_ACCEPT,
  formatFileSize,
  formatIls,
  invoiceFileError,
} from '../../constants/budgets';
import ExpenseModal from './ExpenseModal';

const PAID = EXPENSE_STATUSES[0];
const fmtQty = (q) => new Intl.NumberFormat('he-IL', { maximumFractionDigits: 3 }).format(Number(q) || 0);

function ExpenseStatusBadge({ status }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border whitespace-nowrap ${EXPENSE_STATUS_STYLES[status] ?? EXPENSE_STATUS_STYLES[EXPENSE_STATUSES[1]]}`}>
      {status}
    </span>
  );
}

/* Uploaded file (view in a new tab), else a text reference, else a direct "attach file" picker */
function InvoiceCell({ year, eventId, expense, onUploaded }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const file = expense.invoice_file;
  const ref = expense.invoice_reference;

  const view = async () => {
    setBusy(true);
    try {
      await openFileInNewTab(() => budgetsApi.getInvoice(year, eventId, expense.id), file.file_name);
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה בפתיחת הקובץ'));
    } finally {
      setBusy(false);
    }
  };

  const upload = async (e) => {
    const picked = e.target.files?.[0];
    e.target.value = '';
    if (!picked) return;
    const problem = invoiceFileError(picked);
    if (problem) { alert(problem); return; }
    setBusy(true);
    try {
      await budgetsApi.uploadInvoice(year, eventId, expense.id, picked);
      onUploaded();
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה בהעלאת הקובץ'));
    } finally {
      setBusy(false);
    }
  };

  const reference = ref ? (
    /^https?:\/\//i.test(ref) ? (
      <a href={ref} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline" title={ref}>
        <ExternalLink className="h-3 w-3" /> קישור
      </a>
    ) : (
      <span className="block text-[11px] text-gray-500 truncate max-w-[160px]" title={ref}>{ref}</span>
    )
  ) : null;

  if (file) {
    const Icon = file.content_type?.startsWith('image/') ? ImageIcon : FileText;
    return (
      <div className="leading-tight">
        <button
          type="button"
          onClick={view}
          disabled={busy}
          className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:underline disabled:opacity-60 max-w-[180px]"
          title={`${file.file_name} (${formatFileSize(file.size)}) – פתיחה בלשונית חדשה`}
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin flex-shrink-0" /> : <Icon className="h-3.5 w-3.5 flex-shrink-0" />}
          <span className="truncate" dir="auto">{file.file_name}</span>
        </button>
        {reference}
      </div>
    );
  }

  const missing = expense.status === PAID;
  return (
    <div className="leading-tight">
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={busy}
        className={`inline-flex items-center gap-1 text-xs rounded-md px-1.5 py-0.5 disabled:opacity-60 ${
          missing ? 'text-amber-700 bg-amber-50 hover:bg-amber-100' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
        }`}
        title="העלאת קובץ חשבונית (PDF, PNG, JPG · עד 5MB)"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Paperclip className="h-3.5 w-3.5" />}
        {missing && !ref ? 'חסרה חשבונית' : 'צירוף קובץ'}
      </button>
      <input ref={input} type="file" accept={INVOICE_ACCEPT} onChange={upload} className="hidden" />
      {reference}
    </div>
  );
}

/* Itemized expenses of one holiday / event: table, add/edit modal and Excel export */
export default function EventExpenses({ year, event, onChanged, onClose }) {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(undefined); // undefined = closed, null = new, object = edit
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await budgetsApi.listExpenses(year, event.id);
      setExpenses(data);
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בטעינת ההוצאות'));
    } finally {
      setLoading(false);
    }
  }, [year, event.id]);

  useEffect(() => { load(); }, [load]);

  /* The event's actual_spent is derived from its expenses, so refresh the year too */
  const afterChange = () => {
    load();
    onChanged();
  };

  const handleDelete = async (expense) => {
    if (!window.confirm(`למחוק את "${expense.item_name}"?`)) return;
    try {
      await budgetsApi.removeExpense(year, event.id, expense.id);
      afterChange();
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה במחיקת ההוצאה'));
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      saveDownload(await budgetsApi.exportExpenses(year, event.id), `expenses_${year}.xlsx`);
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה בייצוא לאקסל'));
    } finally {
      setExporting(false);
    }
  };

  const summary = useMemo(() => {
    const total = expenses.reduce((s, e) => s + (Number(e.total_price) || 0), 0);
    const paid = expenses.filter((e) => e.status === PAID).reduce((s, e) => s + (Number(e.total_price) || 0), 0);
    const r = (n) => Math.round(n * 100) / 100;
    return { total: r(total), paid: r(paid), pending: r(total - paid), remaining: r((event.allocated_budget || 0) - total) };
  }, [expenses, event.allocated_budget]);

  return (
    <div className="bg-white rounded-2xl border border-amber-200 shadow-sm overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-gray-100 bg-amber-50/40">
        <div className="flex items-center gap-3 min-w-0">
          <div className="rounded-xl p-2 bg-amber-100 text-amber-600"><ReceiptText className="h-5 w-5" /></div>
          <div className="min-w-0">
            <h2 className="text-base font-bold text-gray-900 truncate">פירוט הוצאות – {event.name} {year}</h2>
            <p className="text-xs text-gray-500 mt-0.5 tabular-nums">
              תקציב {formatIls(event.allocated_budget)} · הוצאות {formatIls(summary.total)} ·{' '}
              <span className={summary.remaining < 0 ? 'text-red-600 font-medium' : 'text-emerald-600'}>
                {summary.remaining < 0 ? `חריגה ${formatIls(-summary.remaining)}` : `יתרה ${formatIls(summary.remaining)}`}
              </span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            disabled={exporting || expenses.length === 0}
            className="flex items-center gap-1.5 border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 px-3 py-2 rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            ייצוא Excel
          </button>
          <button
            onClick={() => setModal(null)}
            className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white px-3.5 py-2 rounded-xl text-sm font-semibold"
          >
            <Plus className="h-4 w-4" /> הוספת הוצאה
          </button>
          <button onClick={onClose} className="p-2 rounded-xl text-gray-400 hover:text-gray-700 hover:bg-white" title="סגירת הפירוט">
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {loading && expenses.length === 0 ? (
        <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 text-amber-500 animate-spin" /></div>
      ) : error ? (
        <div className="flex flex-col items-center py-12 gap-2">
          <p className="text-gray-500 text-sm">{error}</p>
          <button onClick={load} className="flex items-center gap-1.5 text-sm text-amber-600 hover:underline">
            <RefreshCw className="h-3.5 w-3.5" /> נסה שנית
          </button>
        </div>
      ) : expenses.length === 0 ? (
        <div className="flex flex-col items-center py-12 gap-2 text-center">
          <ReceiptText className="h-8 w-8 text-gray-300" />
          <p className="text-gray-500">אין עדיין הוצאות ב{event.name}</p>
          <p className="text-xs text-gray-400 max-w-sm">
            לאחר הוספת הוצאה ראשונה, ״בפועל״ של האירוע יחושב אוטומטית מסכום ההוצאות
          </p>
          <button onClick={() => setModal(null)} className="text-sm text-amber-600 hover:underline mt-1">הוספת הוצאה ראשונה</button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50/80 border-b border-gray-200 text-xs text-gray-500">
                {['שם המוצר / ספק', 'כמות', 'מחיר ליחידה', 'סכום כולל', 'סטטוס תשלום', 'חשבונית', 'הערות'].map((h) => (
                  <th key={h} className="px-4 py-3 text-right font-semibold whitespace-nowrap">{h}</th>
                ))}
                <th className="w-20" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {expenses.map((x) => (
                <tr key={x.id} className="group hover:bg-amber-50/30">
                  <td className="px-4 py-3 font-semibold text-gray-900">{x.item_name}</td>
                  <td className="px-4 py-3 tabular-nums">{fmtQty(x.quantity)}</td>
                  <td className="px-4 py-3 tabular-nums whitespace-nowrap">
                    {x.unit_price != null ? formatIls(x.unit_price) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3 tabular-nums whitespace-nowrap font-medium">{formatIls(x.total_price)}</td>
                  <td className="px-4 py-3"><ExpenseStatusBadge status={x.status} /></td>
                  <td className="px-4 py-3 whitespace-nowrap"><InvoiceCell year={year} eventId={event.id} expense={x} onUploaded={load} /></td>
                  <td className="px-4 py-3 text-gray-500 max-w-[220px] truncate" title={x.notes}>
                    {x.notes || <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => setModal(x)} className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100" title="עריכה">
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(x)}
                        className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 focus:opacity-100"
                        title="מחיקה"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-gray-50 border-t-2 border-gray-200 font-semibold text-gray-800">
                <td className="px-4 py-3" colSpan={3}>סה״כ ({expenses.length} פריטים)</td>
                <td className="px-4 py-3 tabular-nums whitespace-nowrap">{formatIls(summary.total)}</td>
                <td className="px-4 py-3 text-xs font-normal whitespace-nowrap" colSpan={4}>
                  <span className="text-emerald-700">שולם {formatIls(summary.paid)}</span>
                  <span className="text-gray-300 mx-2">|</span>
                  <span className="text-orange-700">ישולם בהעברה {formatIls(summary.pending)}</span>
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {modal !== undefined && (
        <ExpenseModal
          year={year}
          event={event}
          expense={modal}
          onClose={() => setModal(undefined)}
          onSaved={afterChange}
        />
      )}
    </div>
  );
}
