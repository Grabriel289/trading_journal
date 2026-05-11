import { useMemo } from 'react';
import { Doughnut } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

// Per-asset brand-ish colors. Anything not listed cycles through FALLBACK_PALETTE.
const ASSET_COLORS = {
  BTC:   '#f7931a',
  ETH:   '#627eea',
  SOL:   '#14f195',
  USDT:  '#26a17b',
  USDC:  '#2775ca',
  BNB:   '#f3ba2f',
  XRP:   '#23292f',
  ADA:   '#0033ad',
  DOGE:  '#c2a633',
  MATIC: '#8247e5',
  AVAX:  '#e84142',
  DOT:   '#e6007a',
  LINK:  '#2a5ada',
  TRX:   '#eb0029',
  LTC:   '#a6a9aa',
  TON:   '#0098ea',
  ZEC:   '#f4b728',
  ONDO:  '#9c80ff',
  ARB:   '#28a0f0',
  OP:    '#ff0420',
  PEPE:  '#3aab37',
  WLD:   '#1f2937',
};
const FALLBACK_PALETTE = [
  '#25d9a7', '#a78bfa', '#fb7185', '#fbbf24', '#34d399',
  '#60a5fa', '#f472b6', '#facc15', '#22d3ee', '#fb923c',
];

function colorFor(symbol, idx) {
  const s = symbol.toUpperCase();
  return ASSET_COLORS[s] || FALLBACK_PALETTE[idx % FALLBACK_PALETTE.length];
}

function fmtMoney(n) {
  return '$' + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

export default function AssetAllocation({ overview }) {
  const slices = useMemo(() => {
    if (!overview) return [];
    const byAsset = new Map();
    let cash = 0;
    for (const sub of overview.sub_accounts || []) {
      cash += Number(sub.cash);
      for (const pos of sub.open_positions || []) {
        const cur = byAsset.get(pos.asset) || 0;
        byAsset.set(pos.asset, cur + Number(pos.market_value));
      }
    }
    const items = Array.from(byAsset, ([asset, value]) => ({ asset, value }));
    if (cash > 0.0001) {
      items.push({ asset: overview.base_currency || 'Cash', value: cash, isCash: true });
    }
    return items
      .filter((s) => s.value > 0)
      .sort((a, b) => b.value - a.value);
  }, [overview]);

  const total = useMemo(() => slices.reduce((sum, s) => sum + s.value, 0), [slices]);

  const data = useMemo(() => ({
    labels: slices.map((s) => s.asset),
    datasets: [{
      data: slices.map((s) => s.value),
      backgroundColor: slices.map((s, i) => colorFor(s.asset, i)),
      borderColor: '#12131c',  // matches --bg-card so slices look detached from the panel
      borderWidth: 2,
      hoverOffset: 6,
    }],
  }), [slices]);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: {
      legend: { display: false },  // we render a custom legend on the right
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = Number(ctx.parsed);
            const pct = total > 0 ? (v / total) * 100 : 0;
            return ` ${ctx.label}: ${fmtMoney(v)} (${pct.toFixed(1)}%)`;
          },
        },
      },
    },
  }), [total]);

  if (slices.length === 0) {
    return <p className="muted">No assets to allocate yet — add a deposit or place an order.</p>;
  }

  return (
    <div className="alloc-grid">
      <div className="alloc-chart">
        <Doughnut data={data} options={options} />
        <div className="alloc-center">
          <div className="muted" style={{ fontSize: 11, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            Total
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>
            {fmtMoney(total)}
          </div>
        </div>
      </div>
      <div className="alloc-legend">
        {slices.map((s, i) => {
          const pct = total > 0 ? (s.value / total) * 100 : 0;
          return (
            <div key={s.asset} className="alloc-legend-row">
              <span className="alloc-dot" style={{ background: colorFor(s.asset, i) }} />
              <span className="alloc-symbol">{s.asset}{s.isCash ? ' (cash)' : ''}</span>
              <span className="alloc-pct muted">{pct.toFixed(1)}%</span>
              <span className="alloc-value">{fmtMoney(s.value)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
