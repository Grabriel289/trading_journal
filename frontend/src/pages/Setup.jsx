import { useState } from 'react';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';

function fmt(n) {
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function Setup() {
  const { portfolios, loading, error, reload } = usePortfolios();
  const [pName, setPName] = useState('Main Portfolio');
  const [baseCcy, setBaseCcy] = useState('USDT');
  // Phase 2: institutional metadata
  const [pBenchmark, setPBenchmark] = useState('');
  const [pInception, setPInception] = useState('');
  const [pMgmtFee, setPMgmtFee] = useState('');
  const [pPerfFee, setPPerfFee] = useState('');
  const [pDescription, setPDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState(null);

  const [selPortfolio, setSelPortfolio] = useState('');
  const [subName, setSubName] = useState('Spot Main');
  const [subType, setSubType] = useState('SPOT');
  const [subCapital, setSubCapital] = useState('10000');
  const [subErr, setSubErr] = useState(null);
  const [subBusy, setSubBusy] = useState(false);

  const [editPortfolio, setEditPortfolio] = useState(null);
  const [editSub, setEditSub] = useState(null);
  const [actionErr, setActionErr] = useState(null);

  async function createPortfolio(e) {
    e.preventDefault();
    setCreating(true); setCreateErr(null);
    try {
      const body = { name: pName, base_currency: baseCcy };
      if (pBenchmark)   body.benchmark = pBenchmark;
      if (pInception)   body.inception_date = pInception;
      if (pMgmtFee)     body.management_fee_rate = pMgmtFee;
      if (pPerfFee)     body.performance_fee_rate = pPerfFee;
      if (pDescription) body.description = pDescription;
      await api.createPortfolio(body);
      await reload();
    } catch (e) {
      setCreateErr(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function addSubAccount(e) {
    e.preventDefault();
    if (!selPortfolio) { setSubErr('Pick a portfolio'); return; }
    setSubBusy(true); setSubErr(null);
    try {
      await api.addSubAccount(selPortfolio, {
        name: subName,
        type: subType,
        initial_capital: subCapital,
      });
      await reload();
    } catch (e) {
      setSubErr(e.message);
    } finally {
      setSubBusy(false);
    }
  }

  async function saveEditPortfolio() {
    try {
      await api.updatePortfolio(editPortfolio.id, {
        name: editPortfolio.name,
        base_currency: editPortfolio.base_currency,
      });
      setEditPortfolio(null);
      await reload();
    } catch (e) { setActionErr(e.message); }
  }

  async function deletePortfolio(p) {
    if (!confirm(`Delete portfolio "${p.name}"?\n\nAll its sub-accounts, orders, deposits and snapshots will be removed permanently.`)) return;
    try {
      await api.deletePortfolio(p.id);
      await reload();
    } catch (e) { setActionErr(e.message); }
  }

  async function saveEditSub() {
    try {
      await api.updateSubAccount(editSub.id, {
        name: editSub.name,
        initial_capital: editSub.initial_capital,
      });
      setEditSub(null);
      await reload();
    } catch (e) { setActionErr(e.message); }
  }

  async function deleteSub(s) {
    if (!confirm(`Delete sub-account "${s.name}"?\n\nAll its orders and deposits will be removed permanently.`)) return;
    try {
      await api.deleteSubAccount(s.id);
      await reload();
    } catch (e) { setActionErr(e.message); }
  }

  async function wipeData(p) {
    const ack = prompt(
      `Wipe ALL transactions, deposits and snapshots in "${p.name}"?\n\n` +
      `Sub-accounts and the portfolio itself stay. This cannot be undone.\n\n` +
      `Type WIPE to confirm:`
    );
    if (ack !== 'WIPE') return;
    try {
      const r = await api.wipePortfolioData(p.id);
      setActionErr(
        `✔ Wiped: ${r.orders_deleted} orders, ${r.deposits_deleted} deposits, ${r.snapshots_deleted} snapshots`
      );
      await reload();
    } catch (e) { setActionErr(e.message); }
  }

  return (
    <>
      <div className="page-header"><h1>Setup</h1></div>

      {actionErr && (
        <div className={actionErr.startsWith('✔') ? 'green' : 'error'} style={{ marginBottom: 12 }}>
          {actionErr}
        </div>
      )}

      {/* ───── Two forms side by side ───── */}
      <div className="dash-duo" style={{ alignItems: 'start' }}>
        <div className="panel" style={{ marginBottom: 0 }}>
          <h2>Create Portfolio</h2>
          <form onSubmit={createPortfolio}>
            <div className="form-row">
              <label>Name</label>
              <input value={pName} onChange={(e) => setPName(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Base Currency</label>
              <select value={baseCcy} onChange={(e) => setBaseCcy(e.target.value)}>
                <option value="USDT">USDT</option>
                <option value="USDC">USDC</option>
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div className="form-row">
                <label>Benchmark (e.g. BTC)</label>
                <input value={pBenchmark} onChange={(e) => setPBenchmark(e.target.value)}
                  placeholder="BTC" maxLength={20} />
              </div>
              <div className="form-row">
                <label>Inception Date</label>
                <input type="date" value={pInception} onChange={(e) => setPInception(e.target.value)} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div className="form-row">
                <label>Management Fee (decimal, 0.02 = 2%)</label>
                <input type="number" step="0.0001" min="0" max="1"
                  value={pMgmtFee} onChange={(e) => setPMgmtFee(e.target.value)} />
              </div>
              <div className="form-row">
                <label>Performance Fee (above HWM)</label>
                <input type="number" step="0.0001" min="0" max="1"
                  value={pPerfFee} onChange={(e) => setPPerfFee(e.target.value)} />
              </div>
            </div>
            <div className="form-row">
              <label>Description</label>
              <input value={pDescription} onChange={(e) => setPDescription(e.target.value)} />
            </div>
            {createErr && <div className="error">{createErr}</div>}
            <button disabled={creating}>{creating ? 'Creating…' : 'Create Portfolio'}</button>
          </form>
        </div>

        <div className="panel" style={{ marginBottom: 0 }}>
          <h2>Add Sub-Account</h2>
          <form onSubmit={addSubAccount}>
            <div className="form-row">
              <label>Portfolio</label>
              <select value={selPortfolio} onChange={(e) => setSelPortfolio(e.target.value)}>
                <option value="">— Select —</option>
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label>Type</label>
              <select value={subType} onChange={(e) => setSubType(e.target.value)}>
                <option value="SPOT">Spot</option>
                <option value="FUTURES">Futures</option>
              </select>
            </div>
            <div className="form-row">
              <label>Sub-account name</label>
              <input value={subName} onChange={(e) => setSubName(e.target.value)} />
            </div>
            <div className="form-row">
              <label>Initial capital</label>
              <input type="number" step="0.01" value={subCapital} onChange={(e) => setSubCapital(e.target.value)} />
            </div>
            {subErr && <div className="error">{subErr}</div>}
            <button disabled={subBusy}>{subBusy ? 'Adding…' : 'Add Sub-Account'}</button>
          </form>
        </div>
      </div>

      {/* ───── Portfolio list (full width) ───── */}
      <div className="panel">
        <h2>Portfolios</h2>
        {loading && <p className="muted">Loading…</p>}
        {error && <p className="error">{error}</p>}
        {!loading && portfolios.length === 0 && <p className="muted">None yet.</p>}
        {portfolios.map((p) => (
          <div key={p.id} style={{ marginBottom: 22, borderBottom: '1px solid var(--border-card)', paddingBottom: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <strong style={{ fontSize: 16 }}>{p.name}</strong>
              <span className="muted">({p.base_currency})</span>
              <span style={{ flex: 1 }} />
              <div className="btn-row">
                <button className="secondary tiny" onClick={() => setEditPortfolio({ ...p })}>Edit</button>
                <button className="secondary tiny" onClick={() => wipeData(p)}>Wipe Transactions</button>
                <button className="danger tiny" onClick={() => deletePortfolio(p)}>Delete</button>
              </div>
            </div>
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Sub-account</th><th>Type</th><th>Initial Capital</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {p.sub_accounts.length === 0 ? (
                  <tr><td colSpan={4} className="muted">No sub-accounts.</td></tr>
                ) : p.sub_accounts.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td>
                    <td><span className="badge muted">{s.type}</span></td>
                    <td>${fmt(s.initial_capital)}</td>
                    <td className="actions">
                      <div className="btn-row">
                        <button className="secondary tiny" onClick={() => setEditSub({ ...s })}>Edit</button>
                        <button className="danger tiny" onClick={() => deleteSub(s)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {editPortfolio && (
        <div className="modal-backdrop" onClick={() => setEditPortfolio(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Portfolio</h2>
            <div className="form-row">
              <label>Name</label>
              <input value={editPortfolio.name}
                onChange={(e) => setEditPortfolio({ ...editPortfolio, name: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Base Currency</label>
              <select value={editPortfolio.base_currency}
                onChange={(e) => setEditPortfolio({ ...editPortfolio, base_currency: e.target.value })}>
                <option value="USDT">USDT</option>
                <option value="USDC">USDC</option>
              </select>
            </div>
            <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setEditPortfolio(null)}>Cancel</button>
              <button onClick={saveEditPortfolio}>Save</button>
            </div>
          </div>
        </div>
      )}

      {editSub && (
        <div className="modal-backdrop" onClick={() => setEditSub(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Sub-Account</h2>
            <p className="muted" style={{ fontSize: 12, marginTop: -4 }}>
              Type can't be changed once created.
            </p>
            <div className="form-row">
              <label>Name</label>
              <input value={editSub.name}
                onChange={(e) => setEditSub({ ...editSub, name: e.target.value })} />
            </div>
            <div className="form-row">
              <label>Initial capital</label>
              <input type="number" step="0.01" value={editSub.initial_capital}
                onChange={(e) => setEditSub({ ...editSub, initial_capital: e.target.value })} />
            </div>
            <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
              <button className="secondary" onClick={() => setEditSub(null)}>Cancel</button>
              <button onClick={saveEditSub}>Save</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
