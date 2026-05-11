import { useMemo } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, TimeScale, Tooltip, Legend,
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(CategoryScale, LinearScale, BarElement, TimeScale, Tooltip, Legend);

/**
 * Show bar chart of daily equity changes (PnL per day) derived from snapshots.
 * Excludes deposit/withdrawal flows so the bars show only trading PnL.
 */
export default function DailyPnlBars({ snapshots, height = 220 }) {
  const points = useMemo(() => {
    if (snapshots.length < 2) return [];
    const out = [];
    for (let i = 1; i < snapshots.length; i++) {
      const prev = snapshots[i - 1];
      const cur  = snapshots[i];
      const eqDelta  = Number(cur.total_equity) - Number(prev.total_equity);
      const depDelta = Number(cur.total_deposited) - Number(prev.total_deposited);
      out.push({ x: cur.date, y: eqDelta - depDelta });
    }
    return out;
  }, [snapshots]);

  const data = useMemo(() => ({
    datasets: [{
      label: 'Daily P&L $',
      data: points,
      backgroundColor: points.map((p) => p.y >= 0 ? '#26a69a' : '#ef5350'),
      borderWidth: 0,
    }],
  }), [points]);

  const opts = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `$${Number(ctx.parsed.y).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
        },
      },
    },
    scales: {
      x: {
        type: 'time',
        time: { unit: points.length > 30 ? 'week' : 'day' },
        ticks: { color: '#8b949e' },
        grid: { color: 'rgba(138,148,158,0.08)' },
      },
      y: {
        ticks: {
          color: '#8b949e',
          callback: (v) => '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }),
        },
        grid: { color: 'rgba(138,148,158,0.08)' },
      },
    },
  }), [points]);

  if (points.length === 0) {
    return <p className="muted">Need at least 2 snapshots — backfill or take snapshots over multiple days.</p>;
  }
  return (
    <div style={{ height }}>
      <Bar data={data} options={opts} />
    </div>
  );
}
