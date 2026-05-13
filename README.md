# CryptoJournal

> Self-hosted personal crypto trading journal with institutional-grade analytics.
> Track spot + futures trades, deposits, P&L, drawdown, VaR, per-asset contribution,
> rolling Sharpe — all running locally against a SQLite database you own.

![CryptoJournal Dashboard](docs/screenshots/dashboard.png)

---

## Quick Start

### One-line install (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.sh | bash
```

### One-line install (Windows PowerShell)

```powershell
irm https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.ps1 | iex
```

The installer:
1. Checks for `git`, Python 3.10+, and Node 18+ (installs missing ones via Homebrew / apt / dnf / pacman)
2. Clones the repo to `~/crypto_journal`
3. Creates a Python venv + installs all deps
4. Installs `npm` packages for the frontend
5. Runs Alembic migrations to create the SQLite schema
6. Starts the backend (port 8000) + frontend (port 5173)
7. Opens [http://localhost:5173](http://localhost:5173) in your browser

Total time: ~2 minutes on a fresh machine.

---

## Manual install (if you prefer)

```bash
git clone https://github.com/Grabriel289/trading_journal.git
cd REPO
./dev.sh          # macOS / Linux
.\dev.ps1         # Windows
```

That's it. `dev.sh` / `dev.ps1` handles dependency install, schema migration, and starting both servers in one command.

---

## What's Inside

### Pages

| Page | What it shows |
|---|---|
| **Dashboard** | Equity curve, drawdown chart, asset allocation donut, key cards |
| **New Order** | Spot + futures order entry with strategy/tag/venue/order-type metadata |
| **Trade History** | Closed round-trips with gross/funding/net P&L split, plus all raw orders |
| **Statistics** | MyFXBook-style summary: Sharpe, Sortino, Calmar, drawdown, Z-score, profitability bar, hourly/daily heatmaps, risk-of-ruin, MAE/MFE scatter |
| **Performance** | Asset contribution % to portfolio return, per-coin trading skill table, rolling 30d Sharpe + volatility charts, VaR-95/99, skewness, kurtosis |
| **Deposits** | Cash flow log (deposits + withdrawals) feeding TWR/MWR calculations |
| **Import/Export** | CSV import with FIFO matching + auto-create strategies/tags, full orders export |
| **Pricing** | Live + manual price overrides per asset, source priority chain (Binance/Kucoin/CoinGecko/Manual) |
| **Setup** | Portfolio + sub-account management, fee rates, benchmark, HWM |

### Key Features

- **Institutional analytics:** TWR (time-weighted return), MWR (IRR), VaR, CVaR, parametric VaR, tail ratio, alpha/beta vs benchmark, tracking error, information ratio, up/down capture, Pearson correlation matrix, P&L waterfall, exposure breakdown (Herfindahl + sector), strategy attribution, slippage by venue/order type
- **Live + manual pricing:** Binance → Kucoin → CoinGecko fallback chain. Bulk manual price overrides with audit history for tokens not on any exchange
- **Background jobs:** Daily snapshot (00:00 UTC), benchmark sync (00:05 UTC), funding rate sync every 8h
- **FIFO lot matching:** Sell orders auto-match against oldest open buy with correct fee allocation
- **CSV-driven backfill:** Import historical trades + auto-rebuild equity snapshots
- **No cloud, no signup:** SQLite database lives in `data/cryptojournal.db`. Your trades never leave your machine.

---

## Requirements

| Tool | Minimum version | How to install |
|---|---|---|
| Python | 3.10+ | macOS: `brew install python@3.12`. Linux: `apt install python3.12`. Windows: [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | macOS: `brew install node`. Linux: `apt install nodejs`. Windows: [nodejs.org](https://nodejs.org/) |
| Git | any recent | Pre-installed on macOS/Linux. Windows: [git-scm.com](https://git-scm.com/) |

The one-line installer auto-detects and installs these via your system's package manager.

---

## Common Commands

```bash
./dev.sh                  # install (if needed) + start backend + frontend + open browser
./dev.sh --install-only   # set up deps without starting
./dev.sh --reset          # wipe .venv, node_modules, and the SQLite DB (clean slate)

NO_BROWSER=1 ./dev.sh     # skip browser auto-open (useful over SSH or in CI)
BACKEND_PORT=9000 ./dev.sh    # change backend port
FRONTEND_PORT=3000 ./dev.sh   # change frontend port

make dev / make install / make reset / make backend / make frontend / make build
```

---

## Project Layout

```
crypto_journal/
├── backend/              FastAPI + SQLAlchemy + APScheduler
│   ├── api/              HTTP routers (portfolio, orders, stats, ...)
│   ├── calculators/      Pure-function P&L, drawdown, VaR, TWR, ...
│   ├── services/         DB-backed services (portfolio, orders, stats, snapshot, price, ...)
│   ├── models/           SQLAlchemy ORM tables
│   ├── jobs/             APScheduler background jobs
│   ├── exchange/         Binance / Kucoin / CoinGecko adapters
│   └── main.py           App factory + lifespan
├── frontend/             React 18 + Vite + Chart.js
│   └── src/
│       ├── pages/        Dashboard, NewOrder, TradeHistory, Statistics, Performance, ...
│       └── components/   EquityCurve, DrawdownChart, AssetAllocation, ...
├── alembic/              Schema migrations (10 revisions)
├── data/                 SQLite DB (gitignored)
├── dev.sh / dev.ps1      One-command run script
├── install.sh / install.ps1   First-time bootstrapper (curl | bash entry point)
└── requirements.txt      Python deps
```

---

## Troubleshooting

### macOS without Homebrew
The installer will detect that Homebrew is missing and install it automatically — you'll be prompted for your Mac password mid-install. If you'd rather skip Homebrew entirely, install Python 3.10+ and Node 18+ manually (e.g. from python.org and nodejs.org), then:

```bash
git clone https://github.com/Grabriel289/trading_journal.git
cd trading_journal
./dev.sh
```

### Installer fails with "Homebrew install failed"
If something goes wrong during the auto-Homebrew step (network issue, bad sudo password, etc.), install Homebrew manually then re-run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
curl -fsSL https://raw.githubusercontent.com/Grabriel289/trading_journal/main/install.sh | bash
```

### "port 5173 already in use"
A previous Vite dev server is still running. Find and kill it:

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN     # find PID
kill <pid>
```

Or use a different port: `FRONTEND_PORT=5174 ./dev.sh`

### "Python 3.10+ not found"
The script needs Python 3.10 or newer. Check with `python3 --version`. macOS users often have an old Python 3.9 from system or anaconda — install a fresh one with `brew install python@3.12` and re-run.

### Dashboard shows "—" or zero everywhere
You haven't taken any equity snapshots yet. Either:
1. Click "Take Snapshot" on the Dashboard, or
2. Go to Setup → "Backfill snapshots" to rebuild historical snapshots from your transaction history

### Token has no price / dashboard errors
You're holding a token that no configured exchange knows about (e.g. a brand-new memecoin). Go to **Pricing** → find the token → click "Manual override" and set a price. The dashboard will use that until you remove the override.

### "alembic upgrade head" fails
Your DB was created by an older version of the code. Run `./dev.sh --reset` to wipe everything (⚠️ deletes all your trades) or back up `data/cryptojournal.db` and reset manually.

---

## Screenshots

<!--
TODO: capture and drop into docs/screenshots/

- dashboard.png           Main dashboard with equity + drawdown + cards
- new-order.png           Order entry form with advanced metadata panel
- trade-history.png       Closed trades table with gross/funding/net P&L split
- statistics.png          MyFXBook-style summary tab
- performance.png         Asset contribution + rolling Sharpe + risk table
- pricing.png             Manual price override modal
-->

| Dashboard | Performance | Statistics |
|---|---|---|
| _(coming soon)_ | _(coming soon)_ | _(coming soon)_ |

---

## License

MIT — do whatever you want with it. Not financial advice. Not affiliated with any exchange.
