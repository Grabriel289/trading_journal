import { useEffect, useState } from 'react';
import { NavLink, Route, Routes, Navigate } from 'react-router-dom';
import Calc from './pages/Calc.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Deposits from './pages/Deposits.jsx';
import ImportExport from './pages/ImportExport.jsx';
import NewOrder from './pages/NewOrder.jsx';
import Performance from './pages/Performance.jsx';
import Pricing from './pages/Pricing.jsx';
import Setup from './pages/Setup.jsx';
import Statistics from './pages/Statistics.jsx';
import TradeHistory from './pages/TradeHistory.jsx';
import { api } from './services/api.js';

function CurrencyBadge() {
  const [ccy, setCcy] = useState('USDT');
  useEffect(() => {
    api.listPortfolios()
      .then((ps) => { if (ps.length > 0) setCcy(ps[0].base_currency); })
      .catch(() => {});
  }, []);
  return <span className="nav-currency">{ccy}</span>;
}

export default function App() {
  return (
    <>
      <div className="stars" />
      <div className="stars-2" />
      <nav className="nav">
        <span className="brand">
          <span className="nav-logo">CJ</span>
          Crypto Journal
        </span>
        <NavLink to="/" end>Dashboard</NavLink>
        <NavLink to="/new-order">New Order</NavLink>
        <NavLink to="/trades">Trade History</NavLink>
        <NavLink to="/stats">Statistics</NavLink>
        <NavLink to="/calc">Calculator</NavLink>
        <NavLink to="/performance">Performance</NavLink>
        <NavLink to="/deposits">Deposits</NavLink>
        <NavLink to="/import">Import/Export</NavLink>
        <NavLink to="/pricing">Pricing</NavLink>
        <NavLink to="/setup">Setup</NavLink>
        <span className="nav-spacer" />
        <CurrencyBadge />
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new-order" element={<NewOrder />} />
          <Route path="/trades" element={<TradeHistory />} />
          <Route path="/stats" element={<Statistics />} />
          <Route path="/calc" element={<Calc />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/deposits" element={<Deposits />} />
          <Route path="/import" element={<ImportExport />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </>
  );
}
