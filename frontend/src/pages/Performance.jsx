import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, PointElement, LineElement,
  Tooltip, Legend, Filler,
} from 'chart.js';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';

ChartJS.register(
  CategoryScale, LinearScale, BarElement, PointElement, LineElement,
  Tooltip, Legend, Filler,
);

// ── Formatters ───────────────────────────────────────────────────────
function fmtMoney(n) {
  if (n == null || n === '') return '—';
  const x = Number(n);
  const sign = x < 0 ? '-' : '';
  return `${sign}$${Math.abs(x).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;
}
function fmtPct(n, digits = 2) {
  if (n == null || n === '') return '—';
  return Number(n).toFixed(digits) + '%';
}
function fmtRatio(n, digits = 3) {
  if (n == null || n === '') return '—';
  return Number(n).toFixed(digits);
}
function fmtInt(n) {
  if (n == null || n === '') return '—';
  return Number(n).toLocaleString();
}
function fmtHold(seconds) {
  if (seconds == null) return '—';
  const s = Number(seconds);
  if (s < 60) return `${s.toFixed(0)}s`;
  if (s < 3600) return `${(s / 60).toFixed(1)}m`;
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

// ── Sortable header ──────────────────────────────────────────────────
function SortHeader({ label, sortKey, currentKey, currentDir, onSort, align = 'left' }) {
  const active = currentKey === sortKey;
  const arrow = active ? (currentDir === 'asc' ? ' ▲' : ' ▼') : '';
  return (
    <th
      className="sortable"
      style={{ cursor: 'pointer', textAlign: align, userSelect: 'none' }}
      onClick={() => onSort(sortKey)}
    >
      {label}{arrow}
    </th>
  );
}

function useSort(defaultKey, defaultDir = 'desc') {
  const [sortKey, setSortKey] = useState(defaultKey);
  const [sortDir, setSortDir] = useState(defaultDir);
  const toggle = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };
  return { sortKey, sortDir, toggle };
}

function sortRows(rows, key, dir) {
  if (!key) return rows;
  const mult = dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mult;
    const an = Number(av), bn = Number(bv);
    if (!isNaN(an) && !isNaN(bn)) return (an - bn) * mult;
    return String(av).localeCompare(String(bv)) * mult;
  });
}

// ── Section 1: Asset Performance ─────────────────────────────────────
function AssetPerformanceSection({ rows }) {
  const { sortKey, sortDir, toggle } = useSort('contribution_pct', 'desc');
  if (!rows) return <div className="panel"><h2>Asset Performance</h2><p className="muted">Loading…</p></div>;
  if (rows.length === 0) {
    return <div className="panel"><h2>Asset Performance</h2><p className="muted">No buy orders yet.</p></div>;
  }

  const sorted = sortRows(rows, sortKey, sortDir);

  // Totals row
  const totals = rows.reduce((acc, r) => ({
    total_trades: acc.total_trades + r.total_trades,
    open_trades: acc.open_trades + r.open_trades,
    closed_trades: acc.closed_trades + r.closed_trades,
    total_invested: acc.total_invested + Number(r.total_invested),
    realized_pnl: acc.realized_pnl + Number(r.realized_pnl),
    unrealized_pnl: acc.unrealized_pnl + Number(r.unrealized_pnl),
    total_pnl: acc.total_pnl + Number(r.total_pnl),
    current_value: acc.current_value + Number(r.current_value),
  }), {
    total_trades: 0, open_trades: 0, closed_trades: 0,
    total_invested: 0, realized_pnl: 0, unrealized_pnl: 0,
    total_pnl: 0, current_value: 0,
  });
  const totalReturnPct = totals.total_invested > 0
    ? (totals.total_pnl / totals.total_invested) * 100
    : 0;
  const totalContributionPct = rows.reduce(
    (a, r) => a + Number(r.contribution_pct), 0
  );

  // Bar chart — sorted by contribution % ascending (most negative bottom in chart =
  // visually top). For a horizontal bar chart, higher index = top of chart.
  const chartRows = [...rows].sort(
    (a, b) => Number(a.contribution_pct) - Number(b.contribution_pct)
  );
  const chartData = {
    labels: chartRows.map((r) => r.symbol),
    datasets: [{
      data: chartRows.map((r) => Number(r.contribution_pct)),
      backgroundColor: chartRows.map((r) =>
        Number(r.contribution_pct) >= 0 ? '#22c55e' : '#ef4444'
      ),
      borderWidth: 0,
    }],
  };
  const chartOpts = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.parsed.x.toFixed(2)}% contribution`,
        },
      },
    },
    scales: {
      x: {
        ticks: { color: '#8b949e', callback: (v) => v + '%' },
        grid: { color: 'rgba(138,148,158,0.08)' },
      },
      y: {
        ticks: { color: '#cbd5e1' },
        grid: { display: false },
      },
    },
  };

  return (
    <div className="panel">
      <h2>Asset Performance — Contribution to Portfolio</h2>
      <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
        Which coins drive return? Contribution % = total P&L ÷ portfolio NAV.
        Click column headers to sort.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <SortHeader label="Symbol" sortKey="symbol" currentKey={sortKey} currentDir={sortDir} onSort={toggle} />
              <SortHeader label="Total" sortKey="total_trades" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Open" sortKey="open_trades" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Closed" sortKey="closed_trades" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Invested" sortKey="total_invested" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Realized" sortKey="realized_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Unrealized" sortKey="unrealized_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Total P&L" sortKey="total_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Current Value" sortKey="current_value" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Return %" sortKey="return_pct" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Contribution %" sortKey="contribution_pct" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.symbol}>
                <td><strong>{r.symbol}</strong></td>
                <td style={{ textAlign: 'right' }}>{fmtInt(r.total_trades)}</td>
                <td style={{ textAlign: 'right' }}>{fmtInt(r.open_trades)}</td>
                <td style={{ textAlign: 'right' }}>{fmtInt(r.closed_trades)}</td>
                <td style={{ textAlign: 'right' }}>{fmtMoney(r.total_invested)}</td>
                <td className={pnlClass(r.realized_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(r.realized_pnl)}</td>
                <td className={pnlClass(r.unrealized_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(r.unrealized_pnl)}</td>
                <td className={pnlClass(r.total_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(r.total_pnl)}</td>
                <td style={{ textAlign: 'right' }}>{fmtMoney(r.current_value)}</td>
                <td className={pnlClass(r.return_pct)} style={{ textAlign: 'right' }}>{fmtPct(r.return_pct)}</td>
                <td className={pnlClass(r.contribution_pct)} style={{ textAlign: 'right' }}>{fmtPct(r.contribution_pct)}</td>
              </tr>
            ))}
            <tr className="total-row">
              <td><strong>TOTAL</strong></td>
              <td style={{ textAlign: 'right' }}>{fmtInt(totals.total_trades)}</td>
              <td style={{ textAlign: 'right' }}>{fmtInt(totals.open_trades)}</td>
              <td style={{ textAlign: 'right' }}>{fmtInt(totals.closed_trades)}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(totals.total_invested)}</td>
              <td className={pnlClass(totals.realized_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(totals.realized_pnl)}</td>
              <td className={pnlClass(totals.unrealized_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(totals.unrealized_pnl)}</td>
              <td className={pnlClass(totals.total_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(totals.total_pnl)}</td>
              <td style={{ textAlign: 'right' }}>{fmtMoney(totals.current_value)}</td>
              <td className={pnlClass(totalReturnPct)} style={{ textAlign: 'right' }}>{fmtPct(totalReturnPct)}</td>
              <td className={pnlClass(totalContributionPct)} style={{ textAlign: 'right' }}>{fmtPct(totalContributionPct)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 style={{ marginTop: 18, fontSize: 14 }}>Return Contribution by Asset (%)</h3>
      <div style={{ height: `${Math.max(300, chartRows.length * 32)}px` }}>
        <Bar data={chartData} options={chartOpts} />
      </div>
    </div>
  );
}

// ── Section 2: Per-Coin Breakdown ────────────────────────────────────
function PerCoinSection({ rows }) {
  const { sortKey, sortDir, toggle } = useSort('total_pnl', 'desc');
  if (!rows) return <div className="panel"><h2>Per-Coin Breakdown</h2><p className="muted">Loading…</p></div>;
  if (rows.length === 0) {
    return <div className="panel"><h2>Per-Coin Breakdown</h2><p className="muted">No closed trades yet.</p></div>;
  }

  const sorted = sortRows(rows, sortKey, sortDir);

  const winRateClass = (wr) => {
    const x = Number(wr);
    if (x >= 60) return 'green';
    if (x < 40) return 'red';
    return '';
  };

  return (
    <div className="panel">
      <h2>Per-Coin Breakdown</h2>
      <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
        Trading skill per coin — win rate, average P&L, hold time. Different from
        contribution above (which weighs by position size).
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <SortHeader label="Symbol" sortKey="symbol" currentKey={sortKey} currentDir={sortDir} onSort={toggle} />
              <SortHeader label="Trades" sortKey="trades" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Wins" sortKey="wins" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Win Rate" sortKey="win_rate" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Total P&L" sortKey="total_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Avg P&L" sortKey="avg_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Avg Hold" sortKey="avg_hold_seconds" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Best" sortKey="best_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
              <SortHeader label="Worst" sortKey="worst_pnl" currentKey={sortKey} currentDir={sortDir} onSort={toggle} align="right" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.symbol}>
                <td><strong>{r.symbol}</strong></td>
                <td style={{ textAlign: 'right' }}>{fmtInt(r.trades)}</td>
                <td style={{ textAlign: 'right' }}>{fmtInt(r.wins)}</td>
                <td className={winRateClass(r.win_rate)} style={{ textAlign: 'right' }}>{fmtPct(r.win_rate)}</td>
                <td className={pnlClass(r.total_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(r.total_pnl)}</td>
                <td className={pnlClass(r.avg_pnl)} style={{ textAlign: 'right' }}>{fmtMoney(r.avg_pnl)}</td>
                <td style={{ textAlign: 'right' }}>{fmtHold(r.avg_hold_seconds)}</td>
                <td className="green" style={{ textAlign: 'right' }}>{fmtMoney(r.best_pnl)}</td>
                <td className="red" style={{ textAlign: 'right' }}>{fmtMoney(r.worst_pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Section 3: Risk Metrics ──────────────────────────────────────────
const METRIC_TOOLTIPS = {
  sharpe: 'Risk-adjusted return. >1 = good, <0 = losing money',
  sortino: 'Like Sharpe but only penalizes downside volatility',
  calmar: 'Annual return / Max drawdown. Higher = better recovery',
  max_drawdown_pct: 'Largest peak-to-trough drop in portfolio value',
  var_95: "95% of days, your loss won't exceed this %",
  var_99: "99% of days, your loss won't exceed this %",
  annualized_return: 'Geometric annualized return from daily snapshots',
  annualized_volatility: 'Standard deviation of returns, annualized',
  downside_deviation: 'Volatility of negative returns only',
  skewness: 'Return distribution asymmetry. >0 = more upside surprises',
  kurtosis: 'Tail thickness. >0 (excess) = more extreme events than normal',
  best_day_pct: 'Largest single-day gain',
  worst_day_pct: 'Largest single-day loss',
};

function MetricRow({ keyName, label, value, cls = '' }) {
  return (
    <tr>
      <td title={METRIC_TOOLTIPS[keyName] || ''}>{label}</td>
      <td className={cls}>{value}</td>
    </tr>
  );
}

function RiskMetricsSection({ data }) {
  if (!data) {
    return <div className="panel"><h2>Risk Metrics</h2><p className="muted">Loading…</p></div>;
  }
  const s = data.static;
  if (data.sample_size < 2) {
    return (
      <div className="panel">
        <h2>Risk Metrics</h2>
        <p className="muted">
          Need at least 2 daily snapshots. Take a snapshot from the Dashboard,
          or run the backfill from <Link to="/setup">Setup</Link>.
        </p>
      </div>
    );
  }

  const ratioClass = (n) => {
    if (n == null) return '';
    return n >= 1 ? 'green' : (n < 0 ? 'red' : '');
  };
  const skewClass = (n) => (n == null ? '' : (n > 0 ? 'green' : 'red'));
  const kurtClass = (n) => (n == null ? '' : (n > 0 ? 'red' : ''));

  // Charts
  const sharpeChart = {
    labels: data.rolling_sharpe_30d.map((p) => p.date),
    datasets: [{
      data: data.rolling_sharpe_30d.map((p) => p.value),
      borderColor: '#60a5fa',
      backgroundColor: 'rgba(96,165,250,0.08)',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.15,
    }],
  };
  const volChart = {
    labels: data.rolling_volatility_30d.map((p) => p.date),
    datasets: [{
      data: data.rolling_volatility_30d.map((p) => p.value),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245,158,11,0.10)',
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.15,
      fill: 'origin',
    }],
  };
  const baseOpts = (yLabel, addZeroLine = false) => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => items[0].label,
          label: (ctx) => `${yLabel}: ${ctx.parsed.y.toFixed(3)}`,
        },
      },
    },
    scales: {
      x: {
        ticks: { color: '#8b949e', maxTicksLimit: 8, autoSkip: true },
        grid: { color: 'rgba(138,148,158,0.06)' },
      },
      y: {
        ticks: { color: '#8b949e' },
        grid: {
          color: (ctx) => addZeroLine && ctx.tick.value === 0
            ? 'rgba(255,255,255,0.25)'
            : 'rgba(138,148,158,0.06)',
        },
      },
    },
  });

  const hasRolling = data.rolling_sharpe_30d.length > 0;

  return (
    <div className="panel">
      <h2>Risk Metrics</h2>
      <div className="risk-grid">
        <table className="risk-key-table">
          <tbody>
            <MetricRow keyName="sharpe" label="Sharpe Ratio (Ann.)" value={fmtRatio(s.sharpe, 3)} cls={ratioClass(s.sharpe)} />
            <MetricRow keyName="sortino" label="Sortino Ratio (Ann.)" value={fmtRatio(s.sortino, 3)} cls={ratioClass(s.sortino)} />
            <MetricRow keyName="calmar" label="Calmar Ratio" value={fmtRatio(s.calmar, 3)} cls={ratioClass(s.calmar)} />
            <MetricRow keyName="max_drawdown_pct" label="Max Drawdown" value={fmtPct(s.max_drawdown_pct)} cls="red" />
            <MetricRow keyName="var_95" label="VaR 95% (Daily)" value={fmtPct(s.var_95)} cls="red" />
            <MetricRow keyName="var_99" label="VaR 99% (Daily)" value={fmtPct(s.var_99)} cls="red" />
            <MetricRow keyName="annualized_return" label="Annualized Return" value={fmtPct(s.annualized_return)} cls={pnlClass(s.annualized_return)} />
            <MetricRow keyName="annualized_volatility" label="Annualized Volatility" value={fmtPct(s.annualized_volatility)} />
            <MetricRow keyName="downside_deviation" label="Downside Deviation" value={fmtPct(s.downside_deviation)} />
            <MetricRow keyName="skewness" label="Skewness" value={fmtRatio(s.skewness, 3)} cls={skewClass(s.skewness)} />
            <MetricRow keyName="kurtosis" label="Kurtosis (excess)" value={fmtRatio(s.kurtosis, 3)} cls={kurtClass(s.kurtosis)} />
            <MetricRow keyName="best_day_pct" label="Best Day" value={fmtPct(s.best_day_pct)} cls="green" />
            <MetricRow keyName="worst_day_pct" label="Worst Day" value={fmtPct(s.worst_day_pct)} cls="red" />
          </tbody>
        </table>

        <div className="risk-charts">
          <div className="risk-chart-block">
            <h3>Rolling Sharpe Ratio (30d)</h3>
            {hasRolling ? (
              <div style={{ height: 240 }}>
                <Line data={sharpeChart} options={baseOpts('Sharpe', true)} />
              </div>
            ) : (
              <p className="muted">Need ≥ 30 daily snapshots to show rolling Sharpe.</p>
            )}
          </div>
          <div className="risk-chart-block">
            <h3>Rolling Volatility 30d (%)</h3>
            {hasRolling ? (
              <div style={{ height: 240 }}>
                <Line data={volChart} options={baseOpts('Vol')} />
              </div>
            ) : (
              <p className="muted">Need ≥ 30 daily snapshots to show rolling volatility.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────
export default function Performance() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [assetRows, setAssetRows] = useState(null);
  const [perCoinRows, setPerCoinRows] = useState(null);
  const [riskData, setRiskData] = useState(null);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId) return;
    let cancelled = false;
    (async () => {
      setLoading(true); setError(null);
      const params = { portfolio_id: portfolioId };
      try {
        const [ap, pc, rm] = await Promise.all([
          api.statsAssetPerformance(params),
          api.statsPerCoinBreakdown(params),
          api.statsRiskMetrics(params),
        ]);
        if (cancelled) return;
        setAssetRows(ap);
        setPerCoinRows(pc);
        setRiskData(rm);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [portfolioId]);

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return <div className="panel"><p>Create a portfolio via <Link to="/setup">Setup</Link>.</p></div>;
  }

  return (
    <>
      <div className="page-header">
        <h1>Performance</h1>
        <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
          {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
        </select>
      </div>

      {loading && <p className="muted">Loading…</p>}
      {error && <p className="error">{error}</p>}

      <AssetPerformanceSection rows={assetRows} />
      <PerCoinSection rows={perCoinRows} />
      <RiskMetricsSection data={riskData} />
    </>
  );
}
