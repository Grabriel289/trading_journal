import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api.js';
import PriceStatusBadge from '../components/PriceStatusBadge.jsx';

function setBulkDraftField(setter, symbol, field, value) {
  setter((d) => ({ ...d, [symbol]: { ...(d[symbol] || {}), [field]: value } }));
}

const SOURCE_LABEL = {
  BINANCE: 'Binance',
  KUCOIN: 'Kucoin',
  COINGECKO: 'CoinGecko',
  MANUAL: 'Manual',
};

function fmtPrice(p) {
  if (p == null) return '—';
  return '$' + Number(p).toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function timeAgo(iso) {
  if (!iso) return '';
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.round(ms / 3_600_000)}h ago`;
  return `${Math.round(ms / 86_400_000)}d ago`;
}

export default function Pricing() {
  const [assets, setAssets] = useState([]);
  const [quotes, setQuotes] = useState({});  // symbol -> quote
  const [error, setError] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  // Add-asset form state
  const [newSymbol, setNewSymbol] = useState('');
  const [newName,   setNewName]   = useState('');
  const [newGeckoId, setNewGeckoId] = useState('');
  const [creating, setCreating] = useState(false);

  // Manual price form state (per-symbol)
  const [manualOpen, setManualOpen] = useState(null);  // symbol or null
  const [mPrice, setMPrice] = useState('');
  const [mNote,  setMNote]  = useState('');
  const [mOverride, setMOverride] = useState(true);
  const [mHistory, setMHistory] = useState([]);

  // Bulk update state — drafts keyed by symbol
  const [bulkDrafts, setBulkDrafts] = useState({});  // symbol -> { price, note }
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);

  const manualAssets = useMemo(
    () => assets.filter((a) => a.has_manual_price),
    [assets],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api.listAssets();
        if (cancelled) return;
        setAssets(list);
        // Fetch quotes in parallel; isolated try so one bad token doesn't poison the row
        const results = await Promise.all(
          list.map(async (a) => {
            try { return [a.symbol, await api.getQuote(a.symbol)]; }
            catch { return [a.symbol, null]; }
          })
        );
        if (!cancelled) setQuotes(Object.fromEntries(results));
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [reloadKey]);

  async function createAsset(e) {
    e.preventDefault();
    if (!newSymbol.trim()) return;
    setCreating(true); setError(null);
    try {
      await api.createAsset({
        symbol: newSymbol.trim(),
        name: newName || undefined,
        coingecko_id: newGeckoId || undefined,
      });
      setNewSymbol(''); setNewName(''); setNewGeckoId('');
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function deleteAsset(symbol) {
    if (!confirm(`Delete asset ${symbol}? Removes price sources + manual history.`)) return;
    try {
      await api.deleteAsset(symbol);
      setReloadKey((k) => k + 1);
    } catch (e) { setError(e.message); }
  }

  async function openManualForm(symbol) {
    setManualOpen(symbol);
    setMPrice(''); setMNote(''); setMOverride(true);
    try {
      const h = await api.getManualPriceHistory(symbol);
      setMHistory(h);
    } catch { setMHistory([]); }
  }

  async function saveManualPrice() {
    if (!manualOpen || !mPrice) return;
    try {
      await api.setManualPrice(manualOpen, {
        price: mPrice,
        note: mNote || null,
        as_override: mOverride,
      });
      setManualOpen(null);
      setReloadKey((k) => k + 1);
    } catch (e) { setError(e.message); }
  }

  async function clearOverride(symbol) {
    if (!confirm(`Disable manual override for ${symbol}? History is kept.`)) return;
    try {
      await api.clearManualOverride(symbol);
      setReloadKey((k) => k + 1);
    } catch (e) { setError(e.message); }
  }

  async function saveBulk() {
    const items = Object.entries(bulkDrafts)
      .filter(([_, d]) => d?.price && Number(d.price) > 0)
      .map(([symbol, d]) => ({
        symbol,
        price: d.price,
        note: d.note || null,
        as_override: true,
      }));
    if (items.length === 0) {
      setBulkResult({ updated: 0, failed: 0, items: [], message: 'Nothing to save — fill at least one price.' });
      return;
    }
    setBulkBusy(true); setBulkResult(null);
    try {
      const r = await api.bulkManualPrices(items);
      setBulkResult(r);
      setBulkDrafts({});
      setReloadKey((k) => k + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setBulkBusy(false);
    }
  }

  function fillBulkWithCurrent() {
    // Pre-fill with the last-known manual price as a starting point
    const next = {};
    for (const a of manualAssets) {
      next[a.symbol] = {
        price: a.latest_manual_price ? String(a.latest_manual_price) : '',
        note: '',
      };
    }
    setBulkDrafts(next);
  }

  async function toggleSource(symbol, sourceType, isActive) {
    try {
      await api.upsertSource(symbol, {
        source_type: sourceType,
        priority: { BINANCE: 10, KUCOIN: 20, COINGECKO: 30, MANUAL: 5 }[sourceType] || 50,
        is_active: !isActive,
      });
      setReloadKey((k) => k + 1);
    } catch (e) { setError(e.message); }
  }

  return (
    <>
      <h1>Pricing</h1>
      <p className="muted" style={{ fontSize: 12, maxWidth: 760 }}>
        The system tries each enabled source in priority order (lowest priority number first).
        For tokens not on any exchange, set a Manual price as override or fallback. Manual entries
        are version-controlled — every change is appended to history.
      </p>
      {error && <div className="error">{error}</div>}

      <div className="panel form-center" style={{ maxWidth: 720 }}>
        <h2>Add Asset</h2>
        <form onSubmit={createAsset}>
          <div style={{ display: 'grid', gap: 10, gridTemplateColumns: '1fr 1fr 1fr' }}>
            <div className="form-row">
              <label>Symbol</label>
              <input value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
                placeholder="ABC" />
            </div>
            <div className="form-row">
              <label>Name (optional)</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="ABC Token" />
            </div>
            <div className="form-row">
              <label>CoinGecko ID</label>
              <input value={newGeckoId} onChange={(e) => setNewGeckoId(e.target.value)} placeholder="abc-token" />
            </div>
          </div>
          <button disabled={creating || !newSymbol}>{creating ? 'Adding…' : 'Add Asset'}</button>
        </form>
      </div>

      <div className="panel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Bulk Update Manual Prices</h2>
          <div className="btn-row">
            <button type="button" className="secondary tiny" onClick={fillBulkWithCurrent} disabled={manualAssets.length === 0}>
              Pre-fill with last prices
            </button>
            <button type="button" className="secondary tiny" onClick={() => setBulkDrafts({})} disabled={Object.keys(bulkDrafts).length === 0}>
              Clear
            </button>
          </div>
        </div>
        {manualAssets.length === 0 ? (
          <p className="muted">No manual-priced assets yet. Set a manual price on an asset below to populate this section.</p>
        ) : (
          <>
            <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
              Enter today's prices for any subset of your manual-priced assets and save in one click.
              Each save appends to that asset's history (audit trail). Empty rows are skipped.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Symbol</th><th>Last Price</th><th>Last Updated</th>
                  <th style={{ width: 180 }}>New Price</th>
                  <th>Note (optional)</th>
                </tr>
              </thead>
              <tbody>
                {manualAssets.map((a) => (
                  <tr key={a.symbol}>
                    <td><strong>{a.symbol}</strong> <span className="muted" style={{ fontSize: 11 }}>{a.name}</span></td>
                    <td>{fmtPrice(a.latest_manual_price)}</td>
                    <td className="muted">{timeAgo(a.latest_manual_at)}</td>
                    <td>
                      <input type="number" step="any"
                        placeholder={a.latest_manual_price ? String(a.latest_manual_price) : '0.00'}
                        value={bulkDrafts[a.symbol]?.price || ''}
                        onChange={(e) => setBulkDraftField(setBulkDrafts, a.symbol, 'price', e.target.value)} />
                    </td>
                    <td>
                      <input value={bulkDrafts[a.symbol]?.note || ''}
                        onChange={(e) => setBulkDraftField(setBulkDrafts, a.symbol, 'note', e.target.value)}
                        placeholder="DEX mid, OTC, internal mark…" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <button onClick={saveBulk} disabled={bulkBusy || Object.keys(bulkDrafts).length === 0}>
                {bulkBusy ? 'Saving…' : 'Save All'}
              </button>
              {bulkResult && (
                <span className={bulkResult.failed > 0 ? 'red' : 'green'}>
                  ✔ {bulkResult.updated} updated{bulkResult.failed > 0 ? ` · ${bulkResult.failed} failed` : ''}
                  {bulkResult.message ? ` — ${bulkResult.message}` : ''}
                </span>
              )}
            </div>
            {bulkResult?.failed > 0 && (
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>Symbol</th><th>Error</th></tr></thead>
                <tbody>
                  {bulkResult.items.filter((i) => !i.ok).map((i) => (
                    <tr key={i.symbol}><td>{i.symbol}</td><td className="red">{i.error}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      <div className="panel">
        <h2>Assets &amp; Live Prices</h2>
        {assets.length === 0 ? (
          <p className="muted">No assets yet. They auto-register when you place an order or import.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Symbol</th><th>Name</th><th>Sector</th><th>Chain</th><th>Tier</th>
                <th>Price</th><th>Status</th>
                <th>Sources (priority)</th><th>CoinGecko ID</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => {
                const q = quotes[a.symbol];
                return (
                  <tr key={a.symbol}>
                    <td><strong>{a.symbol}</strong></td>
                    <td>{a.name}</td>
                    <td>{a.sector ? <span className="badge muted" style={{ fontSize: 10 }}>{a.sector}</span> : <span className="muted">—</span>}</td>
                    <td>{a.chain ? <span className="badge muted" style={{ fontSize: 10 }}>{a.chain}</span> : <span className="muted">—</span>}</td>
                    <td>{a.market_cap_tier ? <span className="badge accent" style={{ fontSize: 10 }}>{a.market_cap_tier}</span> : <span className="muted">—</span>}</td>
                    <td>{q ? fmtPrice(q.price) : '—'}</td>
                    <td>
                      {q ? <PriceStatusBadge status={q.status} source={q.source} fetchedAt={q.fetched_at} />
                         : <span className="badge muted">…</span>}
                      {q?.fetched_at && <span className="muted" style={{ fontSize: 11, marginLeft: 6 }}>{timeAgo(q.fetched_at)}</span>}
                    </td>
                    <td>
                      {a.sources.map((s) => (
                        <span key={s.source_type}
                              className={`badge ${s.is_active ? (s.source_type === 'MANUAL' ? 'accent' : 'green') : 'muted'}`}
                              title={`${s.source_type} · priority ${s.priority} · ${s.is_active ? 'active' : 'disabled'}`}
                              style={{ marginRight: 4, cursor: 'pointer' }}
                              onClick={() => toggleSource(a.symbol, s.source_type, s.is_active)}>
                          {SOURCE_LABEL[s.source_type] || s.source_type}{s.is_active ? '' : ' ✕'}
                        </span>
                      ))}
                    </td>
                    <td className="muted">{a.coingecko_id || '—'}</td>
                    <td className="actions">
                      <div className="btn-row">
                        <button className="secondary tiny" onClick={() => openManualForm(a.symbol)}>
                          {a.has_manual_price ? 'Update Manual' : 'Set Manual'}
                        </button>
                        {a.has_manual_price && (
                          <button className="secondary tiny" onClick={() => clearOverride(a.symbol)}>Clear Override</button>
                        )}
                        <button className="danger tiny" onClick={() => deleteAsset(a.symbol)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {manualOpen && (
        <div className="modal-backdrop" onClick={() => setManualOpen(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Manual Price · {manualOpen}</h2>
            <div className="form-row">
              <label>Price (USDT)</label>
              <input type="number" step="any" value={mPrice}
                onChange={(e) => setMPrice(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Note (optional)</label>
              <input value={mNote} onChange={(e) => setMNote(e.target.value)}
                placeholder="OTC round, DEX quote, internal valuation, etc." />
            </div>
            <div className="form-row">
              <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="checkbox" checked={mOverride}
                  onChange={(e) => setMOverride(e.target.checked)}
                  style={{ width: 'auto' }} />
                <span>Override exchanges (priority 5). Uncheck to use only when APIs fail.</span>
              </label>
            </div>
            <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setManualOpen(null)}>Cancel</button>
              <button onClick={saveManualPrice} disabled={!mPrice}>Save</button>
            </div>
            {mHistory.length > 0 && (
              <>
                <h2 style={{ marginTop: 18 }}>History</h2>
                <table>
                  <thead><tr><th>When</th><th>Price</th><th>Note</th></tr></thead>
                  <tbody>
                    {mHistory.map((h) => (
                      <tr key={h.id}>
                        <td>{new Date(h.created_at).toLocaleString()}</td>
                        <td>{fmtPrice(h.price)}</td>
                        <td className="muted">{h.note || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
