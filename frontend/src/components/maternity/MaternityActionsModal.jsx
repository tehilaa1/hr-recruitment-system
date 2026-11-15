import { useState } from 'react';
import {
  AlertTriangle,
  Check,
  Copy,
  ExternalLink,
  FileText,
  Mail,
  MessageSquare,
  RotateCcw,
  Settings,
} from 'lucide-react';
import { buildMailComposeUrl, openInNewTab } from '../../utils/outlook';
import {
  MESSAGE_TYPES,
  buildMaternityMessage,
  buildTeamsAnnouncement,
  copyToClipboard,
} from '../../utils/maternityTemplates';
import Modal, { inputClass } from '../Modal';

function Section({ icon: Icon, iconClass, title, subtitle, children }) {
  return (
    <section className="border border-gray-100 rounded-2xl p-5 space-y-3">
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2 ${iconClass}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-gray-900">{title}</h3>
          <p className="text-xs text-gray-400">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function CopyButton({ text, label = 'העתקה' }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    if (await copyToClipboard(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } else {
      alert('ההעתקה נכשלה – סמנו את הטקסט והעתיקו ידנית');
    }
  };
  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex items-center gap-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 px-3 py-2 rounded-xl text-sm font-medium transition-colors"
    >
      {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
      {copied ? 'הועתק!' : label}
    </button>
  );
}

/* Choose between the short initial update and the full-details message */
function MessageTypePicker({ value, onChange }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" role="radiogroup" aria-label="סוג ההודעה">
      {MESSAGE_TYPES.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(t.key)}
            className={`text-right rounded-xl border px-3 py-2.5 transition-colors ${
              active
                ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-200'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <span className={`block text-sm font-semibold ${active ? 'text-blue-800' : 'text-gray-800'}`}>
              {t.label}
            </span>
            <span className="block text-xs text-gray-500 mt-0.5 leading-snug">{t.description}</span>
          </button>
        );
      })}
    </div>
  );
}

const buildAllMessages = (record, settings) =>
  Object.fromEntries(MESSAGE_TYPES.map((t) => [t.key, buildMaternityMessage(t.key, record, settings)]));

/* Per-employee workflow: update email (initial / full) to fixed recipients + Teams announcement */
export default function MaternityActionsModal({ record, settings, onClose, onOpenSettings }) {
  const [messageType, setMessageType] = useState(MESSAGE_TYPES[0].key);
  // Edits are kept per message type, so switching back and forth doesn't lose them
  const [messages, setMessages] = useState(() => buildAllMessages(record, settings));
  const [teamsText, setTeamsText] = useState(() => buildTeamsAnnouncement(record, settings));

  const { subject, body } = messages[messageType];
  const setField = (field) => (e) =>
    setMessages((prev) => ({ ...prev, [messageType]: { ...prev[messageType], [field]: e.target.value } }));
  const resetMessage = () =>
    setMessages((prev) => ({ ...prev, [messageType]: buildMaternityMessage(messageType, record, settings) }));
  const fresh = buildMaternityMessage(messageType, record, settings);
  const edited = fresh.subject !== subject || fresh.body !== body;

  const recipients = settings?.notify_recipients ?? [];
  const teamsUrl = settings?.teams_channel_url;

  const openOutlook = () =>
    openInNewTab(buildMailComposeUrl({ to: recipients, subject, body }));

  const copyAndOpenTeams = async () => {
    await copyToClipboard(teamsText);
    openInNewTab(teamsUrl);
  };

  return (
    <Modal
      title={`שליחת עדכונים – ${record.name}`}
      subtitle="ניתן לערוך את הטקסטים לפני השליחה"
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-5">
        {/* 1. Email to fixed recipients */}
        <Section
          icon={Mail}
          iconClass="bg-blue-50 text-blue-600"
          title="מייל עדכון לנמענים הקבועים"
          subtitle="נפתח כטיוטה ב-Outlook – שום דבר לא נשלח עד שתלחצו 'שלח'"
        >
          <MessageTypePicker value={messageType} onChange={setMessageType} />

          {recipients.length ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-gray-500">אל:</span>
              {recipients.map((r) => (
                <span key={r} dir="ltr" className="bg-gray-100 text-gray-700 rounded-full px-2.5 py-0.5 text-xs">
                  {r}
                </span>
              ))}
              <button
                type="button"
                onClick={onOpenSettings}
                className="text-xs text-blue-600 hover:underline mr-1"
              >
                עריכה
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span className="flex-1">לא הוגדרו נמענים קבועים – המייל ייפתח ללא נמענים.</span>
              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1 font-medium hover:underline"
              >
                <Settings className="h-3.5 w-3.5" />
                הגדרה
              </button>
            </div>
          )}

          <input
            value={subject}
            onChange={setField('subject')}
            aria-label="נושא"
            className={inputClass}
          />
          <textarea
            value={body}
            onChange={setField('body')}
            rows={messageType === 'full' ? 14 : 8}
            aria-label="תוכן המייל"
            className={`${inputClass} resize-y leading-relaxed`}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={openOutlook}
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-semibold transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
              פתיחה ב-Outlook
            </button>
            <CopyButton text={body} label="העתקת התוכן" />
            {edited && (
              <button
                type="button"
                onClick={resetMessage}
                title="חזרה לטקסט שנוצר מהתבנית"
                className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 px-2"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                איפוס
              </button>
            )}
            <button
              type="button"
              onClick={() => onOpenSettings('templates')}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-pink-600 mr-auto self-center"
            >
              <FileText className="h-3.5 w-3.5" />
              עריכת תבניות ההודעות
            </button>
          </div>
        </Section>

        {/* 2. Teams announcement */}
        <Section
          icon={MessageSquare}
          iconClass="bg-violet-50 text-violet-600"
          title="הודעת ברכה ל-Teams"
          subtitle="העתיקו והדביקו בערוץ הכללי"
        >
          <textarea
            value={teamsText}
            onChange={(e) => setTeamsText(e.target.value)}
            rows={7}
            aria-label="הודעת Teams"
            className={`${inputClass} resize-y leading-relaxed`}
          />
          <div className="flex flex-wrap gap-2">
            {teamsUrl ? (
              <button
                type="button"
                onClick={copyAndOpenTeams}
                className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-semibold transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                העתקה ופתיחת הערוץ ב-Teams
              </button>
            ) : (
              <button
                type="button"
                onClick={onOpenSettings}
                className="text-xs text-violet-600 hover:underline self-center"
              >
                הגדירו קישור לערוץ כדי לפתוח אותו ישירות
              </button>
            )}
            <CopyButton text={teamsText} label="העתקת ההודעה" />
          </div>
        </Section>
      </div>
    </Modal>
  );
}
