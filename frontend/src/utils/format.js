// Shared formatters. Prices need adaptive precision (a $0.00904 PENGU
// quote shouldn't render as "$0.01") while dollar aggregates like P&L
// stay at a fixed 2 decimals.

/**
 * Token-price formatter. Decimals scale with magnitude:
 *
 *   ≥ $1            →  2 decimals ($104,250.00, $1.23)
 *   $0.01 – $1      →  4 decimals ($0.5234)
 *   $0.0001 – $0.01 →  6 decimals ($0.009040)
 *   $0.000001 – …   →  8 decimals ($0.00001234)
 *   < $0.000001     → 10 decimals ($0.0000000123 — SHIB / PEPE class)
 */
export function fmtPrice(n) {
  if (n == null || n === '' || !isFinite(Number(n))) return '—';
  const x = Number(n);
  if (x === 0) return '$0.00';
  const abs = Math.abs(x);
  const sign = x < 0 ? '-' : '';

  let digits;
  if (abs >= 1)            digits = 2;
  else if (abs >= 0.01)    digits = 4;
  else if (abs >= 0.0001)  digits = 6;
  else if (abs >= 0.000001) digits = 8;
  else                     digits = 10;

  return `${sign}$${abs.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  })}`;
}

/**
 * Dollar-amount formatter (fixed 2 decimals).
 * Use for P&L, capital, fees, totals — anything that's a USD aggregate.
 * Use fmtPrice for per-unit token prices instead.
 */
export function fmtMoney(n) {
  if (n == null || n === '' || !isFinite(Number(n))) return '—';
  const x = Number(n);
  const sign = x < 0 ? '-' : '';
  return `${sign}$${Math.abs(x).toLocaleString(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  })}`;
}

/** Percentage with configurable decimals. */
export function fmtPct(n, digits = 2) {
  if (n == null || n === '' || !isFinite(Number(n))) return '—';
  return Number(n).toFixed(digits) + '%';
}

/** Token quantity (BTC, ETH, etc.) — up to 8 decimals, trailing zeros trimmed. */
export function fmtQty(n) {
  if (n == null || !isFinite(Number(n))) return '—';
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 8 });
}

/** Tailwind-ish red/green class for P&L numbers. */
export function pnlClass(n) {
  if (n == null) return '';
  const x = Number(n);
  if (x > 0) return 'green';
  if (x < 0) return 'red';
  return '';
}
