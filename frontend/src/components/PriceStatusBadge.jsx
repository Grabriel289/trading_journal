/** Pill that shows freshness/source of a price quote. */
const COLOR = {
  LIVE:         'green',
  MANUAL:       'accent',
  STALE:        'partial',  // orange
  DISCONNECTED: 'red',
  NONE:         'muted',
};

export default function PriceStatusBadge({ status, source, fetchedAt }) {
  if (!status) return null;
  const cls = COLOR[status] || 'muted';
  const tip = [
    source ? `Source: ${source}` : null,
    fetchedAt ? `Updated: ${new Date(fetchedAt).toLocaleString()}` : null,
  ].filter(Boolean).join(' • ');
  return (
    <span className={`badge ${cls}`} title={tip || undefined}>
      {status}{source ? ` · ${source}` : ''}
    </span>
  );
}
