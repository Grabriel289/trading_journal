import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';
import EquityCurve from '../components/EquityCurve.jsx';
import DrawdownChart from '../components/DrawdownChart.jsx';
import PriceStatusBadge from '../components/PriceStatusBadge.jsx';
import AssetAllocation from '../components/AssetAllocation.jsx';

const RANGES = ['1W', '1M', '3M', '1Y', 'ALL'];

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}
function fmtPct(n) {
  if (n == null) return '—';
  return Number(n).toFixed(2) + '%';
}
function pnlClass(n) {
  if (n == null) return '';
  const x = Number(n);
  if (x > 0) return 'green';
  if (x < 0) return 'red';
  return '';
}

export default function Dashboard() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [selectedId, setSelectedId] = useState('');
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [snapshots, setSnapshots] = useState([]);
  const [range, setRange] = useState('ALL');
  const [snapBusy, setSnapBusy] = useState(false);
  const [snapErr, setSnapErr] = useState(null);

  useEffect(() => {
    if (!selectedId && portfolios.length > 0) setSelectedId(portfolios[0].id);
  }, [portfolios, selectedId]);

  const loadOverview = useCallback(async () => {
    if (!selectedId) { setOverview(null); return; }
    setLoading(true); setError(null);
    try {
      setOverview(await api.getOverview(selectedId));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  const loadCurve = useCallback(async () => {
    if (!selectedId) { setSnapshots([]); return; }
    try {
      setSnapshots(await api.getEquityCurve(selectedId, range));
    } catch (e) {
      setSnapErr(e.message);
    }
  }, [selectedId, range]);

  useEffect(() => { loadOverview(); }, [loadOverview]);
  useEffect(() => { loadCurve(); }, [loadCurve]);

  async function takeSnapshot() {
    if (!selectedId) return;
    setSnapBusy(true); setSnapErr(null);
    try {
      await api.takeSnapshot(selectedId);
      await loadCurve();
    } catch (e) {
      setSnapErr(e.message);
    } finally {
      setSnapBusy(false);
    }
  }

  async function backfill() {
    if (!selectedId) return;
    if (!confirm(
      'Backfill historical snapshots?\n\nThis replays every order + deposit and fetches Binance daily klines to mark-to-market each day. Existing snapshots in the date range will be replaced.'
    )) return;
    setSnapBusy(true); setSnapErr(null);
    try {
      const r = await api.backfillSnapshots(selectedId);
      await loadCurve();
      const skipped = r.assets_skipped?.length
        ? ` (klines unavailable for: ${r.assets_skipped.join(', ')})`
        : '';
      setSnapErr(
        `✔ Backfilled ${r.snapshots_upserted} snapshots from ${r.first_date} to ${r.last_date}${skipped}`
      );
    } catch (e) {
      setSnapErr(e.message);
    } finally {
      setSnapBusy(false);
    }
  }

  async function editFunding(pos) {
    const current = pos.funding_accumulated || '0';
    const next = window.prompt(
      `Update accumulated funding for ${pos.asset} ${pos.direction} ${pos.leverage}x (positive = paid, negative = received):`,
      String(current)
    );
    if (next == null) return;
    if (Number.isNaN(Number(next))) { setError('Funding must be a number'); return; }
    try {
      await api.updateFunding(pos.order_id, next);
      await loadOverview();
    } catch (e) {
      setError(e.message);
    }
  }

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return (
      <div className="panel">
        <h2>Welcome to CryptoJournal</h2>
        <p className="muted">No portfolio yet. Head to <Link to="/setup">Setup</Link> to create one.</p>
      </div>
    );
  }

  const latestSnap = snapshots[snapshots.length - 1] || null;
  const deposited = overview?.total_deposited ?? 0;
  const equity = overview?.total_equity ?? 0;
  const totalReturn = deposited > 0 ? equity - deposited : 0;
  const totalReturnPct = deposited > 0 ? (totalReturn / deposited) * 100 : 0;

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
          {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
        </select>
      </div>

      {loading && <p className="muted">Loading overview…</p>}
      {error && <p className="error">{error}</p>}

      {overview && (
        <>
          {/* ───── Top stat cards: 3-3 symmetric grid ───── */}
          <div className="dash-stats">
            <div className="card">
              <div className="label">Total Equity</div>
              <div className="value">{fmtMoney(overview.total_equity)}</div>
              <div className={`card-sub ${pnlClass(totalReturn)}`}>
                {totalReturn >= 0 ? '+' : ''}{fmtMoney(totalReturn)} ({totalReturnPct >= 0 ? '+' : ''}{totalReturnPct.toFixed(2)}%)
              </div>
            </div>
            <div className="card">
              <div className="label">Cash Balance</div>
              <div className="value">{fmtMoney(overview.total_balance)}</div>
              <div className="card-sub muted">{deposited > 0 ? ((Number(overview.total_balance) / deposited) * 100).toFixed(1) + '% of deposited' : '—'}</div>
            </div>
            <div className="card">
              <div className="label">Unrealized P&L</div>
              <div className={`value ${pnlClass(overview.total_unrealized_pnl)}`}>
                {fmtMoney(overview.total_unrealized_pnl)}
              </div>
              <div className={`card-sub ${pnlClass(overview.total_unrealized_pnl)}`}>
                {overview.total_unrealized_pnl >= 0 ? '+' : ''}{deposited > 0 ? ((Number(overview.total_unrealized_pnl) / deposited) * 100).toFixed(2) : '0.00'}%
              </div>
            </div>
            <div className="card">
              <div className="label">Deposited</div>
              <div className="value">{fmtMoney(overview.total_deposited)}</div>
              <div className="card-sub muted">Total capital in</div>
            </div>
            <div className="card">
              <div className="label">Drawdown</div>
              <div className="value red">
                {latestSnap ? fmtPct(latestSnap.drawdown_pct) : '—'}
              </div>
              <div className="card-sub muted">From peak</div>
            </div>
            <div className="card">
              <div className="label">Open Trades</div>
              <div className="value">{overview.open_trades}</div>
              <div className="card-sub muted">
                {overview.sub_accounts.filter(s => s.type === 'SPOT').length} Spot · {overview.sub_accounts.filter(s => s.type === 'FUTURES').length} Futures
              </div>
            </div>
          </div>

          {/* ───── Equity Curve (full width) ───── */}
          <div className="panel">
            <div className="panel-header">
              <h2>Equity Curve</h2>
              <div className="panel-actions">
                <div className="range-group">
                  {RANGES.map((r) => (
                    <button
                      key={r} type="button"
                      className={range === r ? '' : 'secondary'}
                      onClick={() => setRange(r)}
                      style={{ padding: '5px 10px', fontSize: 12 }}
                    >{r}</button>
                  ))}
                </div>
                <button className="secondary" onClick={takeSnapshot} disabled={snapBusy}>
                  {snapBusy ? 'Working…' : 'Take Snapshot'}
                </button>
                <button className="secondary" onClick={backfill} disabled={snapBusy}>
                  {snapBusy ? 'Working…' : 'Backfill'}
                </button>
              </div>
            </div>
            {snapErr && <p className={snapErr.startsWith('✔') ? 'muted green' : 'error'}>{snapErr}</p>}
            <EquityCurve snapshots={snapshots} />
          </div>

          {/* ───── Asset Allocation + Drawdown side by side ───── */}
          <div className="dash-duo">
            <div className="panel" style={{ marginBottom: 0 }}>
              <h2>Asset Allocation</h2>
              <AssetAllocation overview={overview} />
            </div>
            {snapshots.length > 0 && (
              <div className="panel" style={{ marginBottom: 0 }}>
                <h2>Drawdown</h2>
                <DrawdownChart snapshots={snapshots} />
              </div>
            )}
          </div>

          {/* ───── Sub-Accounts + Open Positions side by side ───── */}
          <div className="dash-duo">
            <div className="panel" style={{ marginBottom: 0 }}>
              <h2>Sub-Accounts</h2>
              <table>
                <thead>
                  <tr>
                    <th>Name</th><th>Type</th><th>Initial</th>
                    <th>Cash</th><th>Equity</th><th>Unrealized</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.sub_accounts.map((s) => (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      <td><span className="badge">{s.type}</span></td>
                      <td>{fmtMoney(s.initial_capital)}</td>
                      <td>{fmtMoney(s.cash)}</td>
                      <td>{fmtMoney(s.equity)}</td>
                      <td className={pnlClass(s.unrealized_pnl)}>{fmtMoney(s.unrealized_pnl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel" style={{ marginBottom: 0 }}>
              <h2>Open Positions</h2>
              <table>
                <thead>
                  <tr>
                    <th>Asset</th><th>Side</th>
                    <th>Qty</th><th>Entry</th><th>Current</th>
                    <th>Value</th><th>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.sub_accounts.flatMap((s) =>
                    s.open_positions.map((pos, i) => {
                      const tag = pos.direction
                        ? `${pos.direction} ${pos.leverage}x`
                        : 'SPOT';
                      const cls = pos.direction === 'SHORT' ? 'red' : 'green';
                      return (
                        <tr key={`${s.id}-${i}`}>
                          <td style={{ fontWeight: 500 }}>{pos.asset}</td>
                          <td className={pos.direction ? cls : 'muted'}>{tag}</td>
                          <td>{Number(pos.quantity).toLocaleString(undefined, { maximumFractionDigits: 8 })}</td>
                          <td>{fmtMoney(pos.entry_price)}</td>
                          <td>
                            {fmtMoney(pos.current_price)}{' '}
                            {pos.price_status && (
                              <PriceStatusBadge status={pos.price_status} source={pos.price_source} />
                            )}
                          </td>
                          <td>{fmtMoney(pos.market_value)}</td>
                          <td className={pnlClass(pos.unrealized_pnl)}>
                            {fmtMoney(pos.unrealized_pnl)}
                            {pos.direction && (
                              <button
                                type="button" className="secondary tiny"
                                onClick={() => editFunding(pos)}
                                style={{ marginLeft: 6 }}
                                title="Edit funding"
                              >F</button>
                            )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                  {overview.sub_accounts.every((s) => s.open_positions.length === 0) && (
                    <tr><td colSpan={7} className="muted">No open positions.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
