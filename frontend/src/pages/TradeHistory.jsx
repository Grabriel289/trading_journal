import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';
import { fmtPrice } from '../utils/format.js';

function fmtMoney(n) {
  if (n == null || n === '') return '—';
  return '$' + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}
function fmtPct(n) {
  if (n == null || n === '') return '—';
  return Number(n).toFixed(2) + '%';
}
function fmtQty(n) {
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 8 });
}
function fmtDuration(seconds) {
  if (seconds == null) return '—';
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
}
function pnlClass(n) {
  if (n == null) return '';
  const x = Number(n);
  if (x > 0) return 'green';
  if (x < 0) return 'red';
  return '';
}
function toLocalInput(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function TradeHistory() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState('');
  const [trades, setTrades] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [editing, setEditing] = useState(null);  // { order, datetime, price, fee, note }

  const subAccountById = useMemo(() => {
    const map = new Map();
    for (const p of portfolios) for (const s of p.sub_accounts) map.set(s.id, s);
    return map;
  }, [portfolios]);

  const subIds = useMemo(() => {
    const p = portfolios.find((x) => x.id === portfolioId);
    return p ? p.sub_accounts.map((s) => s.id) : [];
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId) return;
    let cancelled = false;
    (async () => {
      setLoading(true); setError(null);
      try {
        const [t, ...orderLists] = await Promise.all([
          api.getTrades(portfolioId),
          ...subIds.map((sid) => api.listOrders({ sub_account_id: sid })),
        ]);
        if (!cancelled) {
          setTrades(t);
          setOrders(orderLists.flat().sort((a, b) => new Date(b.datetime) - new Date(a.datetime)));
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [portfolioId, subIds.join(','), reloadKey]);

  const totals = useMemo(() => {
    if (trades.length === 0) return null;
    const winners = trades.filter((t) => Number(t.pnl_dollar) > 0);
    const losers = trades.filter((t) => Number(t.pnl_dollar) < 0);
    const sum = trades.reduce((acc, t) => acc + Number(t.pnl_dollar), 0);
    return {
      total: trades.length,
      winners: winners.length,
      losers: losers.length,
      win_rate: (winners.length / trades.length) * 100,
      net_pnl: sum,
    };
  }, [trades]);

  function startEdit(o) {
    setEditing({
      order: o,
      datetime: toLocalInput(o.datetime),
      price: o.price,
      fee: o.fee,
      note: o.note || '',
    });
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      const body = {};
      if (editing.datetime) body.when = new Date(editing.datetime).toISOString();
      if (editing.price !== editing.order.price) body.price = editing.price;
      if (editing.fee !== editing.order.fee)     body.fee = editing.fee;
      if (editing.note !== (editing.order.note || '')) body.note = editing.note;
      await api.updateOrder(editing.order.id, body);
      setEditing(null);
      setReloadKey((x) => x + 1);
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeOrder(o) {
    const label = `${o.side} ${fmtQty(o.quantity)} ${o.asset} @ ${fmtPrice(o.price)}`;
    if (!confirm(`Delete order?\n\n${label}\n\n${o.side === 'BUY' ? 'Will fail if it has linked sells.' : 'Linked buy will reopen by this quantity.'}`)) return;
    try {
      await api.deleteOrder(o.id);
      setReloadKey((x) => x + 1);
    } catch (e) {
      try {
        const j = JSON.parse(e.message);
        setError(j.detail || e.message);
      } catch { setError(e.message); }
    }
  }

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return <div className="panel"><p>Create a portfolio via <Link to="/setup">Setup</Link>.</p></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Trade History</h1>
        <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
          {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
        </select>
      </div>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}

      {totals && (
        <div className="cards">
          <div className="card">
            <div className="label">Closed Trades</div>
            <div className="value">{totals.total}</div>
          </div>
          <div className="card">
            <div className="label">Win Rate</div>
            <div className="value">{fmtPct(totals.win_rate)}</div>
          </div>
          <div className="card">
            <div className="label">Net Realized P&L</div>
            <div className={`value ${pnlClass(totals.net_pnl)}`}>{fmtMoney(totals.net_pnl)}</div>
          </div>
          <div className="card">
            <div className="label">Winners / Losers</div>
            <div className="value">{totals.winners} / {totals.losers}</div>
          </div>
        </div>
      )}

      <div className="panel">
        <h2>Closed Round-Trips</h2>
        {trades.length === 0 ? (
          <p className="muted">No closed trades yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Closed</th><th>Asset</th><th>Side</th><th>Sub-Account</th><th>Qty</th>
                <th>Entry</th><th>Exit</th><th>Duration</th>
                <th>Gross P&L</th><th>Funding</th><th>Net P&L $</th><th>Net P&L %</th><th>Fees</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => {
                const tag = t.direction ? `${t.direction} ${t.leverage}x` : 'SPOT';
                const tagClass = t.direction === 'SHORT' ? 'red' : (t.direction === 'LONG' ? 'green' : 'muted');
                return (
                  <tr key={t.exit_order_id}>
                    <td>{new Date(t.exit_datetime).toLocaleString()}</td>
                    <td>{t.asset}</td>
                    <td><span className={`badge ${tagClass}`}>{tag}</span></td>
                    <td>{subAccountById.get(t.sub_account_id)?.name || '—'}</td>
                    <td>{fmtQty(t.quantity)}</td>
                    <td>{fmtPrice(t.entry_price)}</td>
                    <td>{fmtPrice(t.exit_price)}</td>
                    <td>{fmtDuration(t.holding_seconds)}</td>
                    <td className={pnlClass(t.gross_pnl)}>{fmtMoney(t.gross_pnl)}</td>
                    <td className={pnlClass(-Number(t.funding_pnl))}>{fmtMoney(t.funding_pnl)}</td>
                    <td className={pnlClass(t.pnl_dollar)}>{fmtMoney(t.pnl_dollar)}</td>
                    <td className={pnlClass(t.pnl_dollar)}>{fmtPct(t.pnl_percent)}</td>
                    <td>{fmtMoney(t.fee_total)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h2>All Orders</h2>
        {orders.length === 0 ? (
          <p className="muted">No orders yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th><th>Sub-Account</th><th>Asset</th><th>Side</th>
                <th>Type</th><th>Venue</th>
                <th>Qty</th><th>Price</th><th>Total</th><th>Fee</th>
                <th>Tags</th>
                <th>Status</th><th>Remaining</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>{new Date(o.datetime).toLocaleString()}</td>
                  <td>{subAccountById.get(o.sub_account_id)?.name || '—'}</td>
                  <td>{o.asset}</td>
                  <td><span className={`badge ${o.side === 'BUY' ? 'green' : 'red'}`}>{o.side}</span></td>
                  <td className="muted" style={{ fontSize: 11 }}>{o.order_type || '—'}</td>
                  <td className="muted" style={{ fontSize: 11 }}>{o.execution_venue || '—'}</td>
                  <td>{fmtQty(o.quantity)}</td>
                  <td>{fmtPrice(o.price)}</td>
                  <td>{fmtMoney(o.total_value)}</td>
                  <td>{fmtMoney(o.fee)}{o.fee_currency ? <span className="muted" style={{ fontSize: 10 }}> {o.fee_currency}</span> : null}</td>
                  <td>
                    {(o.tags || []).map((t) => (
                      <span key={t.id} className="badge" style={{ background: t.color, color: '#07080d', marginRight: 2 }}>{t.name}</span>
                    ))}
                  </td>
                  <td><span className="badge muted">{o.status}</span></td>
                  <td>{fmtQty(o.remaining_quantity)}</td>
                  <td className="actions">
                    <div className="btn-row">
                      <button className="secondary tiny" onClick={() => startEdit(o)}>Edit</button>
                      <button className="danger tiny" onClick={() => removeOrder(o)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editing && (
        <div className="modal-backdrop" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit {editing.order.side} order</h2>
            <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
              Quantity isn't editable — delete and re-create to change it.
            </p>
            <div className="form-row">
              <label>Datetime</label>
              <input type="datetime-local"
                value={editing.datetime}
                onChange={(e) => setEditing({ ...editing, datetime: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Price</label>
              <input type="number" step="any"
                value={editing.price}
                onChange={(e) => setEditing({ ...editing, price: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Fee</label>
              <input type="number" step="any"
                value={editing.fee}
                onChange={(e) => setEditing({ ...editing, fee: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Note</label>
              <input value={editing.note}
                onChange={(e) => setEditing({ ...editing, note: e.target.value })} />
            </div>
            <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setEditing(null)}>Cancel</button>
              <button onClick={saveEdit}>Save</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
