import { useMemo, useState } from 'react';
import { fmtPrice } from '../utils/format.js';

// ── Formatters ───────────────────────────────────────────────────────
// fmtMoney = USD aggregates (capital, risk $, margin) — fixed 2 dp.
// fmtPrice (imported) = per-unit token prices — adaptive precision.
const fmtMoney = (n, digits = 2) => {
  if (n == null || !isFinite(n)) return '—';
  const x = Number(n);
  const sign = x < 0 ? '-' : '';
  return `${sign}$${Math.abs(x).toLocaleString(undefined, {
    maximumFractionDigits: digits, minimumFractionDigits: digits,
  })}`;
};
const fmtPct = (n, digits = 2) => {
  if (n == null || !isFinite(n)) return '—';
  return Number(n).toFixed(digits) + '%';
};
const fmtQty = (n, digits = 6) => {
  if (n == null || !isFinite(n)) return '—';
  return Number(n).toFixed(digits);
};

// ── Pure math (the whole spec lives here) ────────────────────────────
function calculatePosition({
  asset, entryPrice, direction, capital, leverage, riskPct,
  slModel, fixedSlPct, atrValue, atrMultiplier,
}) {
  const ep = parseFloat(entryPrice);
  const cap = parseFloat(capital);
  const lev = parseFloat(leverage);
  const risk = parseFloat(riskPct);
  const atr = parseFloat(atrValue);
  const atrMult = parseFloat(atrMultiplier);
  const fixedSl = parseFloat(fixedSlPct);

  const valid =
    ep > 0 && cap > 0 && lev >= 1 && risk > 0 && risk <= 100 &&
    (slModel === 'fixed' ? fixedSl > 0 : (atr > 0 && atrMult > 0));
  if (!valid) return null;

  // Per spec Core Concept: risk % applies to CAPITAL only. Leverage doesn't
  // change dollar risk — it only affects how much margin you have to post.
  const dollarRisk = cap * (risk / 100);
  // Buying power is used as a constraint (max position size cap), not as a
  // risk basis. Using full buying power = risking leverage × risk_pct of capital.
  const maxBuyingPower = cap * lev;

  // SL distance % from the chosen model
  let slDistancePct;
  let atrAsPct = null;
  if (slModel === 'fixed') {
    slDistancePct = fixedSl;
    if (atr > 0) atrAsPct = (atr / ep) * 100;  // optional comparison
  } else {
    const atrSlDistance = atr * atrMult;        // in dollars
    slDistancePct = (atrSlDistance / ep) * 100;
    atrAsPct = (atr / ep) * 100;
  }

  // Position sizing per spec: notional = dollar_risk / SL_pct. If the implied
  // margin overflows capital (only possible when SL is tiny), cap to buying power.
  const idealNotional = dollarRisk / (slDistancePct / 100);
  let notional = idealNotional;
  let actualRisk = dollarRisk;
  let capped = false;

  const idealMargin = idealNotional / lev;
  if (idealMargin > cap) {
    notional = maxBuyingPower;
    actualRisk = notional * (slDistancePct / 100);
    capped = true;
  }

  const positionSize = notional / ep;
  const requiredMargin = notional / lev;

  // SL price
  const slPrice = direction === 'LONG'
    ? ep * (1 - slDistancePct / 100)
    : ep * (1 + slDistancePct / 100);

  // Liquidation (simplified Binance cross-margin, 0.5% maintenance)
  const MAINT_RATE = 0.005;
  let liqPrice = null;
  let distToLiqPct = null;
  if (lev > 1) {
    liqPrice = direction === 'LONG'
      ? ep * (1 - 1 / lev + MAINT_RATE)
      : ep * (1 + 1 / lev - MAINT_RATE);
    distToLiqPct = Math.abs(ep - liqPrice) / ep * 100;
  }

  // R:R projections
  const rrTargets = [1, 1.5, 2, 3].map((ratio) => {
    const rewardDist = slDistancePct * ratio;
    const tpPrice = direction === 'LONG'
      ? ep * (1 + rewardDist / 100)
      : ep * (1 - rewardDist / 100);
    return { ratio, tpPrice, profit: actualRisk * ratio };
  });

  // Leverage comparison table — same dollar_risk budget at every row.
  // The table teaches: as leverage grows, you'd need a tighter SL to stay
  // within the same dollar risk if you were to use the full buying power.
  const LEV_ROWS = [1, 2, 3, 5, 10, 20, 50];
  const leverageRows = LEV_ROWS.map((L) => {
    const rowNotional = cap * L;
    const rowSlPct = (dollarRisk / rowNotional) * 100;
    const rowSlPrice = direction === 'LONG'
      ? ep * (1 - rowSlPct / 100)
      : ep * (1 + rowSlPct / 100);
    let rowLiqPrice = null;
    if (L > 1) {
      rowLiqPrice = direction === 'LONG'
        ? ep * (1 - 1 / L + MAINT_RATE)
        : ep * (1 + 1 / L - MAINT_RATE);
    }
    return {
      leverage: L,
      notional: rowNotional,
      margin: cap,
      slDistPct: rowSlPct,
      slPrice: rowSlPrice,
      liqPrice: rowLiqPrice,
      isCurrent: L === lev,
      tightBelowAtr: atrAsPct != null && rowSlPct < atrAsPct,
    };
  });

  // Warnings
  const warnings = [];
  if (capped) {
    // Cap only triggers when SL is so tight that the risk-budget-derived
    // position would exceed buying power. After capping, actual loss is
    // notional × SL_pct.
    warnings.push({
      level: 'yellow',
      message:
        `Actual risk (${fmtMoney(actualRisk)}) exceeds target (${fmtMoney(dollarRisk)}). ` +
        `Your stop loss (${slDistancePct.toFixed(2)}%) at ${lev}× leverage requires more margin ` +
        `than available. Position capped to ${fmtMoney(notional)} notional ` +
        `(${(actualRisk / cap * 100).toFixed(2)}% of capital at risk).`,
    });
  }
  if (slModel === 'fixed' && atrAsPct != null && slDistancePct < atrAsPct) {
    warnings.push({
      level: 'yellow',
      message:
        `Stop loss (${slDistancePct.toFixed(2)}%) is tighter than 1 ATR (${atrAsPct.toFixed(2)}%). ` +
        `At ${lev}× with ${risk}% risk, your SL will be hit by normal price noise. ` +
        `Consider: lower leverage, wider risk %, or switch to ATR model.`,
    });
  }
  if (liqPrice != null && Math.abs(slPrice - liqPrice) / ep < 0.05) {
    warnings.push({
      level: 'red',
      message:
        `Stop loss (${fmtPrice(slPrice)}) is within 5% of liquidation (${fmtPrice(liqPrice)}). ` +
        `Slippage or a single wick could liquidate you before SL triggers. ` +
        `Reduce leverage or widen stop loss.`,
    });
  }
  if (lev >= 50) {
    warnings.push({
      level: 'yellow',
      message:
        `At ${lev}× leverage, exchange fees (~0.04% per side) consume a significant portion ` +
        `of your SL distance (${slDistancePct.toFixed(3)}%). Effective risk may be 2-3× stated risk.`,
    });
  }

  return {
    asset, direction, leverage: lev, capital: cap, riskPct: risk,
    entryPrice: ep,
    maxBuyingPower,
    dollarRisk, actualRisk, capped,
    notional, idealNotional,
    positionSize, requiredMargin,
    slDistancePct, slPrice,
    liqPrice, distToLiqPct,
    atrValue: atr || null, atrMultiplier: atrMult, atrAsPct,
    rrTargets,
    leverageRows,
    warnings,
  };
}

// ── Components ───────────────────────────────────────────────────────
function ResultCard({ label, value, cls = '', aux = null }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className={`value ${cls}`}>{value}</div>
      {aux && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{aux}</div>}
    </div>
  );
}

function WarningAlerts({ warnings }) {
  if (!warnings || warnings.length === 0) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      {warnings.map((w, i) => (
        <div key={i} className={`calc-warning ${w.level}`}>
          <span>{w.level === 'red' ? '🔴' : '⚠️'}</span>
          <span>{w.message}</span>
        </div>
      ))}
    </div>
  );
}

function ResultCards({ r }) {
  return (
    <div className="calc-cards">
      <ResultCard label="Dollar Risk" value={fmtMoney(r.actualRisk)} cls="red"
        aux={r.capped ? `target ${fmtMoney(r.dollarRisk)}` : `${r.riskPct.toFixed(1)}% of capital`} />
      <ResultCard label="Position Size" value={`${fmtQty(r.positionSize)} ${r.asset || ''}`.trim()} />
      <ResultCard label="Notional Value" value={fmtMoney(r.notional)}
        aux={`${(r.notional / r.capital * 100).toFixed(0)}% of capital`} />
      <ResultCard label="Margin Required" value={fmtMoney(r.requiredMargin)}
        aux={`${(r.requiredMargin / r.capital * 100).toFixed(0)}% of capital`} />
      <ResultCard label="Entry Price" value={fmtPrice(r.entryPrice)} />
      <ResultCard label="Stop Loss Price" value={fmtPrice(r.slPrice)} cls="red" />
      <ResultCard label="SL Distance"
        value={`${fmtPct(r.slDistancePct)} / ${fmtPrice((r.slDistancePct / 100) * r.entryPrice)}`}
        cls="red" />
      <ResultCard label="Liquidation Price"
        value={r.liqPrice != null ? fmtPrice(r.liqPrice) : 'N/A'}
        cls={r.distToLiqPct != null && r.distToLiqPct < 5 ? 'red' : ''}
        aux={r.distToLiqPct != null ? `${r.distToLiqPct.toFixed(1)}% away` : '(1× = no liq)'} />
    </div>
  );
}

function BreakdownTable({ r }) {
  const distToLiqCls =
    r.distToLiqPct == null ? '' :
    r.distToLiqPct >= 10 ? 'green' :
    r.distToLiqPct >= 5 ? '' : 'red';

  return (
    <table>
      <tbody>
        <tr><td>Account Capital</td><td style={{ textAlign: 'right' }}>{fmtMoney(r.capital)}</td></tr>
        <tr><td>Risk Per Trade</td><td style={{ textAlign: 'right' }}>{fmtPct(r.riskPct, 1)} of capital → <strong>{fmtMoney(r.dollarRisk)}</strong></td></tr>
        <tr><td>Leverage</td><td style={{ textAlign: 'right' }}>{r.leverage}×</td></tr>
        <tr><td>Max Buying Power</td><td style={{ textAlign: 'right' }}>{fmtMoney(r.maxBuyingPower)} <span className="muted" style={{ fontSize: 11 }}>(constraint only)</span></td></tr>
        <tr><td>Notional Value</td><td style={{ textAlign: 'right' }}>{fmtMoney(r.notional)} ({(r.notional / r.capital * 100).toFixed(0)}% of capital)</td></tr>
        <tr><td>Position Size</td><td style={{ textAlign: 'right' }}>{fmtQty(r.positionSize)} {r.asset || ''}</td></tr>
        <tr><td>Entry Price</td><td style={{ textAlign: 'right' }}>{fmtPrice(r.entryPrice)}</td></tr>
        <tr><td>Stop Loss Price</td><td style={{ textAlign: 'right' }} className="red">{fmtPrice(r.slPrice)} ({r.direction})</td></tr>
        <tr><td>SL Distance</td><td style={{ textAlign: 'right' }}>{fmtPct(r.slDistancePct)} ({fmtPrice((r.slDistancePct / 100) * r.entryPrice)} per {r.asset || 'unit'})</td></tr>
        <tr><td><strong>Dollar at Risk</strong></td><td style={{ textAlign: 'right' }} className="red"><strong>{fmtMoney(r.actualRisk)}</strong></td></tr>
        <tr><td>Liquidation Price (est.)</td><td style={{ textAlign: 'right' }}>{r.liqPrice != null ? fmtPrice(r.liqPrice) : 'N/A'}</td></tr>
        <tr><td>Distance to Liquidation</td><td style={{ textAlign: 'right' }} className={distToLiqCls}>{r.distToLiqPct != null ? fmtPct(r.distToLiqPct) : '—'}</td></tr>
        <tr><td colSpan={2} className="muted" style={{ borderTop: '1px solid var(--border-card)', paddingTop: 6, fontSize: 11 }}>Risk / Reward projections</td></tr>
        {r.rrTargets.map((rr) => (
          <tr key={rr.ratio}>
            <td>R:R 1:{rr.ratio}</td>
            <td style={{ textAlign: 'right' }} className="green">
              TP {fmtPrice(rr.tpPrice)} → profit {fmtMoney(rr.profit)}
            </td>
          </tr>
        ))}
        {r.atrValue != null && (
          <>
            <tr><td colSpan={2} className="muted" style={{ borderTop: '1px solid var(--border-card)', paddingTop: 6, fontSize: 11 }}>ATR reference</td></tr>
            <tr><td>ATR value (manual)</td><td style={{ textAlign: 'right' }}>{fmtPrice(r.atrValue)} ({fmtPct(r.atrAsPct)})</td></tr>
            {r.slDistancePct && r.atrMultiplier && (
              <tr><td>ATR × Multiplier</td><td style={{ textAlign: 'right' }}>{fmtPrice(r.atrValue)} × {r.atrMultiplier} = {fmtPrice(r.atrValue * r.atrMultiplier)}</td></tr>
            )}
          </>
        )}
      </tbody>
    </table>
  );
}

function LeverageTable({ r }) {
  const slCellClass = (pct) =>
    pct < 0.1 ? 'danger-sl' :
    pct < 0.5 ? 'tight-sl' : '';
  return (
    <table className="lev-table">
      <thead>
        <tr>
          <th style={{ textAlign: 'left' }}>Lev</th>
          <th style={{ textAlign: 'right' }}>Notional</th>
          <th style={{ textAlign: 'right' }}>Margin</th>
          <th style={{ textAlign: 'right' }}>SL Dist %</th>
          <th style={{ textAlign: 'right' }}>SL Price</th>
          <th style={{ textAlign: 'right' }}>Liq Price</th>
        </tr>
      </thead>
      <tbody>
        {r.leverageRows.map((row) => (
          <tr key={row.leverage}
              className={`${row.isCurrent ? 'current-lev' : ''} ${row.tightBelowAtr ? 'tight-vs-atr' : ''}`.trim()}
              title={row.tightBelowAtr ? 'SL tighter than 1 ATR — high chance of noise stop-out' : ''}>
            <td>{row.leverage}×</td>
            <td style={{ textAlign: 'right' }}>{fmtMoney(row.notional)}</td>
            <td style={{ textAlign: 'right' }}>{fmtMoney(row.margin)}</td>
            <td style={{ textAlign: 'right' }} className={slCellClass(row.slDistPct)}>
              {fmtPct(row.slDistPct, row.slDistPct < 1 ? 3 : 2)}
            </td>
            <td style={{ textAlign: 'right' }}>{fmtPrice(row.slPrice)}</td>
            <td style={{ textAlign: 'right' }}>{row.liqPrice != null ? fmtPrice(row.liqPrice) : 'N/A'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const LEVERAGE_OPTIONS = [1, 2, 3, 5, 7, 10, 15, 20, 25, 50, 75, 100, 125];

// ── Page ─────────────────────────────────────────────────────────────
export default function Calc() {
  const [inputs, setInputs] = useState({
    asset: 'BTC',
    entryPrice: '',
    direction: 'LONG',
    capital: '',
    leverage: 5,
    riskPct: 2.0,
    slModel: 'fixed',
    fixedSlPct: 2.0,
    atrValue: '',
    atrMultiplier: 1.5,
  });

  const set = (patch) => setInputs((prev) => ({ ...prev, ...patch }));

  const results = useMemo(() => calculatePosition(inputs), [inputs]);

  const incomplete = !results;
  const incompleteMsg = (() => {
    if (!inputs.capital || parseFloat(inputs.capital) <= 0) return 'Enter capital to begin.';
    if (!inputs.entryPrice || parseFloat(inputs.entryPrice) <= 0) return 'Enter entry price.';
    if (!inputs.riskPct || parseFloat(inputs.riskPct) <= 0) return 'Enter risk %.';
    if (inputs.slModel === 'fixed' && (!inputs.fixedSlPct || parseFloat(inputs.fixedSlPct) <= 0))
      return 'Enter stop loss distance %.';
    if (inputs.slModel === 'atr' && (!inputs.atrValue || parseFloat(inputs.atrValue) <= 0))
      return 'Enter ATR value from your chart.';
    return null;
  })();

  return (
    <>
      <div className="page-header">
        <h1>Position Calculator</h1>
      </div>

      {/* Input panel */}
      <div className="panel calc-input-panel">
        <div className="calc-input-grid">
          <div className="calc-input-group">
            <label>Asset</label>
            <input type="text" value={inputs.asset}
              onChange={(e) => set({ asset: e.target.value.toUpperCase() })}
              placeholder="BTC" maxLength={10} />
          </div>
          <div className="calc-input-group">
            <label>Entry Price ($)</label>
            <input type="number" step="any" value={inputs.entryPrice}
              onChange={(e) => set({ entryPrice: e.target.value })}
              placeholder="104250.00" />
          </div>
          <div className="calc-input-group">
            <label>Direction</label>
            <select value={inputs.direction} onChange={(e) => set({ direction: e.target.value })}>
              <option value="LONG">Long</option>
              <option value="SHORT">Short</option>
            </select>
          </div>
          <div className="calc-input-group">
            <label>Capital ($)</label>
            <input type="number" step="any" value={inputs.capital}
              onChange={(e) => set({ capital: e.target.value })}
              placeholder="500.00" />
          </div>
          <div className="calc-input-group">
            <label>Leverage</label>
            <select value={inputs.leverage} onChange={(e) => set({ leverage: Number(e.target.value) })}>
              {LEVERAGE_OPTIONS.map((L) => <option key={L} value={L}>{L}×</option>)}
            </select>
          </div>
          <div className="calc-input-group">
            <label>Risk % per trade</label>
            <input type="number" step="0.1" min="0" max="100" value={inputs.riskPct}
              onChange={(e) => set({ riskPct: e.target.value })} />
          </div>
        </div>

        <div style={{ marginTop: 18, marginBottom: 6, fontSize: 11, color: 'var(--txt-secondary)',
                      textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Stop Loss Model
        </div>
        <div className="sl-model-toggle">
          <button type="button"
            className={inputs.slModel === 'fixed' ? 'active' : ''}
            onClick={() => set({ slModel: 'fixed' })}>Fixed Stop Loss</button>
          <button type="button"
            className={inputs.slModel === 'atr' ? 'active' : ''}
            onClick={() => set({ slModel: 'atr' })}>ATR Volatility Model</button>
        </div>

        <div className="calc-input-grid" style={{ marginTop: 12, gridTemplateColumns: 'repeat(3, 1fr)' }}>
          {inputs.slModel === 'fixed' ? (
            <div className="calc-input-group">
              <label>Stop Loss Distance %</label>
              <input type="number" step="0.01" min="0" value={inputs.fixedSlPct}
                onChange={(e) => set({ fixedSlPct: e.target.value })} />
            </div>
          ) : (
            <>
              <div className="calc-input-group">
                <label>ATR Value ($) — from TradingView</label>
                <input type="number" step="any" value={inputs.atrValue}
                  onChange={(e) => set({ atrValue: e.target.value })}
                  placeholder="1890.50" />
              </div>
              <div className="calc-input-group">
                <label>ATR Multiplier</label>
                <input type="number" step="0.1" value={inputs.atrMultiplier}
                  onChange={(e) => set({ atrMultiplier: e.target.value })} />
              </div>
            </>
          )}
          {inputs.slModel === 'fixed' && (
            <div className="calc-input-group">
              <label>ATR (optional, for warnings)</label>
              <input type="number" step="any" value={inputs.atrValue}
                onChange={(e) => set({ atrValue: e.target.value })}
                placeholder="1890.50" />
            </div>
          )}
        </div>
      </div>

      {/* Incomplete state */}
      {incomplete && incompleteMsg && (
        <div className="panel" style={{ textAlign: 'center', padding: '32px 20px' }}>
          <p className="muted" style={{ margin: 0 }}>{incompleteMsg}</p>
        </div>
      )}

      {/* Results */}
      {results && (
        <>
          <WarningAlerts warnings={results.warnings} />
          <ResultCards r={results} />

          <div className="panel-grid-3" style={{ gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="panel" style={{ marginBottom: 0 }}>
              <h2>Risk Breakdown</h2>
              <BreakdownTable r={results} />
            </div>
            <div className="panel" style={{ marginBottom: 0 }}>
              <h2>Leverage Comparison</h2>
              <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
                If you used full buying power at each leverage with a {fmtMoney(results.dollarRisk)} risk budget,
                this is the SL distance you'd need. Tighter SL = more vulnerable to price noise.
              </p>
              <LeverageTable r={results} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
