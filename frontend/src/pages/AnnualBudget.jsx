import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CalendarRange,
  Coins,
  Loader2,
  Pencil,
  PiggyBank,
  Plus,
  Receipt,
  ReceiptText,
  RefreshCw,
  Trash2,
  Wallet,
} from 'lucide-react';
import { apiErrorMessage, budgetsApi } from '../api/client';
import Navbar from '../components/Navbar';
import BudgetEventModal from '../components/budgets/BudgetEventModal';
import BudgetYearModal from '../components/budgets/BudgetYearModal';
import EventExpenses from '../components/budgets/EventExpenses';
import { EventStatusBadge } from '../components/budgets/budgetUi';
import { formatIls } from '../constants/budgets';
import { formatIsoDate } from '../constants/maternityColumns';

const pct = (part, whole) => (whole > 0 ? Math.round((part / whole) * 100) : 0);

function KpiCard({ title, value, sub, icon: Icon, tone = 'amber', bar }) {
  const tones = {
    amber: 'bg-amber-50 text-amber-600',
    sky: 'bg-sky-50 text-sky-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
    violet: 'bg-violet-50 text-violet-600',
  };
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2.5 ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <p className="text-xs text-gray-500 font-medium">{title}</p>
      </div>
      <p className={`text-2xl font-bold mt-3 tabular-nums ${tone === 'red' ? 'text-red-600' : 'text-gray-900'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      {bar !== undefined && (
        <div className="h-1.5 bg-gray-100 rounded-full mt-3 overflow-hidden">
          <div
            className={`h-full rounded-full ${bar > 100 ? 'bg-red-500' : 'bg-amber-400'}`}
            style={{ width: `${Math.min(100, bar)}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Variance({ value }) {
  if (!value) return <span className="text-gray-400 tabular-nums">{formatIls(0)}</span>;
  return (
    <span className={`font-medium tabular-nums ${value < 0 ? 'text-red-600' : 'text-emerald-600'}`} dir="ltr">
      {value < 0 ? '−' : '+'}
      {formatIls(Math.abs(value))}
    </span>
  );
}

export default function AnnualBudget() {
  const [params, setParams] = useSearchParams();
  const [years, setYears] = useState([]); // summaries, newest first
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [yearModal, setYearModal] = useState(undefined); // undefined = closed, null = new, object = edit
  const [eventModal, setEventModal] = useState(undefined);

  const selectedYear = Number(params.get('year')) || null;
  const selectedEventId = params.get('event');
  const selectYear = (y) => setParams(y ? { year: String(y) } : {}, { replace: true });
  /* Opens (or closes, when already open) the holiday's itemized expenses */
  const toggleEvent = (id) =>
    setParams(
      id && id !== selectedEventId ? { year: String(selectedYear), event: id } : { year: String(selectedYear) },
      { replace: true }
    );
  const expensesRef = useRef(null);

  const loadYears = useCallback(async () => {
    const { data } = await budgetsApi.list();
    setYears(data);
    return data;
  }, []);

  // Initial load: pick the requested year, else the current year, else the newest
  useEffect(() => {
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await loadYears();
        if (data.length && !data.some((y) => y.year === selectedYear)) {
          const current = new Date().getFullYear();
          selectYear((data.find((y) => y.year === current) ?? data[0]).year);
        }
      } catch (err) {
        setError(apiErrorMessage(err, 'שגיאה בטעינת התקציבים'));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Selected year's events
  useEffect(() => {
    if (!selectedYear) { setDetail(null); return undefined; }
    let cancelled = false;
    setDetailLoading(true);
    budgetsApi
      .get(selectedYear)
      .then(({ data }) => !cancelled && setDetail(data))
      .catch(() => !cancelled && setDetail(null))
      .finally(() => !cancelled && setDetailLoading(false));
    return () => { cancelled = true; };
  }, [selectedYear]);

  /* After any change: replace the year's detail and refresh the summaries */
  const applyDetail = (data) => {
    setDetail(data);
    loadYears().catch(() => {});
  };

  const refreshDetail = async () => {
    const { data } = await budgetsApi.get(selectedYear);
    applyDetail(data);
  };

  const handleYearSaved = (data) => {
    applyDetail(data);
    selectYear(data.year);
  };

  const handleDeleteYear = async () => {
    if (!window.confirm(`למחוק את תקציב ${detail.year} ואת כל ${detail.events.length} האירועים שבו? לא ניתן לבטל.`)) return;
    try {
      await budgetsApi.remove(detail.year);
      const data = await loadYears();
      selectYear(data[0]?.year ?? null);
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה במחיקת התקציב'));
    }
  };

  const handleDeleteEvent = async (event) => {
    if (!window.confirm(`למחוק את "${event.name}"?`)) return;
    try {
      await budgetsApi.removeEvent(detail.year, event.id);
      await refreshDetail();
    } catch (err) {
      alert(apiErrorMessage(err, 'שגיאה במחיקת האירוע'));
    }
  };

  const suggestedYear = useMemo(() => {
    const current = new Date().getFullYear();
    const taken = new Set(years.map((y) => y.year));
    let y = taken.has(current) ? Math.max(...taken) + 1 : current;
    while (taken.has(y)) y += 1;
    return y;
  }, [years]);

  const d = detail;
  const selectedEvent = d?.events.find((e) => e.id === selectedEventId) ?? null;

  useEffect(() => {
    if (selectedEvent) expensesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    // Only when a different holiday is opened, not on every refresh of its data
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedEvent?.id]);
  const totals = d && {
    allocated: d.allocated_total,
    spent: d.spent_total,
    variance: Math.round((d.allocated_total - d.spent_total) * 100) / 100,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="rounded-xl p-3 bg-amber-100 text-amber-600">
              <Wallet className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">ניהול תקציב שנתי</h1>
              <p className="text-sm text-gray-400 mt-0.5">תקציב לכל שנה, וחלוקתו לחגים ולאירועים</p>
            </div>
          </div>
          <button
            onClick={() => setYearModal(null)}
            className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
          >
            <Plus className="h-4 w-4" />
            תקציב לשנה חדשה
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center py-24">
            <Loader2 className="h-8 w-8 text-amber-500 animate-spin" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center py-20 gap-3">
            <p className="text-gray-500">{error}</p>
            <button onClick={() => window.location.reload()} className="flex items-center gap-2 text-sm text-amber-600 hover:underline">
              <RefreshCw className="h-4 w-4" /> נסה שנית
            </button>
          </div>
        ) : years.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm flex flex-col items-center py-20 gap-3 text-center">
            <div className="bg-amber-50 rounded-full p-4"><PiggyBank className="h-8 w-8 text-amber-400" /></div>
            <p className="text-gray-600 font-medium">עדיין לא הוגדר תקציב שנתי</p>
            <button onClick={() => setYearModal(null)} className="text-sm text-amber-600 hover:underline">
              יצירת התקציב הראשון
            </button>
          </div>
        ) : (
          <>
            {/* Years */}
            <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="שנות תקציב">
              {years.map((y) => {
                const active = y.year === selectedYear;
                return (
                  <button
                    key={y.year}
                    role="tab"
                    aria-selected={active}
                    onClick={() => selectYear(y.year)}
                    className={`flex-shrink-0 text-right rounded-xl border px-4 py-2.5 transition-colors ${
                      active ? 'bg-white border-amber-300 ring-2 ring-amber-100 shadow-sm' : 'bg-white/60 border-gray-200 hover:bg-white'
                    }`}
                  >
                    <span className={`block text-lg font-bold ${active ? 'text-gray-900' : 'text-gray-600'}`}>{y.year}</span>
                    <span className={`block text-[11px] tabular-nums ${y.remaining < 0 ? 'text-red-600' : 'text-gray-400'}`}>
                      יתרה {formatIls(y.remaining)} · {y.events_count} אירועים
                    </span>
                  </button>
                );
              })}
            </div>

            {detailLoading && !d ? (
              <div className="flex justify-center py-16"><Loader2 className="h-7 w-7 text-amber-500 animate-spin" /></div>
            ) : d && (
              <>
                {/* KPIs */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <KpiCard title={`תקציב שנתי ${d.year}`} value={formatIls(d.total_budget)} icon={Wallet} sub={d.notes || undefined} />
                  <KpiCard
                    title="הוקצה לאירועים"
                    value={formatIls(d.allocated_total)}
                    icon={CalendarRange}
                    tone="sky"
                    sub={`${pct(d.allocated_total, d.total_budget)}% מהתקציב השנתי`}
                    bar={pct(d.allocated_total, d.total_budget)}
                  />
                  <KpiCard
                    title="יתרה פנויה (לא מוקצית)"
                    value={formatIls(d.remaining)}
                    icon={PiggyBank}
                    tone={d.remaining < 0 ? 'red' : 'emerald'}
                    sub={d.remaining < 0 ? 'ההקצאות חורגות מהתקציב השנתי' : 'כרית ביטחון לשנה'}
                  />
                  <KpiCard
                    title="הוצא בפועל"
                    value={formatIls(d.spent_total)}
                    icon={Receipt}
                    tone="violet"
                    sub={`${pct(d.spent_total, d.allocated_total)}% מהסכום שהוקצה`}
                  />
                </div>

                {/* Events */}
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
                  <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-gray-100">
                    <div>
                      <h2 className="text-base font-bold text-gray-900">חגים ואירועים – {d.year}</h2>
                      <p className="text-xs text-gray-400 mt-0.5">
                        לחיצה על אירוע פותחת את פירוט ההוצאות שלו · אירועים בסטטוס ״בוטל״ אינם נספרים בסיכומים
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setYearModal(d)}
                        className="flex items-center gap-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 px-3 py-2 rounded-xl text-sm"
                      >
                        <Pencil className="h-3.5 w-3.5" /> עריכת התקציב
                      </button>
                      <button
                        onClick={handleDeleteYear}
                        className="p-2 rounded-xl text-gray-400 hover:text-red-500 hover:bg-red-50"
                        title={`מחיקת תקציב ${d.year}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => setEventModal(null)}
                        className="flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white px-3.5 py-2 rounded-xl text-sm font-semibold"
                      >
                        <Plus className="h-4 w-4" /> הוספת אירוע
                      </button>
                    </div>
                  </div>

                  {d.events.length === 0 ? (
                    <div className="flex flex-col items-center py-16 gap-2 text-center">
                      <Coins className="h-8 w-8 text-gray-300" />
                      <p className="text-gray-500">אין עדיין אירועים לשנה זו</p>
                      <button onClick={() => setEventModal(null)} className="text-sm text-amber-600 hover:underline">
                        הוספת חג או אירוע
                      </button>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50/80 border-b border-gray-200 text-xs text-gray-500">
                            {['חג / אירוע', 'תאריך', 'סטטוס', 'תקציב מוקצה', 'בפועל', 'סטייה', 'הערות'].map((h) => (
                              <th key={h} className="px-4 py-3 text-right font-semibold whitespace-nowrap">{h}</th>
                            ))}
                            <th className="w-32" />
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {d.events.map((e) => (
                            <tr
                              key={e.id}
                              onClick={() => toggleEvent(e.id)}
                              className={`group cursor-pointer ${
                                e.id === selectedEventId ? 'bg-amber-50/70' : 'hover:bg-amber-50/30'
                              } ${e.status === 'בוטל' ? 'opacity-50' : ''}`}
                            >
                              <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">{e.name}</td>
                              <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{e.event_date ? formatIsoDate(e.event_date) : <span className="text-gray-300">—</span>}</td>
                              <td className="px-4 py-3"><EventStatusBadge status={e.status} /></td>
                              <td className="px-4 py-3 tabular-nums whitespace-nowrap">{formatIls(e.allocated_budget)}</td>
                              <td className="px-4 py-3 tabular-nums whitespace-nowrap">{formatIls(e.actual_spent)}</td>
                              <td className="px-4 py-3 whitespace-nowrap"><Variance value={e.variance} /></td>
                              <td className="px-4 py-3 text-gray-500 max-w-[220px] truncate" title={e.notes}>{e.notes || <span className="text-gray-300">—</span>}</td>
                              <td className="px-4 py-3" onClick={(ev) => ev.stopPropagation()}>
                                <div className="flex items-center gap-1 justify-end">
                                  <button
                                    onClick={() => toggleEvent(e.id)}
                                    className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs whitespace-nowrap ${
                                      e.id === selectedEventId
                                        ? 'bg-amber-100 text-amber-800'
                                        : 'text-gray-500 hover:text-amber-700 hover:bg-amber-50'
                                    }`}
                                    title="פירוט הוצאות"
                                  >
                                    <ReceiptText className="h-3.5 w-3.5" />
                                    {e.expenses_count > 0 ? e.expenses_count : 'הוצאות'}
                                  </button>
                                  <button onClick={() => setEventModal(e)} className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100" title="עריכה">
                                    <Pencil className="h-3.5 w-3.5" />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteEvent(e)}
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
                            <td className="px-4 py-3" colSpan={3}>סה״כ (ללא אירועים שבוטלו)</td>
                            <td className="px-4 py-3 tabular-nums whitespace-nowrap">{formatIls(totals.allocated)}</td>
                            <td className="px-4 py-3 tabular-nums whitespace-nowrap">{formatIls(totals.spent)}</td>
                            <td className="px-4 py-3 whitespace-nowrap"><Variance value={totals.variance} /></td>
                            <td colSpan={2} />
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  )}
                </div>

                {selectedEvent && (
                  <div ref={expensesRef} className="scroll-mt-4">
                    <EventExpenses
                      key={selectedEvent.id}
                      year={d.year}
                      event={selectedEvent}
                      onChanged={() => refreshDetail().catch(() => {})}
                      onClose={() => toggleEvent(null)}
                    />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>

      {yearModal !== undefined && (
        <BudgetYearModal
          budget={yearModal}
          suggestedYear={suggestedYear}
          onClose={() => setYearModal(undefined)}
          onSaved={handleYearSaved}
        />
      )}
      {eventModal !== undefined && d && (
        <BudgetEventModal
          year={d.year}
          event={eventModal}
          existingNames={d.events.map((e) => e.name)}
          onClose={() => setEventModal(undefined)}
          onSaved={() => refreshDetail().catch(() => {})}
        />
      )}
    </div>
  );
}
