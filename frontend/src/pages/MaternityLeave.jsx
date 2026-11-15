import { useEffect, useMemo, useState } from 'react';
import {
  Baby,
  CalendarClock,
  CalendarPlus,
  ClipboardX,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings,
  Trash2,
} from 'lucide-react';
import { maternityApi } from '../api/client';
import CompleteToggle from '../components/CompleteToggle';
import Navbar from '../components/Navbar';
import MaternityActionsModal from '../components/maternity/MaternityActionsModal';
import MaternityFormModal from '../components/maternity/MaternityFormModal';
import MaternitySettingsModal from '../components/maternity/MaternitySettingsModal';
import { MATERNITY_COLUMNS, formatIsoDate } from '../constants/maternityColumns';
import { returnFollowupDate } from '../utils/dates';
import { buildMaternityReminderUrl, openInNewTab } from '../utils/outlook';

const RETURN_SOON_DAYS = 30;

const todayIso = () => new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD, local time
const addDaysIso = (days) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString('en-CA');
};

const Empty = () => <span className="text-gray-300">—</span>;

/* Active records first; completed ("יולדת חזרה") ones sink to the bottom, order otherwise kept */
const activeFirst = (list) =>
  list
    .map((r, i) => [r, i])
    .sort(([a, ai], [b, bi]) => Number(!!a.is_completed) - Number(!!b.is_completed) || ai - bi)
    .map(([r]) => r);

/* Opens a pre-filled Outlook event 13 weeks after the birth (weekends -> Thursday) */
function ReminderButton({ record }) {
  const date = returnFollowupDate(record.birth_date);
  return (
    <button
      type="button"
      disabled={!date}
      onClick={() => openInNewTab(buildMaternityReminderUrl(record))}
      title={
        date
          ? `תזכורת ביומן Outlook ל-${formatIsoDate(date)} (13 שבועות מהלידה) – יצירת קשר לבדיקת מועד החזרה`
          : 'יש להזין תאריך לידה כדי ליצור תזכורת'
      }
      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-violet-200 text-violet-600 hover:bg-violet-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
    >
      <CalendarPlus className="h-3.5 w-3.5" />
      תזכורת ב-Outlook
    </button>
  );
}

function StatCard({ title, value, icon: Icon, colorClass }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 flex items-center gap-4">
      <div className={`rounded-xl p-3 ${colorClass}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500 font-medium">{title}</p>
        <p className="text-2xl font-bold text-gray-900 leading-tight">{value}</p>
      </div>
    </div>
  );
}

/* Renders one table cell according to the column type */
function Cell({ col, record, onToggle, toggling }) {
  const value = record[col.key];

  switch (col.type) {
    case 'group': {
      const parts = col.fields.map((f) => record[f.key]).filter(Boolean);
      if (!parts.length) return <Empty />;
      return (
        <div className="leading-tight">
          {parts.map((p, i) => (
            <div key={i} className={i ? 'text-xs text-gray-500 font-mono' : 'text-gray-700'}>
              {p}
            </div>
          ))}
        </div>
      );
    }
    case 'date':
      return value ? <span className="whitespace-nowrap">{formatIsoDate(value)}</span> : <Empty />;
    case 'tel':
      return value ? (
        <a href={`tel:${value}`} className="font-mono text-xs tracking-wider hover:text-pink-600" dir="ltr">
          {value}
        </a>
      ) : (
        <Empty />
      );
    case 'email':
      return value ? (
        <a href={`mailto:${value}`} className="text-blue-600 hover:underline text-xs" title={value}>
          {value}
        </a>
      ) : (
        <Empty />
      );
    case 'boolean':
      return (
        <button
          type="button"
          disabled={toggling}
          onClick={() => onToggle(record, col.key)}
          title="לחצו לשינוי"
          className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-opacity hover:opacity-80 disabled:opacity-50 ${
            value
              ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
              : 'bg-amber-50 text-amber-700 border-amber-200'
          }`}
        >
          {value ? 'כן' : 'לא'}
        </button>
      );
    default:
      return value ? (
        <span className="block truncate max-w-[220px]" title={value}>
          {value}
        </span>
      ) : (
        <Empty />
      );
  }
}

export default function MaternityLeave() {
  const [records, setRecords] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [filter, setFilter] = useState('');
  const [togglingId, setTogglingId] = useState(null);

  const [formRecord, setFormRecord] = useState(undefined); // undefined = closed, null = new
  const [actionsRecord, setActionsRecord] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    setError(false);
    try {
      const [recRes, setRes] = await Promise.all([maternityApi.list(), maternityApi.getSettings()]);
      setRecords(recRes.data);
      setSettings(setRes.data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const handleSaved = (saved, isEdit) =>
    setRecords((prev) => (isEdit ? prev.map((r) => (r.id === saved.id ? saved : r)) : [saved, ...prev]));

  const handleDelete = async (record) => {
    if (!window.confirm(`למחוק את ${record.name} מהטבלה?`)) return;
    try {
      await maternityApi.remove(record.id);
      setRecords((prev) => prev.filter((r) => r.id !== record.id));
    } catch {
      alert('שגיאה במחיקה');
    }
  };

  /* Optimistic yes/no toggle with rollback */
  const handleToggle = async (record, key) => {
    const previous = Boolean(record[key]);
    const next = !previous;
    setRecords((prev) => prev.map((r) => (r.id === record.id ? { ...r, [key]: next } : r)));
    setTogglingId(record.id);
    try {
      await maternityApi.update(record.id, { [key]: next });
    } catch {
      // Only roll back if nothing newer has replaced our optimistic value meanwhile
      setRecords((prev) =>
        prev.map((r) => (r.id === record.id && Boolean(r[key]) === next ? { ...r, [key]: previous } : r))
      );
      alert('שגיאה בעדכון – הערך הוחזר');
    } finally {
      setTogglingId(null);
    }
  };

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const matching = q
      ? records.filter((r) =>
          [r.name, r.phone, r.company_email, r.notes].some((v) => String(v || '').toLowerCase().includes(q))
        )
      : records;
    return activeFirst(matching);
  }, [records, filter]);

  const completedCount = useMemo(() => filtered.filter((r) => r.is_completed).length, [filtered]);

  /* Stats count only open records: employees who already returned are done */
  const stats = useMemo(() => {
    const today = todayIso();
    const soon = addDaysIso(RETURN_SOON_DAYS);
    const active = records.filter((r) => !r.is_completed);
    return {
      total: active.length,
      returned: records.length - active.length,
      notUpdated: active.filter((r) => !r.attendance_updated).length,
      returningSoon: active.filter(
        (r) => r.expected_return_date && r.expected_return_date >= today && r.expected_return_date <= soon
      ).length,
    };
  }, [records]);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">מעקב חופשות לידה</h1>
            <p className="text-sm text-gray-400 mt-1">ניהול עובדים/ות בחופשת לידה ושליחת עדכונים</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center gap-2 border border-gray-200 text-gray-600 hover:bg-white px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              <Settings className="h-4 w-4" />
              הגדרות התראות
            </button>
            <button
              onClick={() => setFormRecord(null)}
              className="flex items-center gap-2 bg-pink-600 hover:bg-pink-700 text-white px-4 py-2.5 rounded-xl font-semibold text-sm transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" />
              הוספת רשומה
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard title="בחופשת לידה" value={stats.total} icon={Baby} colorClass="bg-pink-50 text-pink-500" />
          <StatCard
            title="טרם עודכנו בנוכחות"
            value={stats.notUpdated}
            icon={ClipboardX}
            colorClass="bg-amber-50 text-amber-500"
          />
          <StatCard
            title={`חוזרים/ות ב-${RETURN_SOON_DAYS} הימים הקרובים`}
            value={stats.returningSoon}
            icon={CalendarClock}
            colorClass="bg-emerald-50 text-emerald-500"
          />
        </div>

        {/* Table card */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-gray-100">
            <h2 className="text-base font-bold text-gray-900">
              רשומות {records.length > 0 && <span className="text-gray-400 font-normal">({filtered.length})</span>}
              {stats.returned > 0 && (
                <span className="mr-2 text-xs font-normal text-emerald-600">· {stats.returned} חזרו לעבודה</span>
              )}
            </h2>
            <div className="relative w-full max-w-xs">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="search"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="סינון לפי שם, טלפון, מייל..."
                className="w-full bg-gray-100 focus:bg-white border border-transparent focus:border-pink-300 rounded-xl py-2 pr-9 pl-3 text-sm outline-none"
              />
            </div>
          </div>

          {loading ? (
            <div className="flex justify-center py-20">
              <Loader2 className="h-7 w-7 text-pink-500 animate-spin" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center py-20 gap-3">
              <p className="text-gray-500">שגיאה בטעינת הנתונים</p>
              <button onClick={fetchAll} className="flex items-center gap-2 text-sm text-pink-600 hover:underline">
                <RefreshCw className="h-4 w-4" />
                נסה שנית
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center py-20 gap-3 text-center">
              <div className="bg-pink-50 rounded-full p-4">
                <Baby className="h-8 w-8 text-pink-300" />
              </div>
              <p className="text-gray-500 font-medium">
                {records.length ? 'אין רשומות התואמות לסינון' : 'אין רשומות עדיין'}
              </p>
              {!records.length && (
                <button onClick={() => setFormRecord(null)} className="text-sm text-pink-600 hover:underline">
                  הוספת הרשומה הראשונה
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50/80 border-b border-gray-200">
                    {MATERNITY_COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        className={`px-4 py-3 text-right text-xs font-semibold text-gray-500 whitespace-nowrap ${col.tableWidth ?? ''}`}
                      >
                        {col.label}
                      </th>
                    ))}
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 whitespace-nowrap min-w-[170px]">
                      סיום טיפול
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 whitespace-nowrap">
                      פעולות
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((r, idx) => (
                    <tr
                      key={r.id}
                      className={`transition-colors group ${
                        r.is_completed
                          ? 'bg-gray-50/80 [&>td:not(.keep-color)]:opacity-60 hover:bg-gray-100/70'
                          : 'hover:bg-pink-50/30'
                      } ${
                        // Divider between open records and employees who already returned
                        r.is_completed && idx === filtered.length - completedCount && idx > 0
                          ? 'border-t-2 border-t-gray-200'
                          : ''
                      }`}
                    >
                      {MATERNITY_COLUMNS.map((col) => (
                        <td
                          key={col.key}
                          className={`px-4 py-3 text-gray-700 align-middle ${
                            col.key === 'name' ? 'font-semibold text-gray-900 whitespace-nowrap' : ''
                          }`}
                        >
                          <Cell col={col} record={r} onToggle={handleToggle} toggling={togglingId === r.id} />
                        </td>
                      ))}
                      <td className="keep-color px-4 py-3 whitespace-nowrap">
                        <CompleteToggle
                          completed={!!r.is_completed}
                          disabled={togglingId === r.id}
                          onToggle={() => handleToggle(r, 'is_completed')}
                          label="סיום טיפול - יולדת חזרה"
                          doneLabel="חזרה לעבודה"
                          reopenLabel="פתיחה מחדש"
                          title="סמן שהעובדת חזרה לעבודה והטיפול הסתיים"
                        />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-1">
                          <ReminderButton record={r} />
                          <button
                            onClick={() => setActionsRecord(r)}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-pink-600 hover:bg-pink-700 text-white transition-colors"
                          >
                            <Send className="h-3.5 w-3.5" />
                            שליחת עדכונים
                          </button>
                          <button
                            onClick={() => setFormRecord(r)}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100"
                            title="עריכה"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(r)}
                            className="p-1.5 rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="מחיקה"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {formRecord !== undefined && (
        <MaternityFormModal record={formRecord} onClose={() => setFormRecord(undefined)} onSaved={handleSaved} />
      )}
      {actionsRecord && (
        <MaternityActionsModal
          record={actionsRecord}
          settings={settings}
          onClose={() => setActionsRecord(null)}
          onOpenSettings={() => setShowSettings(true)}
        />
      )}
      {showSettings && (
        <MaternitySettingsModal settings={settings} onClose={() => setShowSettings(false)} onSaved={setSettings} />
      )}
    </div>
  );
}
