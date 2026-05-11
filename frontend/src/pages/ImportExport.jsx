import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';

function ExportOrderCount({ portfolioId }) {
  const { portfolios } = usePortfolios();
  const [counts, setCounts] = useState(null);
  const subIds = useMemo(() => {
    const p = portfolios.find((x) => x.id === portfolioId);
    return p ? p.sub_accounts.map((s) => s.id) : [];
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (subIds.length === 0) { setCounts({ buys: 0, sells: 0 }); return; }
    let cancelled = false;
    (async () => {
      try {
        const lists = await Promise.all(
          subIds.map((sid) => api.listOrders({ sub_account_id: sid }))
        );
        if (cancelled) return;
        const all = lists.flat();
        setCounts({
          buys: all.filter((o) => o.side === 'BUY').length,
          sells: all.filter((o) => o.side === 'SELL').length,
        });
      } catch {
        if (!cancelled) setCounts(null);
      }
    })();
    return () => { cancelled = true; };
  }, [subIds.join(',')]);

  if (counts == null) return null;
  const total = counts.buys + counts.sells;
  return (
    <p className="muted" style={{ fontSize: 12, marginTop: -4, marginBottom: 8 }}>
      Will export <strong>{total}</strong> rows — {counts.buys} BUY + {counts.sells} SELL.
    </p>
  );
}

export default function ImportExport() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState('');
  const [file, setFile] = useState(null);
  const [dryRun, setDryRun] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const [jobBusy, setJobBusy] = useState(null);
  const [jobResult, setJobResult] = useState(null);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  async function submit(e) {
    e.preventDefault();
    if (!file || !portfolioId) return;
    setSubmitting(true); setError(null); setResult(null);
    try {
      const r = await api.importCSV(portfolioId, file, dryRun);
      setResult(r);
    } catch (e) {
      try {
        const parsed = JSON.parse(e.message);
        setError(parsed.detail || e.message);
      } catch {
        setError(e.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function runJob(name) {
    setJobBusy(name); setJobResult(null);
    try {
      const r = await api.triggerJob(name);
      setJobResult({ name, payload: r });
    } catch (e) {
      setJobResult({ name, error: e.message });
    } finally {
      setJobBusy(null);
    }
  }

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return <div className="panel"><p>Create a portfolio via <Link to="/setup">Setup</Link>.</p></div>;
  }

  return (
    <>
      <h1>Import / Export</h1>

      <div className="dash-duo" style={{ alignItems: 'start' }}>
      <div className="panel" style={{ marginBottom: 0 }}>
        <h2>CSV Import</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          Columns: <code>datetime, asset, side, quantity, price, fee, sub_account, leverage, direction, note</code>.
          {' '}<a href={api.templateURL()} download="cryptojournal-template.csv">Download template</a>.
          {' '}SELL rows match open buys via FIFO within the same sub-account / asset (and direction, if specified).
          {' '}Any row error rolls back the whole import — fix and re-upload.
        </p>
        <form onSubmit={submit}>
          <div className="form-row">
            <label>Portfolio</label>
            <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
              {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>
          <div className="form-row">
            <label>CSV file</label>
            <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <input type="checkbox" id="dryrun" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)}
              style={{ width: 18, height: 18, accentColor: 'var(--accent)', cursor: 'pointer' }} />
            <label htmlFor="dryrun" style={{ textTransform: 'none', letterSpacing: 0, fontSize: 13, color: 'var(--txt-secondary)', cursor: 'pointer' }}>
              Dry run (validate only, do not write)
            </label>
          </div>
          {error && <div className="error">{error}</div>}
          <button disabled={!file || submitting}>
            {submitting ? 'Uploading…' : (dryRun ? 'Validate' : 'Import')}
          </button>
        </form>

        {result && (
          <div style={{ marginTop: 16, padding: 12, background: 'var(--panel-2)', borderRadius: 6 }}>
            <div>
              Rows processed: <strong>{result.rows_processed}</strong>
              {' • '}
              Orders created: <strong className={result.orders_created > 0 ? 'green' : 'muted'}>
                {result.orders_created}
              </strong>
              {' • '}
              Errors: <strong className={result.errors.length > 0 ? 'red' : 'green'}>
                {result.errors.length}
              </strong>
            </div>
            {result.errors.length > 0 && (
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>Row</th><th>Error</th></tr></thead>
                <tbody>
                  {result.errors.map((e, i) => (
                    <tr key={i}><td>{e.row}</td><td className="red">{e.message}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <div className="panel" style={{ marginBottom: 0 }}>
        <h2>CSV Export</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          Downloads every order (every BUY and every SELL leg) for the selected portfolio. One row per order.
          {' '}For 100 closed trades you typically get 100+ SELL rows + the BUY rows they were matched against.
        </p>
        <div className="form-row">
          <label>Portfolio</label>
          <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
            {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
          </select>
        </div>
        <ExportOrderCount portfolioId={portfolioId} />
        <a
          href={api.exportURL(portfolioId)}
          download="orders.csv"
          style={{ display: 'inline-block', padding: '8px 14px', background: 'var(--accent)', color: 'white', borderRadius: 4, marginTop: 6 }}
        >Download orders.csv</a>
      </div>
      </div>

      <div className="panel">
        <h2>Background Jobs</h2>
        <p className="muted" style={{ fontSize: 13 }}>
          These run automatically (price cache every 60s, daily snapshot at 00:00 UTC, funding sync every 8h).
          Manual triggers below for testing or on-demand refresh.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button" className="secondary"
            onClick={() => runJob('price-cache')}
            disabled={jobBusy != null}
          >Price Cache Refresh</button>
          <button
            type="button" className="secondary"
            onClick={() => runJob('equity-snapshot')}
            disabled={jobBusy != null}
          >Equity Snapshot (all portfolios)</button>
          <button
            type="button" className="secondary"
            onClick={() => runJob('funding-sync')}
            disabled={jobBusy != null}
          >Funding Sync</button>
        </div>
        {jobBusy && <p className="muted" style={{ marginTop: 8 }}>Running {jobBusy}…</p>}
        {jobResult && (
          <pre className="muted" style={{ marginTop: 12, background: 'var(--panel-2)', padding: 10, borderRadius: 6, fontSize: 12 }}>
            {jobResult.error
              ? `${jobResult.name}: ERROR — ${jobResult.error}`
              : `${jobResult.name}: ${JSON.stringify(jobResult.payload)}`}
          </pre>
        )}
      </div>
    </>
  );
}
