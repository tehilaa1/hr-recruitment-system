import { STATUS_STYLES } from '../constants/statuses';

/* Read-only status pill, same look as StatusSelect */
export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES['לא טופל'];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap ${style.badge}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${style.dot}`} />
      {status}
    </span>
  );
}
