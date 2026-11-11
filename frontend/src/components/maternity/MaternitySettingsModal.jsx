import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { apiErrorMessage, maternityApi } from '../../api/client';
import Modal, { inputClass, primaryButtonClass, secondaryButtonClass } from '../Modal';

/* Edit the fixed notification recipients and the Teams channel link */
export default function MaternitySettingsModal({ settings, onClose, onSaved }) {
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
    setSaving(true);
    setError('');
    try {
      const { data } = await maternityApi.saveSettings({
        notify_recipients: recipients.map((r) => r.trim()).filter(Boolean),
        teams_channel_url: teamsUrl.trim(),
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

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
        )}
      </div>
    </Modal>
  );
}
