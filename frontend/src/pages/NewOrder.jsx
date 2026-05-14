import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';
import { fmtPrice } from '../utils/format.js';

function fmt(n, digits = 2) {
  if (n == null || n === '' || Number.isNaN(Number(n))) return '—';
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function NewOrder() {
  const { portfolios, loading: pLoading } = usePortfolios();

  const [side, setSide] = useState('BUY');
  const [portfolioId, setPortfolioId] = useState('');
  const [subAccountId, setSubAccountId] = useState('');

  const [asset, setAsset] = useState('BTC');
  const [leverage, setLeverage] = useState('5');
  const [direction, setDirection] = useState('LONG');

  // Unified amount input (works for both BUY and SELL).
  const [inputMode, setInputMode] = useState('qty');     // 'qty' | 'notional'
  const [inputAmount, setInputAmount] = useState('');

  // SELL-only state
  const [openBuys, setOpenBuys] = useState([]);
  const [linkedBuyId, setLinkedBuyId] = useState('');

  // Shared
  const [usePriceMode, setUsePriceMode] = useState('live');
  const [manualPrice, setManualPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [note, setNote] = useState('');

  // Phase 2 enrichment (advanced)
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [strategies, setStrategies] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [strategyId, setStrategyId] = useState('');
  const [orderType, setOrderType] = useState('');
  const [venue, setVenue] = useState('');
  const [exchangeOrderId, setExchangeOrderId] = useState('');
  const [expectedPrice, setExpectedPrice] = useState('');
  const [feeCurrency, setFeeCurrency] = useState('');
  const [makerTaker, setMakerTaker] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState([]);

  useEffect(() => {
    api.listStrategies(true).then(setStrategies).catch(() => {});
    api.listTags().then(setAllTags).catch(() => {});
  }, []);

  const [livePrice, setLivePrice] = useState(null);
  const [priceError, setPriceError] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);
  const [error, setError] = useState(null);

  const subAccounts = useMemo(() => {
    const p = portfolios.find((x) => x.id === portfolioId);
    return p ? p.sub_accounts : [];
  }, [portfolios, portfolioId]);

  const activeSub = useMemo(
    () => subAccounts.find((s) => s.id === subAccountId) || null,
    [subAccounts, subAccountId]
  );
  const isFutures = activeSub?.type === 'FUTURES';

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (subAccounts.length > 0 && !subAccounts.find((s) => s.id === subAccountId)) {
      setSubAccountId(subAccounts[0].id);
    }
  }, [subAccounts, subAccountId]);

  // Load open buys when SELL is active
  useEffect(() => {
    if (side !== 'SELL' || !subAccountId) { setOpenBuys([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getOpenBuys(subAccountId);
        if (!cancelled) {
          setOpenBuys(data);
          if (data.length > 0 && !data.find((b) => b.id === linkedBuyId)) {
            setLinkedBuyId(data[0].id);
          } else if (data.length === 0) {
            setLinkedBuyId('');
          }
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [side, subAccountId, success]);

  const linkedBuy = useMemo(
    () => openBuys.find((b) => b.id === linkedBuyId) || null,
    [openBuys, linkedBuyId]
  );

  const priceAsset = side === 'BUY' ? asset : (linkedBuy?.asset || '');

  useEffect(() => {
    if (!priceAsset || usePriceMode !== 'live') { setLivePrice(null); return; }
    let cancelled = false;
    setLivePrice(null); setPriceError(null);
    (async () => {
      try {
        const data = await api.getPrice(priceAsset);
        if (!cancelled) setLivePrice(data.price);
      } catch (e) {
        if (!cancelled) setPriceError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [priceAsset, usePriceMode]);

  const effectivePrice = usePriceMode === 'live' ? livePrice : manualPrice;
  const px = Number(effectivePrice);
  const amt = Number(inputAmount);

  // Convert input → quantity / notional pair
  const effectiveQuantity = useMemo(() => {
    if (!amt || !px) return 0;
    return inputMode === 'qty' ? amt : amt / px;
  }, [amt, px, inputMode]);
  const effectiveNotional = useMemo(() => {
    if (!amt || !px) return 0;
    return inputMode === 'qty' ? amt * px : amt;
  }, [amt, px, inputMode]);

  const sellRemaining = linkedBuy ? Number(linkedBuy.remaining_quantity) : 0;
  const sellOverLimit =
    side === 'SELL' && effectiveQuantity > 0 && effectiveQuantity > sellRemaining + 1e-12;

  const futuresPreview = useMemo(() => {
    if (side !== 'BUY' || !isFutures) return null;
    const lev = Number(leverage);
    if (!lev || !px || !effectiveQuantity) return null;
    const margin = (effectiveQuantity * px) / lev;
    const mmr = 0.005;
    const liq = direction === 'LONG'
      ? px * (1 - 1 / lev + mmr)
      : px * (1 + 1 / lev - mmr);
    return { margin, liq };
  }, [side, isFutures, leverage, px, effectiveQuantity, direction]);

  const projectedPnl = useMemo(() => {
    if (side !== 'SELL' || !linkedBuy || !px || !effectiveQuantity) return null;
    const entry = Number(linkedBuy.price);
    const exit = px;
    const qty = effectiveQuantity;
    const totalQty = Number(linkedBuy.quantity || 1);
    const share = qty / totalQty;
    const buyFeeShare = Number(linkedBuy.fee) * share;
    const sellFee = Number(fee) || 0;
    const isFut = !!linkedBuy.direction;
    const raw = isFut && linkedBuy.direction === 'SHORT'
      ? (entry - exit) * qty
      : (exit - entry) * qty;
    const fundingShare = isFut ? Number(linkedBuy.funding_accumulated || 0) * share : 0;
    const net = raw - buyFeeShare - sellFee - fundingShare;
    const denom = isFut ? Number(linkedBuy.margin_used || 0) * share : entry * qty;
    const pct = denom > 0 ? (net / denom) * 100 : 0;
    return { net, pct };
  }, [side, linkedBuy, px, effectiveQuantity, fee]);

  function setSellAllRemaining() {
    if (!linkedBuy) return;
    if (inputMode === 'qty') setInputAmount(String(linkedBuy.remaining_quantity));
    else if (px) setInputAmount(String(Number(linkedBuy.remaining_quantity) * px));
  }

  async function submit(e) {
    e.preventDefault();
    if (effectiveQuantity <= 0) { setError('Enter a positive amount'); return; }
    setSubmitting(true); setError(null); setSuccess(null);
    try {
      // Phase 2: build the enrichment payload only when populated
      const enrichment = {};
      if (strategyId) enrichment.strategy_id = strategyId;
      if (orderType) enrichment.order_type = orderType;
      if (venue) enrichment.execution_venue = venue;
      if (exchangeOrderId) enrichment.exchange_order_id = exchangeOrderId;
      if (expectedPrice) enrichment.expected_price = expectedPrice;
      if (feeCurrency) enrichment.fee_currency = feeCurrency;
      if (makerTaker) enrichment.maker_taker = makerTaker;
      if (selectedTagIds.length > 0) enrichment.tag_ids = selectedTagIds;

      if (side === 'BUY') {
        const body = {
          sub_account_id: subAccountId,
          asset,
          quantity: String(effectiveQuantity),
          fee,
          note: note || null,
          ...enrichment,
        };
        if (usePriceMode === 'manual') body.price = manualPrice;
        if (isFutures) {
          body.leverage = Number(leverage);
          body.direction = direction;
        }
        const order = await api.createBuy(body);
        const tag = isFutures ? ` (${direction} ${leverage}x)` : '';
        setSuccess(`BUY${tag}: ${fmt(order.quantity, 8)} ${order.asset} @ ${fmtPrice(order.price)}`);
      } else {
        if (!linkedBuyId) throw new Error('Pick a buy order to sell from');
        const body = {
          linked_buy_order_id: linkedBuyId,
          sell_quantity: String(effectiveQuantity),
          fee,
          note: note || null,
          ...enrichment,
        };
        if (usePriceMode === 'manual') body.price = manualPrice;
        const order = await api.createSell(body);
        setSuccess(`SELL: ${fmt(order.quantity, 8)} ${order.asset} @ ${fmtPrice(order.price)}`);
      }
      setInputAmount('');
      setNote('');
    } catch (e) {
      try {
        const j = JSON.parse(e.message);
        setError(j.detail || e.message);
      } catch { setError(e.message); }
    } finally {
      setSubmitting(false);
    }
  }

  if (pLoading) return <p className="muted">Loading…</p>;
  if (portfolios.length === 0) {
    return (
      <div className="panel">
        <h2>No portfolio</h2>
        <p>Create one via <Link to="/setup">Setup</Link>.</p>
      </div>
    );
  }
  if (subAccounts.length === 0) {
    return (
      <div className="panel">
        <h2>No sub-account</h2>
        <p>Add one via <Link to="/setup">Setup</Link>.</p>
      </div>
    );
  }

  const amountLabel = inputMode === 'qty'
    ? `Quantity (${priceAsset || 'units'})`
    : 'Notional ($)';

  return (
    <>
      <h1>New Order</h1>
      <div className="panel form-center" style={{ maxWidth: 580 }}>
        <div className="btn-row" style={{ marginBottom: 16 }}>
          <button type="button"
            className={side === 'BUY' ? '' : 'secondary'}
            onClick={() => setSide('BUY')}
            style={{ flex: 1 }}>Buy</button>
          <button type="button"
            className={side === 'SELL' ? '' : 'secondary'}
            onClick={() => setSide('SELL')}
            style={{ flex: 1 }}>Sell</button>
        </div>

        <form onSubmit={submit}>
          <div className="form-row">
            <label>Portfolio</label>
            <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)}>
              {portfolios.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </div>
          <div className="form-row">
            <label>Sub-Account</label>
            <select value={subAccountId} onChange={(e) => setSubAccountId(e.target.value)}>
              {subAccounts.map((s) => (<option key={s.id} value={s.id}>{s.name} ({s.type})</option>))}
            </select>
          </div>

          {side === 'BUY' && (
            <div className="form-row">
              <label>Asset</label>
              <input value={asset} onChange={(e) => setAsset(e.target.value.toUpperCase())} />
            </div>
          )}

          {side === 'SELL' && (
            <div className="form-row">
              <label>Sell from buy order</label>
              {openBuys.length === 0 ? (
                <p className="muted">No open buy orders in this sub-account.</p>
              ) : (
                <select value={linkedBuyId} onChange={(e) => setLinkedBuyId(e.target.value)}>
                  {openBuys.map((b) => {
                    const tag = b.direction ? ` ${b.direction} ${b.leverage}x` : '';
                    return (
                      <option key={b.id} value={b.id}>
                        {b.asset}{tag} — {fmt(b.remaining_quantity, 8)} @ {fmtPrice(b.price)}
                        {' '}({new Date(b.datetime).toLocaleDateString()})
                      </option>
                    );
                  })}
                </select>
              )}
            </div>
          )}

          {/* qty/notional toggle */}
          <div className="form-row">
            <label>{amountLabel}</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input type="number" step="any" inputMode="decimal"
                value={inputAmount}
                onChange={(e) => setInputAmount(e.target.value)}
                style={{ flex: 1 }} />
              <button type="button"
                className={inputMode === 'qty' ? '' : 'secondary'}
                onClick={() => setInputMode('qty')}
                style={{ minWidth: 56 }}>Units</button>
              <button type="button"
                className={inputMode === 'notional' ? '' : 'secondary'}
                onClick={() => setInputMode('notional')}
                style={{ minWidth: 56 }}>$</button>
            </div>
            {effectiveQuantity > 0 && (
              <p className="muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
                ≈ {fmt(effectiveQuantity, 8)} {priceAsset || 'units'}
                {' • '}
                ${fmt(effectiveNotional)}
              </p>
            )}
            {side === 'SELL' && linkedBuy && (
              <button type="button" className="secondary tiny"
                onClick={setSellAllRemaining}
                style={{ marginTop: 6, alignSelf: 'flex-start' }}>
                Sell all remaining ({fmt(linkedBuy.remaining_quantity, 8)} {linkedBuy.asset})
              </button>
            )}
            {sellOverLimit && (
              <div className="error">Exceeds remaining {fmt(sellRemaining, 8)} {linkedBuy?.asset}</div>
            )}
          </div>

          {side === 'BUY' && isFutures && (
            <>
              <div className="form-row">
                <label>Direction</label>
                <div className="btn-row">
                  <button type="button"
                    className={direction === 'LONG' ? '' : 'secondary'}
                    onClick={() => setDirection('LONG')}
                    style={{ flex: 1 }}>LONG</button>
                  <button type="button"
                    className={direction === 'SHORT' ? '' : 'secondary'}
                    onClick={() => setDirection('SHORT')}
                    style={{ flex: 1 }}>SHORT</button>
                </div>
              </div>
              <div className="form-row">
                <label>Leverage</label>
                <input type="number" min="1" step="1" value={leverage} onChange={(e) => setLeverage(e.target.value)} />
              </div>
            </>
          )}

          <div className="form-row">
            <label>Price source</label>
            <select value={usePriceMode} onChange={(e) => setUsePriceMode(e.target.value)}>
              <option value="live">Live (Binance)</option>
              <option value="manual">Manual</option>
            </select>
          </div>
          {usePriceMode === 'manual' && (
            <div className="form-row">
              <label>Manual price</label>
              <input type="number" step="any" value={manualPrice} onChange={(e) => setManualPrice(e.target.value)} />
            </div>
          )}
          {usePriceMode === 'live' && priceAsset && (
            <p className="muted" style={{ marginTop: -6 }}>
              {priceError ? <span className="red">price error: {priceError}</span> : (
                livePrice ? `Live ${priceAsset}USDT: ${fmtPrice(livePrice)}` : 'Fetching live price…'
              )}
            </p>
          )}
          <div className="form-row">
            <label>Fee</label>
            <input type="number" step="any" value={fee} onChange={(e) => setFee(e.target.value)} />
          </div>
          <div className="form-row">
            <label>Note</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          {/* ── Phase 2: Advanced (execution metadata / strategy / tags) ── */}
          <div style={{ borderTop: '1px solid var(--border-card)', marginTop: 14, paddingTop: 10 }}>
            <button
              type="button"
              className="secondary tiny"
              onClick={() => setAdvancedOpen(!advancedOpen)}
              style={{ marginBottom: advancedOpen ? 14 : 0 }}
            >{advancedOpen ? '▾ Hide advanced' : '▸ Advanced (strategy, venue, tags)'}</button>

            {advancedOpen && (
              <>
                <div className="form-row">
                  <label>Strategy</label>
                  <select value={strategyId} onChange={(e) => setStrategyId(e.target.value)}>
                    <option value="">— No strategy —</option>
                    {strategies.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="form-row">
                    <label>Order Type</label>
                    <select value={orderType} onChange={(e) => setOrderType(e.target.value)}>
                      <option value="">—</option>
                      <option value="MARKET">Market</option>
                      <option value="LIMIT">Limit</option>
                      <option value="STOP_MARKET">Stop Market</option>
                      <option value="STOP_LIMIT">Stop Limit</option>
                      <option value="TRAILING_STOP">Trailing Stop</option>
                    </select>
                  </div>
                  <div className="form-row">
                    <label>Venue</label>
                    <select value={venue} onChange={(e) => setVenue(e.target.value)}>
                      <option value="">—</option>
                      <option value="BINANCE_SPOT">Binance Spot</option>
                      <option value="BINANCE_FUTURES">Binance Futures</option>
                      <option value="KUCOIN_SPOT">Kucoin Spot</option>
                      <option value="KUCOIN_FUTURES">Kucoin Futures</option>
                      <option value="OKX_SPOT">OKX Spot</option>
                      <option value="OKX_FUTURES">OKX Futures</option>
                      <option value="BYBIT_SPOT">Bybit Spot</option>
                      <option value="BYBIT_FUTURES">Bybit Futures</option>
                      <option value="HYPERLIQUID">Hyperliquid</option>
                      <option value="DERIBIT">Deribit</option>
                      <option value="DEX">DEX</option>
                      <option value="OTC">OTC</option>
                      <option value="MANUAL">Manual</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="form-row">
                    <label>Exchange Order ID</label>
                    <input value={exchangeOrderId} onChange={(e) => setExchangeOrderId(e.target.value)} placeholder="123456789" />
                  </div>
                  <div className="form-row">
                    <label>Expected Price (for slippage)</label>
                    <input type="number" step="any" value={expectedPrice}
                      onChange={(e) => setExpectedPrice(e.target.value)} />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="form-row">
                    <label>Fee Currency</label>
                    <input value={feeCurrency} onChange={(e) => setFeeCurrency(e.target.value)} placeholder="USDT / BNB / BTC" />
                  </div>
                  <div className="form-row">
                    <label>Maker / Taker</label>
                    <select value={makerTaker} onChange={(e) => setMakerTaker(e.target.value)}>
                      <option value="">—</option>
                      <option value="MAKER">Maker</option>
                      <option value="TAKER">Taker</option>
                      <option value="UNKNOWN">Unknown</option>
                    </select>
                  </div>
                </div>
                <div className="form-row">
                  <label>Tags</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {allTags.length === 0 && <span className="muted" style={{ fontSize: 12 }}>No tags yet — create one in Settings.</span>}
                    {allTags.map((t) => {
                      const on = selectedTagIds.includes(t.id);
                      return (
                        <button
                          key={t.id} type="button"
                          onClick={() =>
                            setSelectedTagIds(on
                              ? selectedTagIds.filter((x) => x !== t.id)
                              : [...selectedTagIds, t.id])
                          }
                          style={{
                            padding: '4px 9px', fontSize: 11, borderRadius: 4,
                            background: on ? t.color : 'transparent',
                            color: on ? '#07080d' : 'var(--txt-secondary)',
                            border: `1px solid ${on ? t.color : 'var(--border-card)'}`,
                            fontWeight: 500, cursor: 'pointer',
                          }}
                        >{t.name}</button>
                      );
                    })}
                  </div>
                </div>
              </>
            )}
          </div>

          {futuresPreview && (
            <p className="muted">
              Margin required: <strong>${fmt(futuresPreview.margin)}</strong>
              {' • '}
              Liquidation: <strong className="red">${fmt(futuresPreview.liq)}</strong>
            </p>
          )}
          {projectedPnl && (
            <p className="muted">
              Projected P&L:{' '}
              <strong className={projectedPnl.net >= 0 ? 'green' : 'red'}>
                ${fmt(projectedPnl.net)} ({fmt(projectedPnl.pct)}%)
              </strong>
            </p>
          )}

          {error && <div className="error">{error}</div>}
          {success && <div className="green" style={{ marginBottom: 8 }}>{success}</div>}
          <button
            disabled={
              submitting ||
              !effectivePrice ||
              effectiveQuantity <= 0 ||
              (side === 'BUY' && isFutures && (!leverage || Number(leverage) < 1)) ||
              (side === 'SELL' && (!linkedBuyId || sellOverLimit))
            }
          >
            {submitting ? 'Submitting…' : side === 'BUY' ? 'Record Buy' : 'Record Sell'}
          </button>
        </form>
      </div>
    </>
  );
}
