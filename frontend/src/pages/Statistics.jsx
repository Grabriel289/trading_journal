import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, PointElement, Tooltip, Legend,
} from 'chart.js';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';
import EquityCurve from '../components/EquityCurve.jsx';
import DrawdownChart from '../components/DrawdownChart.jsx';
import DailyPnlBars from '../components/DailyPnlBars.jsx';

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, Tooltip, Legend);

const TABS = ['Summary', 'Trades', 'Hourly', 'Daily', 'Risk of Ruin', 'Duration', 'MAE/MFE', 'Charts'];

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}
function fmtPct(n, digits = 2) {
  if (n == null) return '—';
  return Number(n).toFixed(digits) + '%';
}
function fmtNum(n, digits = 4) {
  if (n == null) return '—';
  return Number(n).toFixed(digits);
}
function pnlClass(n) {
  if (n == null) return '';
  const x = Number(n);
  if (x > 0) return 'green';
  if (x < 0) return 'red';
  return '';
}

function StatCell({ label, value, cls = '' }) {
  return (
    <div className="adv-stats-cell">
      <span className="adv-stats-label">{label}</span>
      <span className={`adv-stats-value ${cls}`}>{value}</span>
    </div>
  );
}

function ProfitabilityBar({ winners, losers }) {
  const total = winners + losers;
  if (total === 0) {
    return <span className="adv-stats-value muted">—</span>;
  }
  const winPct = (winners / total) * 100;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="profitability-bar" title={`${winners} wins / ${losers} losses`}>
        <div className="win"  style={{ width: `${winPct}%` }} />
        <div className="loss" style={{ width: `${100 - winPct}%` }} />
      </div>
    </div>
  );
}

function SummaryTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  const wr = data.win_rate;
  const awl = data.avg_win_loss;
  const dd = data.drawdown;
  const lw = data.long_win_rate;
  const sw = data.short_win_rate;
  const bw = data.best_worst;

  const longCell = (
    <span>
      <span className="adv-stats-aux">({lw.winners}/{lw.total}) </span>
      {fmtPct(lw.win_rate)}
    </span>
  );
  const shortCell = sw.total > 0 ? (
    <span>
      <span className="adv-stats-aux">({sw.winners}/{sw.total}) </span>
      {fmtPct(sw.win_rate)}
    </span>
  ) : '—';

  const bestDate  = bw.best_at  ? new Date(bw.best_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : null;
  const worstDate = bw.worst_at ? new Date(bw.worst_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : null;
  const bestCell = bw.best_dollar != null
    ? <span><span className="adv-stats-aux">{bestDate ? `(${bestDate}) ` : ''}</span>{fmtMoney(bw.best_dollar)}</span>
    : '—';
  const worstCell = bw.worst_dollar != null
    ? <span><span className="adv-stats-aux">{worstDate ? `(${worstDate}) ` : ''}</span>{fmtMoney(bw.worst_dollar)}</span>
    : '—';

  const zScoreCell = data.z_score != null ? (
    <span>
      {fmtNum(data.z_score, 3)}
      {data.z_score_probability != null && (
        <span className="adv-stats-aux"> ({fmtPct(data.z_score_probability * 100)})</span>
      )}
    </span>
  ) : '—';

  const maxDdCell = (
    <span>
      <span className="adv-stats-aux">({fmtPct(dd.max_dd_pct)}) </span>
      <span className="red">{fmtMoney(dd.max_dd_dollar)}</span>
    </span>
  );

  // Layout: 3 columns × N rows. Order matches the reference pattern —
  // general/trade meta on the left, sides + best/worst in the middle, ratios on the right.
  const rows = [
    [
      { label: 'Trades',         value: wr.total },
      { label: 'Longs Won',      value: longCell },
      { label: 'Profit Factor',  value: data.profit_factor != null ? fmtNum(data.profit_factor, 2) : '—' },
    ],
    [
      { label: 'Profitability',  value: <ProfitabilityBar winners={wr.winners} losers={wr.losers} /> },
      { label: 'Shorts Won',     value: shortCell },
      { label: 'Standard Deviation', value: data.std_deviation != null ? fmtMoney(data.std_deviation) : '—' },
    ],
    [
      { label: 'Net Profit',     value: fmtMoney(data.total_net_profit), cls: pnlClass(data.total_net_profit) },
      { label: 'Best Trade',     value: bestCell, cls: 'green' },
      { label: 'Sharpe Ratio',   value: data.sharpe != null ? fmtNum(data.sharpe, 3) : '—' },
    ],
    [
      { label: 'Expectancy',     value: fmtMoney(awl.expectancy_dollar), cls: pnlClass(awl.expectancy_dollar) },
      { label: 'Worst Trade',    value: worstCell, cls: 'red' },
      { label: 'Sortino Ratio',  value: data.sortino != null ? fmtNum(data.sortino, 3) : '—' },
    ],
    [
      { label: 'Average Win',    value: fmtMoney(awl.avg_win_dollar),   cls: 'green' },
      { label: 'Max Consecutive Wins',   value: data.streaks.max_consecutive_wins,   cls: 'green' },
      { label: 'Calmar Ratio',   value: data.calmar != null ? fmtNum(data.calmar, 3) : '—' },
    ],
    [
      { label: 'Average Loss',   value: fmtMoney(awl.avg_loss_dollar),  cls: 'red' },
      { label: 'Max Consecutive Losses', value: data.streaks.max_consecutive_losses, cls: 'red' },
      { label: 'Z-Score (Probability)',  value: zScoreCell },
    ],
    [
      { label: 'Avg Win %',      value: fmtPct(awl.avg_win_pct),  cls: 'green' },
      { label: 'Max Drawdown',   value: maxDdCell },
      { label: 'Annual Return',  value: data.annual_return != null ? fmtPct(data.annual_return * 100) : '—' },
    ],
    [
      { label: 'Avg Loss %',     value: fmtPct(awl.avg_loss_pct), cls: 'red' },
      { label: 'Current Drawdown', value: fmtPct(dd.current_dd_pct) },
      { label: 'AHPR',           value: data.ahpr != null ? fmtNum(data.ahpr, 5) : '—' },
    ],
    [
      { label: 'Recovery Factor', value: data.recovery_factor != null ? fmtNum(data.recovery_factor, 2) : '—' },
      { label: 'Peak Equity',    value: fmtMoney(dd.peak_equity) },
      { label: 'GHPR',           value: data.ghpr != null ? fmtNum(data.ghpr, 5) : '—' },
    ],
    [
      { label: 'Breakeven',      value: wr.breakeven },
      { label: 'Max DD Duration', value: `${dd.max_dd_duration_days} days` },
      { label: '', value: '' },  // spacer
    ],
  ];

  return (
    <div className="adv-stats">
      {rows.map((cols, rowIdx) => (
        <div className="adv-stats-row" key={rowIdx}>
          {cols.map((c, colIdx) => (
            <StatCell key={colIdx} label={c.label} value={c.value} cls={c.cls || ''} />
          ))}
        </div>
      ))}
    </div>
  );
}

function TradesTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  if (data.length === 0) return <p className="muted">No closed trades.</p>;
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Asset</th>
            <th>Longs (W%)</th><th>Long P&L</th>
            <th>Shorts (W%)</th><th>Short P&L</th>
            <th>Total (W%)</th><th>Total P&L</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.asset}>
              <td><strong>{row.asset}</strong></td>
              <td>{row.longs_count} ({fmtPct(row.longs_win_rate)})</td>
              <td className={pnlClass(row.longs_pnl)}>{fmtMoney(row.longs_pnl)}</td>
              <td>{row.shorts_count} ({fmtPct(row.shorts_win_rate)})</td>
              <td className={pnlClass(row.shorts_pnl)}>{fmtMoney(row.shorts_pnl)}</td>
              <td>{row.total_count} ({fmtPct(row.total_win_rate)})</td>
              <td className={pnlClass(row.total_pnl)}>{fmtMoney(row.total_pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const CHART_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#e6edf3' } } },
  scales: {
    x: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' } },
    y: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' } },
  },
};

function HourlyTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  const labels = data.map((r) => `${String(r.hour).padStart(2, '0')}:00`);
  const counts = {
    labels,
    datasets: [{
      label: 'Trade count',
      data: data.map((r) => r.count),
      backgroundColor: '#2962ff',
    }],
  };
  const profits = {
    labels,
    datasets: [{
      label: 'P&L $',
      data: data.map((r) => Number(r.profit)),
      backgroundColor: data.map((r) => Number(r.profit) >= 0 ? '#26a69a' : '#ef5350'),
    }],
  };
  return (
    <>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Trades by Hour (UTC)</h2>
        <div style={{ height: 240 }}><Bar data={counts} options={CHART_OPTS} /></div>
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>P&L by Hour</h2>
        <div style={{ height: 240 }}><Bar data={profits} options={CHART_OPTS} /></div>
      </div>
    </>
  );
}

function fmtDuration(seconds) {
  if (seconds == null) return '—';
  const s = Math.max(0, Math.floor(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
  if (s < 86400) return `${(s / 3600).toFixed(1)}h`;
  return `${(s / 86400).toFixed(1)}d`;
}

function RiskOfRuinTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  const usable = data.some((r) => r.consecutive_losses != null);
  if (!usable) return (
    <p className="muted">
      Need at least one losing trade with a defined avg loss % to compute Risk of Ruin.
    </p>
  );
  return (
    <div className="panel">
      <h2 style={{ fontSize: 14 }}>Risk of Ruin Table</h2>
      <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Probability of an N-loss streak large enough to drop your equity by each level.
        Each loss removes ~avg_loss_% of remaining capital.
      </p>
      <table>
        <thead>
          <tr>
            <th>Equity Loss</th>
            <th>Consecutive Losses Needed</th>
            <th>Probability</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r) => (
            <tr key={r.loss_pct}>
              <td className="red">{Number(r.loss_pct).toFixed(0)}%</td>
              <td>{r.consecutive_losses == null ? '∞' : r.consecutive_losses}</td>
              <td>
                {r.probability == null
                  ? '—'
                  : (r.probability < 0.0001
                    ? '< 0.01%'
                    : (r.probability * 100).toFixed(4) + '%')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DurationTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  if (!data.points || data.points.length === 0) {
    return <p className="muted">No closed trades.</p>;
  }
  const winners = data.points.filter((p) => Number(p.pnl_dollar) > 0);
  const losers = data.points.filter((p) => Number(p.pnl_dollar) < 0);
  const breakeven = data.points.filter((p) => Number(p.pnl_dollar) === 0);
  const toPoint = (p) => ({ x: p.duration_seconds / 3600, y: Number(p.pnl_percent) });
  const chartData = {
    datasets: [
      { label: 'Winners', data: winners.map(toPoint), backgroundColor: '#26a69a', pointRadius: 5 },
      { label: 'Losers',  data: losers.map(toPoint),  backgroundColor: '#ef5350', pointRadius: 5 },
      ...(breakeven.length > 0 ? [{ label: 'BE', data: breakeven.map(toPoint), backgroundColor: '#8b949e', pointRadius: 4 }] : []),
    ],
  };
  const opts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#e6edf3' } },
      tooltip: {
        callbacks: {
          label: (ctx) => `Duration ${fmtDuration(ctx.parsed.x * 3600)}, P&L ${ctx.parsed.y.toFixed(2)}%`,
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        title: { display: true, text: 'Duration (hours)', color: '#8b949e' },
        ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' },
      },
      y: {
        title: { display: true, text: 'P&L %', color: '#8b949e' },
        ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' },
      },
    },
  };
  return (
    <>
      <div className="cards">
        <div className="card"><div className="label">Avg Duration</div><div className="value">{fmtDuration(data.avg_seconds)}</div></div>
        <div className="card"><div className="label">Median</div><div className="value">{fmtDuration(data.median_seconds)}</div></div>
        <div className="card"><div className="label">Longest</div><div className="value">{fmtDuration(data.longest_seconds)}</div></div>
        <div className="card"><div className="label">Shortest</div><div className="value">{fmtDuration(data.shortest_seconds)}</div></div>
        <div className="card"><div className="label">Avg Winner</div><div className="value green">{fmtDuration(data.avg_winner_seconds)}</div></div>
        <div className="card"><div className="label">Avg Loser</div><div className="value red">{fmtDuration(data.avg_loser_seconds)}</div></div>
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Duration vs P&L %</h2>
        <div style={{ height: 360 }}><Scatter data={chartData} options={opts} /></div>
      </div>
    </>
  );
}

function ChartsTab({ snapshots }) {
  if (!snapshots || snapshots.length === 0) {
    return (
      <p className="muted">
        No snapshots yet — click <strong>Backfill</strong> on the Dashboard to reconstruct
        historical snapshots from your trade log, or <strong>Take Snapshot</strong> to record a daily one.
      </p>
    );
  }
  return (
    <>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Equity / Balance / Deposited</h2>
        <EquityCurve snapshots={snapshots} />
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Daily P&L</h2>
        <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
          Day-over-day equity change (excluding deposits/withdrawals).
        </p>
        <DailyPnlBars snapshots={snapshots} height={260} />
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Drawdown Area</h2>
        <DrawdownChart snapshots={snapshots} height={260} />
      </div>
    </>
  );
}

function MaeMfeTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  if (!data.points || data.points.length === 0) {
    return (
      <p className="muted">
        No data — need closed trades and Binance kline history.
        {data && data.skipped > 0 && ` (${data.skipped} trade(s) skipped — kline fetch failed.)`}
      </p>
    );
  }
  const baseOpts = (xLabel) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: '#e6edf3' } },
      tooltip: {
        callbacks: {
          label: (ctx) => `${xLabel} ${ctx.parsed.x.toFixed(2)}%, P&L ${ctx.parsed.y.toFixed(2)}%`,
        },
      },
    },
    scales: {
      x: {
        type: 'linear',
        title: { display: true, text: xLabel + ' (%)', color: '#8b949e' },
        ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' },
      },
      y: {
        title: { display: true, text: 'Realized P&L %', color: '#8b949e' },
        ticks: { color: '#8b949e' }, grid: { color: 'rgba(138,148,158,0.08)' },
      },
    },
  });
  const winners = data.points.filter((p) => Number(p.pnl_pct) > 0);
  const losers = data.points.filter((p) => Number(p.pnl_pct) < 0);
  const maePts = (rows) => rows.map((p) => ({ x: Number(p.mae_pct), y: Number(p.pnl_pct) }));
  const mfePts = (rows) => rows.map((p) => ({ x: Number(p.mfe_pct), y: Number(p.pnl_pct) }));
  const maeData = {
    datasets: [
      { label: 'Winners', data: maePts(winners), backgroundColor: '#26a69a', pointRadius: 5 },
      { label: 'Losers',  data: maePts(losers),  backgroundColor: '#ef5350', pointRadius: 5 },
    ],
  };
  const mfeData = {
    datasets: [
      { label: 'Winners', data: mfePts(winners), backgroundColor: '#26a69a', pointRadius: 5 },
      { label: 'Losers',  data: mfePts(losers),  backgroundColor: '#ef5350', pointRadius: 5 },
    ],
  };
  return (
    <>
      <div className="cards">
        <div className="card"><div className="label">Avg MAE</div><div className="value red">{data.avg_mae_pct != null ? fmtPct(data.avg_mae_pct) : '—'}</div></div>
        <div className="card"><div className="label">Avg MFE</div><div className="value green">{data.avg_mfe_pct != null ? fmtPct(data.avg_mfe_pct) : '—'}</div></div>
        <div className="card"><div className="label">Trades Plotted</div><div className="value">{data.points.length}</div></div>
        <div className="card"><div className="label">Skipped</div><div className="value">{data.skipped}</div></div>
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>MAE Scatter — worst price during hold vs realized P&L</h2>
        <div style={{ height: 320 }}><Scatter data={maeData} options={baseOpts('MAE')} /></div>
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>MFE Scatter — best price during hold vs realized P&L</h2>
        <div style={{ height: 320 }}><Scatter data={mfeData} options={baseOpts('MFE')} /></div>
      </div>
      {data.skipped > 0 && (
        <p className="muted" style={{ fontSize: 12 }}>
          {data.skipped} trade(s) skipped — Binance had no klines for that symbol/window.
        </p>
      )}
    </>
  );
}

function DailyTab({ data }) {
  if (!data) return <p className="muted">Loading…</p>;
  const labels = data.map((r) => r.name);
  const counts = {
    labels,
    datasets: [
      { label: 'Winners', data: data.map((r) => r.winners), backgroundColor: '#26a69a' },
      { label: 'Losers',  data: data.map((r) => r.losers),  backgroundColor: '#ef5350' },
    ],
  };
  const profits = {
    labels,
    datasets: [{
      label: 'P&L $',
      data: data.map((r) => Number(r.profit)),
      backgroundColor: data.map((r) => Number(r.profit) >= 0 ? '#26a69a' : '#ef5350'),
    }],
  };
  return (
    <>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>Winners vs Losers by Weekday</h2>
        <div style={{ height: 260 }}><Bar data={counts} options={CHART_OPTS} /></div>
      </div>
      <div className="panel">
        <h2 style={{ fontSize: 14 }}>P&L by Weekday</h2>
        <div style={{ height: 240 }}><Bar data={profits} options={CHART_OPTS} /></div>
      </div>
      <div className="panel">
        <table>
          <thead><tr><th>Day</th><th>Winners</th><th>Losers</th><th>Profit</th></tr></thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.weekday}>
                <td>{r.name}</td><td className="green">{r.winners}</td>
                <td className="red">{r.losers}</td>
                <td className={pnlClass(r.profit)}>{fmtMoney(r.profit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function Statistics() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState('');
  const [subAccountId, setSubAccountId] = useState('');
  const [tab, setTab] = useState('Summary');
  const [data, setData] = useState({
    Summary: null, Trades: null, Hourly: null, Daily: null,
    'Risk of Ruin': null, Duration: null, 'MAE/MFE': null, Charts: null,
  });
  const [maeMfeLoading, setMaeMfeLoading] = useState(false);
  const [error, setError] = useState(null);

  const subAccounts = useMemo(() => {
    const p = portfolios.find((x) => x.id === portfolioId);
    return p ? p.sub_accounts : [];
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId) return;
    let cancelled = false;
    const params = { portfolio_id: portfolioId };
    if (subAccountId) params.sub_account_id = subAccountId;

    (async () => {
      try {
        const [summary, breakdown, hourly, daily, ror, duration, snapshots] = await Promise.all([
          api.statsSummary(params),
          api.statsBreakdown(params),
          api.statsHourly(params),
          api.statsDaily(params),
          api.statsRisk(params),
          api.statsDuration(params),
          api.getEquityCurve(portfolioId, 'ALL'),
        ]);
        if (!cancelled) {
          setData((prev) => ({
            ...prev,
            Summary: summary, Trades: breakdown, Hourly: hourly, Daily: daily,
            'Risk of Ruin': ror, Duration: duration, Charts: snapshots,
          }));
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [portfolioId, subAccountId]);

  // MAE/MFE is heavy (one Binance kline call per trade); load lazily on tab open.
  useEffect(() => {
    if (tab !== 'MAE/MFE' || !portfolioId || data['MAE/MFE']) return;
    let cancelled = false;
    const params = { portfolio_id: portfolioId };
    if (subAccountId) params.sub_account_id = subAccountId;
    (async () => {
      setMaeMfeLoading(true);
      try {
        const d = await api.statsMaeMfe(params);
        if (!cancelled) setData((prev) => ({ ...prev, 'MAE/MFE': d }));
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setMaeMfeLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [tab, portfolioId, subAccountId, data]);

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return <div className="panel"><p>Create a portfolio via <Link to="/setup">Setup</Link>.</p></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Statistics</h1>
        <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
          {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={subAccountId} onChange={(e) => setSubAccountId(e.target.value)}>
          <option value="">All sub-accounts</option>
          {subAccounts.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.type})</option>)}
        </select>
      </div>

      <div style={{
        display: 'flex', gap: 4, marginBottom: 16,
        borderBottom: '1px solid var(--border)',
        overflowX: 'auto', paddingBottom: 1,
      }}>
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={tab === t ? '' : 'secondary'}
            style={{
              borderRadius: '4px 4px 0 0',
              padding: '8px 14px',
              borderBottom: tab === t ? '2px solid var(--accent)' : 'none',
              flexShrink: 0,
            }}
          >{t}</button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {tab === 'Summary' && <SummaryTab data={data.Summary} />}
      {tab === 'Trades'  && <TradesTab data={data.Trades} />}
      {tab === 'Hourly'  && <HourlyTab data={data.Hourly} />}
      {tab === 'Daily'   && <DailyTab data={data.Daily} />}
      {tab === 'Risk of Ruin' && <RiskOfRuinTab data={data['Risk of Ruin']} />}
      {tab === 'Duration' && <DurationTab data={data.Duration} />}
      {tab === 'MAE/MFE' && (
        maeMfeLoading
          ? <p className="muted">Fetching kline history from Binance — this can take a few seconds…</p>
          : <MaeMfeTab data={data['MAE/MFE']} />
      )}
      {tab === 'Charts' && <ChartsTab snapshots={data.Charts} />}

      {subAccountId && tab === 'Summary' && (
        <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
          Note: Sharpe / Sortino / Calmar / drawdown are portfolio-level only —
          omitted when filtering by sub-account.
        </p>
      )}
    </>
  );
}
