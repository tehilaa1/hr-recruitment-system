import { useState } from 'react';
import { FileText, Plus, Users, X } from 'lucide-react';
import { apiErrorMessage, maternityApi } from '../../api/client';
import { DEFAULT_TEMPLATES, effectiveTemplate } from '../../utils/maternityTemplates';
import Modal, { inputClass, primaryButtonClass, secondaryButtonClass } from '../Modal';
import MaternityTemplatesEditor, { unknownPlaceholders } from './MaternityTemplatesEditor';

const TABS = [
  { key: 'recipients', label: 'נמענים וערוצים', icon: Users },
  { key: 'templates', label: 'תבניות הודעות', icon: FileText },
];

/* Text equal to the built-in default is saved as "" so future default updates apply */
const toStoredTemplates = (templates) =>
  Object.fromEntries(
    Object.keys(DEFAULT_TEMPLATES).map((k) => {
      const text = templates[k] ?? '';
      return [k, text.trim() === DEFAULT_TEMPLATES[k].trim() ? '' : text];
    })
  );

/* Edit the fixed notification recipients, the Teams channel link and the message templates */
export default function MaternitySettingsModal({ settings, onClose, onSaved, initialTab = 'recipients' }) {
  const [tab, setTab] = useState(initialTab);
  const [templates, setTemplates] = useState(() =>
    Object.fromEntries(Object.keys(DEFAULT_TEMPLATES).map((k) => [k, effectiveTemplate(settings, k)]))
  );
  const [recipients, setRecipients] = useState(
    settings?.notify_recipients?.length ? settings.notify_recipients : ['']
  );
  const [teamsUrl, setTeamsUrl] = useState(settings?.teams_channel_url ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const update = (i, v) => setRecipients((p) => p.map((x, idx) => (idx === i ? v : x)));
  const remove = (i) => setRecipients((p) => (p.length > 1 ? p.filter((_, idx) => idx !== i) : ['']));
  const add = () => setRecipients((p) => [...p, '']);

  const handleSave = async () => {
    const unknown = unknownPlaceholders(templates);
    if (unknown.length) {
      setTab('templates');
      setError(`שדות לא מוכרים בתבנית: ${unknown.map((k) => `{${k}}`).join(', ')}`);
      return;
    }
    const emptyKey = Object.keys(DEFAULT_TEMPLATES).find((k) => !templates[k]?.trim());
    if (emptyKey) {
      setTab('templates');
      setError('אחת התבניות ריקה – כתבו טקסט או לחצו ״שחזור ברירת מחדל״');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await maternityApi.saveSettings({
        notify_recipients: recipients.map((r) => r.trim()).filter(Boolean),
        teams_channel_url: teamsUrl.trim(),
        templates: toStoredTemplates(templates),
      });
      onSaved(data);
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'שגיאה בשמירת ההגדרות'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title="הגדרות התראות"
      subtitle="נשמר לכל המערכת ומשמש בכל שליחת עדכון"
      onClose={onClose}
      maxWidth={tab === 'templates' ? 'max-w-3xl' : 'max-w-lg'}
      footer={
        <>
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            ביטול
          </button>
          <button type="button" onClick={handleSave} disabled={saving} className={primaryButtonClass}>
            {saving ? 'שומר...' : 'שמירה'}
          </button>
        </>
      }
    >
      <div className="flex gap-1 border-b border-gray-100 -mt-1 mb-5" role="tablist">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? 'border-pink-500 text-pink-700'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'templates' ? (
        <MaternityTemplatesEditor value={templates} onChange={setTemplates} />
      ) : (
      <div className="space-y-6">
        <div>
          <p className="text-sm font-medium text-gray-700">נמענים קבועים למייל עדכון</p>
          <p className="text-xs text-gray-400 mb-2">לדוגמה: שכר, נוכחות, מנהל/ת ישיר/ה, רווחה</p>
          <div className="flex flex-col gap-2">
            {recipients.map((r, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="email"
                  dir="ltr"
                  value={r}
                  placeholder="name@company.com"
                  onChange={(e) => update(i, e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (i === recipients.length - 1) add();
                    }
                  }}
                  className={inputClass}
                />
                <button
                  type="button"
                  onClick={() => remove(i)}
                  className="text-gray-400 hover:text-red-500 p-1"
                  title="הסר"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={add}
              className="flex items-center gap-1 text-pink-600 hover:text-pink-700 text-sm font-medium w-fit mt-1"
            >
              <Plus className="h-3.5 w-3.5" />
              הוסף נמען
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="teams-url" className="text-sm font-medium text-gray-700">
            קישור לערוץ Teams (אופציונלי)
          </label>
          <p className="text-xs text-gray-400 mb-2">
            ב-Teams: לחיצה על ⋯ ליד שם הערוץ ← "קבלת קישור לערוץ"
          </p>
          <input
            id="teams-url"
            type="url"
            dir="ltr"
            value={teamsUrl}
            placeholder="https://teams.microsoft.com/l/channel/..."
            onChange={(e) => setTeamsUrl(e.target.value)}
            className={inputClass}
          />
        </div>
      </div>
      )}

      {error && (
        <p className="mt-5 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
      )}
    </Modal>
  );
}
