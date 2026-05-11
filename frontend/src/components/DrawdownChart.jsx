import { useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement, TimeScale,
  Tooltip, Legend, Filler,
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, TimeScale,
  Tooltip, Legend, Filler
);

function pickTimeUnit(count) {
  if (count <= 14) return 'day';
  if (count <= 90) return 'week';
  return 'month';
}

export default function DrawdownChart({ snapshots, height = 220 }) {
  const data = useMemo(() => ({
    datasets: [{
      label: 'Drawdown %',
      data: snapshots.map((s) => ({
        x: s.date,
        y: -Math.abs(Number(s.drawdown_pct)),
      })),
      borderColor: '#ef5350',
      backgroundColor: 'rgba(239,83,80,0.18)',
      fill: 'origin',
      tension: 0.25,
      pointRadius: 0,
    }],
  }), [snapshots]);

  const timeUnit = pickTimeUnit(snapshots.length);

  const opts = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `Drawdown: ${Math.abs(ctx.parsed.y).toFixed(2)}%`,
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
        grid: { color: 'rgba(138,148,158,0.08)' },
      },
      y: {
        max: 0,
        ticks: {
          color: '#8b949e',
          callback: (v) => Math.abs(v).toFixed(0) + '%',
        },
        grid: { color: 'rgba(138,148,158,0.08)' },
      },
    },
  }), [timeUnit]);

  if (snapshots.length === 0) return null;
  return (
    <div style={{ height }}>
      <Line data={data} options={opts} />
    </div>
  );
}
