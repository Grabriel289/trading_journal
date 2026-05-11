import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  TimeScale,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, TimeScale,
  Title, Tooltip, Legend, Filler
);

const COLOR_EQUITY    = '#25d9a7';
const COLOR_BALANCE   = '#8b8d9a';
const COLOR_DEPOSITED = '#5a5c6a';

function pickTimeUnit(count) {
  if (count <= 14) return 'day';
  if (count <= 90) return 'week';
  return 'month';
}

export default function EquityCurve({ snapshots }) {
  const data = useMemo(() => ({
    datasets: [
      {
        label: 'Equity',
        data: snapshots.map((s) => ({ x: s.date, y: Number(s.total_equity) })),
        borderColor: COLOR_EQUITY,
        backgroundColor: 'transparent',
        borderWidth: 2,
        fill: false,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: COLOR_EQUITY,
      },
      {
        label: 'Balance (cash)',
        data: snapshots.map((s) => ({ x: s.date, y: Number(s.total_balance) })),
        borderColor: COLOR_BALANCE,
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: COLOR_BALANCE,
      },
      {
        label: 'Deposited',
        data: snapshots.map((s) => ({ x: s.date, y: Number(s.total_deposited) })),
        borderColor: COLOR_DEPOSITED,
        borderDash: [4, 4],
        backgroundColor: 'transparent',
        borderWidth: 1,
        tension: 0,
        pointRadius: 0,
      },
    ],
  }), [snapshots]);

  const timeUnit = pickTimeUnit(snapshots.length);

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: '#e6edf3' } },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed.y).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
        },
      },
    },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: timeUnit,
          displayFormats: {
            day: 'MMM d',
            week: 'MMM d',
            month: 'MMM yyyy',
          },
        },
        ticks: {
          color: '#8b949e',
          maxTicksLimit: 12,
          autoSkip: true,
        },
        grid: { color: 'rgba(138,148,158,0.1)' },
      },
      y: {
        beginAtZero: false,
        grace: '10%',
        ticks: {
          color: '#8b949e',
          callback: (v) => '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 }),
        },
        grid: { color: 'rgba(138,148,158,0.1)' },
      },
    },
  }), [timeUnit]);

  if (snapshots.length === 0) {
    return <p className="muted">No snapshots yet — click "Take Snapshot" to record one, or "Backfill" to reconstruct historical snapshots from your trade log.</p>;
  }
  return (
    <div style={{ height: 380 }}>
      <Line data={data} options={options} />
    </div>
  );
}
