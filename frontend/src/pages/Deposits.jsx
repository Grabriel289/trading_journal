import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api.js';
import { usePortfolios } from '../hooks/usePortfolios.js';

function fmtMoney(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

export default function Deposits() {
  const { portfolios, loading: pLoading } = usePortfolios();
  const [portfolioId, setPortfolioId] = useState('');
  const [subAccountId, setSubAccountId] = useState('');
  const [type, setType] = useState('DEPOSIT');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [items, setItems] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);

  const subAccountById = useMemo(() => {
    const map = new Map();
    for (const p of portfolios) for (const s of p.sub_accounts) map.set(s.id, s);
    return map;
  }, [portfolios]);

  const subAccounts = useMemo(() => {
    const p = portfolios.find((x) => x.id === portfolioId);
    return p ? p.sub_accounts : [];
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (!portfolioId && portfolios.length > 0) setPortfolioId(portfolios[0].id);
  }, [portfolios, portfolioId]);

  useEffect(() => {
    if (subAccounts.length > 0 && !subAccounts.find((s) => s.id === subAccountId)) {
      setSubAccountId(subAccounts[0].id);
    }
  }, [subAccounts, subAccountId]);

  useEffect(() => {
    if (!portfolioId) { setItems([]); return; }
    const subIds = (portfolios.find((p) => p.id === portfolioId)?.sub_accounts || []).map((s) => s.id);
    if (subIds.length === 0) { setItems([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const lists = await Promise.all(subIds.map((sid) => api.listDeposits({ sub_account_id: sid })));
        if (!cancelled) {
          const flat = lists.flat().sort((a, b) => new Date(b.datetime) - new Date(a.datetime));
          setItems(flat);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => { cancelled = true; };
  }, [portfolioId, portfolios, reloadKey]);

  async function submit(e) {
    e.preventDefault();
    setSubmitting(true); setError(null);
    try {
      await api.createDeposit({
        sub_account_id: subAccountId,
        amount,
        type,
        note: note || null,
      });
      setAmount(''); setNote('');
      setReloadKey((x) => x + 1);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id) {
    if (!confirm('Delete this entry?')) return;
    try {
      await api.deleteDeposit(id);
      setReloadKey((x) => x + 1);
    } catch (e) {
      setError(e.message);
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

  return (
    <>
      <div className="page-header"><h1>Deposits & Withdrawals</h1></div>

      <div className="dash-duo" style={{ alignItems: 'start' }}>
        {/* Left: form */}
        <div className="panel" style={{ marginBottom: 0 }}>
          <h2>New Entry</h2>
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
            <div className="form-row">
              <label>Type</label>
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="DEPOSIT">Deposit</option>
                <option value="WITHDRAW">Withdraw</option>
              </select>
            </div>
            <div className="form-row">
              <label>Amount</label>
              <input type="number" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />
            </div>
            <div className="form-row">
              <label>Note</label>
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional" />
            </div>
            {error && <div className="error">{error}</div>}
            <button disabled={submitting || !amount}>
              {submitting ? 'Saving…' : 'Record Entry'}
            </button>
          </form>
        </div>

        {/* Right: history */}
        <div className="panel" style={{ marginBottom: 0 }}>
          <h2>History</h2>
          {items.length === 0 ? (
            <p className="muted">No entries yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Date</th><th>Type</th><th>Account</th>
                  <th>Amount</th><th>Note</th><th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id}>
                    <td>{new Date(d.datetime).toLocaleDateString()}</td>
                    <td><span className={`badge ${d.type === 'DEPOSIT' ? 'green' : 'red'}`}>{d.type}</span></td>
                    <td>{subAccountById.get(d.sub_account_id)?.name || '—'}</td>
                    <td>{fmtMoney(d.amount)}</td>
                    <td className="muted">{d.note || '—'}</td>
                    <td>
                      <button className="danger tiny" onClick={() => remove(d.id)}>Del</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
