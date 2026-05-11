async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  listPortfolios: () => request('/api/portfolio'),
  createPortfolio: (body) =>
    request('/api/portfolio', { method: 'POST', body: JSON.stringify(body) }),
  getPortfolio: (id) => request(`/api/portfolio/${id}`),
  updatePortfolio: (id, body) =>
    request(`/api/portfolio/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deletePortfolio: (id) =>
    request(`/api/portfolio/${id}`, { method: 'DELETE' }),
  addSubAccount: (id, body) =>
    request(`/api/portfolio/${id}/sub-account`, { method: 'POST', body: JSON.stringify(body) }),
  updateSubAccount: (sub_id, body) =>
    request(`/api/portfolio/sub-account/${sub_id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteSubAccount: (sub_id) =>
    request(`/api/portfolio/sub-account/${sub_id}`, { method: 'DELETE' }),
  getOverview: (id) => request(`/api/portfolio/${id}/overview`),

  listOrders: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/orders${qs ? `?${qs}` : ''}`);
  },
  createBuy: (body) =>
    request('/api/orders/buy', { method: 'POST', body: JSON.stringify(body) }),
  createSell: (body) =>
    request('/api/orders/sell', { method: 'POST', body: JSON.stringify(body) }),
  updateOrder: (order_id, body) =>
    request(`/api/orders/${order_id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteOrder: (order_id) =>
    request(`/api/orders/${order_id}`, { method: 'DELETE' }),
  updateFunding: (order_id, funding_accumulated) =>
    request(`/api/orders/${order_id}/funding`, {
      method: 'PATCH', body: JSON.stringify({ funding_accumulated }),
    }),
  getOpenBuys: (sub_account_id, asset) => {
    const qs = new URLSearchParams({ sub_account_id, ...(asset ? { asset } : {}) });
    return request(`/api/orders/open-buys?${qs}`);
  },
  getTrades: (portfolio_id) => request(`/api/portfolio/${portfolio_id}/trades`),

  listDeposits: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/deposits${qs ? `?${qs}` : ''}`);
  },
  createDeposit: (body) =>
    request('/api/deposits', { method: 'POST', body: JSON.stringify(body) }),
  deleteDeposit: (id) =>
    request(`/api/deposits/${id}`, { method: 'DELETE' }),

  getEquityCurve: (portfolio_id, range = 'ALL') =>
    request(`/api/dashboard/equity-curve?portfolio_id=${portfolio_id}&range=${range}`),
  takeSnapshot: (portfolio_id) =>
    request(`/api/dashboard/snapshot?portfolio_id=${portfolio_id}`, { method: 'POST' }),
  backfillSnapshots: (portfolio_id) =>
    request(`/api/dashboard/backfill?portfolio_id=${portfolio_id}`, { method: 'POST' }),
  wipePortfolioData: (portfolio_id) =>
    request(`/api/portfolio/${portfolio_id}/data`, { method: 'DELETE' }),

  statsSummary: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/summary?${qs}`);
  },
  statsBreakdown: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/trades-breakdown?${qs}`);
  },
  statsHourly: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/hourly?${qs}`);
  },
  statsDaily: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/daily?${qs}`);
  },
  statsRisk: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/risk-of-ruin?${qs}`);
  },
  statsDuration: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/duration?${qs}`);
  },
  statsMaeMfe: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/mae-mfe?${qs}`);
  },

  // Phase 2: Strategies
  listStrategies: (activeOnly = true) =>
    request(`/api/strategies?active_only=${activeOnly}`),
  createStrategy: (body) =>
    request('/api/strategies', { method: 'POST', body: JSON.stringify(body) }),
  updateStrategy: (id, body) =>
    request(`/api/strategies/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteStrategy: (id) =>
    request(`/api/strategies/${id}`, { method: 'DELETE' }),

  // Phase 2: Tags
  listTags: () => request('/api/tags'),
  createTag: (body) =>
    request('/api/tags', { method: 'POST', body: JSON.stringify(body) }),
  updateTag: (id, body) =>
    request(`/api/tags/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteTag: (id) =>
    request(`/api/tags/${id}`, { method: 'DELETE' }),

  // Phase 2: trade confirmation + funding payments
  getOrderConfirmation: (orderId) =>
    request(`/api/orders/${orderId}/confirmation`),
  getOrderFundingPayments: (orderId) =>
    request(`/api/orders/${orderId}/funding-payments`),

  getPrice: (asset, base = 'USDT') => request(`/api/prices/${asset}?base=${base}`),
  getQuote: (asset, base = 'USDT') => request(`/api/prices/${asset}/quote?base=${base}`),

  listAssets: () => request('/api/assets'),
  createAsset: (body) => request('/api/assets', { method: 'POST', body: JSON.stringify(body) }),
  getAsset: (symbol) => request(`/api/assets/${symbol}`),
  updateAsset: (symbol, body) =>
    request(`/api/assets/${symbol}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteAsset: (symbol) =>
    request(`/api/assets/${symbol}`, { method: 'DELETE' }),
  setManualPrice: (symbol, body) =>
    request(`/api/assets/${symbol}/manual-price`, { method: 'POST', body: JSON.stringify(body) }),
  bulkManualPrices: (items) =>
    request('/api/assets/manual-prices/bulk', {
      method: 'POST', body: JSON.stringify({ items }),
    }),
  clearManualOverride: (symbol) =>
    request(`/api/assets/${symbol}/manual-price`, { method: 'DELETE' }),
  getManualPriceHistory: (symbol) =>
    request(`/api/assets/${symbol}/manual-price-history`),
  upsertSource: (symbol, body) =>
    request(`/api/assets/${symbol}/sources`, { method: 'POST', body: JSON.stringify(body) }),
  removeSource: (symbol, source_type) =>
    request(`/api/assets/${symbol}/sources/${source_type}`, { method: 'DELETE' }),

  importCSV: async (portfolio_id, file, dry_run = false) => {
    const fd = new FormData();
    fd.append('file', file);
    const qs = new URLSearchParams({ portfolio_id, dry_run: String(dry_run) });
    const res = await fetch(`/api/import/csv?${qs}`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  templateURL: () => '/api/import/template',
  exportURL: (portfolio_id) =>
    // _ts cache-buster prevents the browser from re-serving a stale CSV.
    `/api/export/orders.csv?${new URLSearchParams({ portfolio_id, _ts: Date.now() })}`,

  triggerJob: (name) =>
    request(`/api/jobs/${name}`, { method: 'POST' }),

  // Phase 3: institutional analytics
  statsFunding: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/funding-analytics?${qs}`);
  },
  statsStrategyAttribution: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/strategy-attribution?${qs}`);
  },
  statsBenchmark: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/benchmark?${qs}`);
  },
  statsCorrelations: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/correlations?${qs}`);
  },
  statsExposure: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/exposure?${qs}`);
  },
  statsPnLWaterfall: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/pnl-waterfall?${qs}`);
  },
  statsSlippage: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/slippage?${qs}`);
  },

  // Performance tab redesign
  statsAssetPerformance: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/asset-performance?${qs}`);
  },
  statsPerCoinBreakdown: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/per-coin-breakdown?${qs}`);
  },
  statsRiskMetrics: (params) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/stats/risk-metrics?${qs}`);
  },
};
