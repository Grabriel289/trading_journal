# Calc Tab — Perpetual Position Sizing Calculator

> **Purpose:** คำนวณ position size ที่ถูกต้องก่อนเข้า trade ทุกครั้ง
> ไม่ต้องเปิด spreadsheet แยก ไม่ต้องคำนวณในหัว — ใส่ capital + risk % + stop loss model
> ได้คำตอบทันทีว่า "ใส่กี่ contract, SL ที่ไหน, ขาดทุนเท่าไหร่"
>
> Tab นี้เป็น **standalone utility** — ไม่ต้องมี portfolio, ไม่ต้องมี trade history
> เปิดใช้ได้ทันทีวันแรกที่ install app

---

## Core Concept: The 2% Rule

```
Capital = $500
Risk Per Trade = 2% of capital
Dollar Risk = $500 × 2% = $10

ไม่ว่าจะใช้ leverage เท่าไหร่ → dollar risk คงที่ = $10
Leverage แค่กำหนดว่าต้องวาง margin เท่าไหร่ ไม่ได้เปลี่ยน risk

ถ้ากำหนด SL Distance 2% → Position Size ต้องเป็นเท่าไหร่?
  Max Notional = $10 / 2% = $500
  Position Size = $500 / current_price

Leverage กำหนดแค่ margin:
  5x → ต้องวาง margin $500 / 5 = $100 (เหลือ $400 เปิด position อื่นได้)
  10x → ต้องวาง margin $500 / 10 = $50 (เหลือ $450)

แต่ถ้าใช้ full buying power ($2,500 ที่ 5x) กับ SL 2%:
  Loss = $2,500 × 2% = $50 → 10% ของ capital ← อันตราย!
```

**Key Insight:** Leverage ไม่ได้เปลี่ยน dollar risk — leverage แค่กำหนด margin ที่ต้องวาง
Position Size ถูกกำหนดโดย risk budget ($10) และ SL distance ไม่ใช่โดย leverage
ถ้าเปิด position เท่ากับ full buying power จะเสี่ยงเกิน 2% ของ capital → ผิดหลัก risk management

---

## Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  🧮 Position Calculator                                             │
│                                                                     │
│  ┌─ INPUT PANEL ──────────────────────────────────────────────────┐ │
│  │                                                                │ │
│  │  Asset     [BTC    ]     Entry Price  [$104,250.00]            │ │
│  │  Direction [Long ▼]    Capital      [$500.00]                 │ │
│  │  Leverage  [5x  ▼]    Risk %       [2.0%]                    │ │
│  │                                                                │ │
│  │  ── Stop Loss Model ──────────────────────────────────────     │ │
│  │  (●) Fixed Stop Loss     ( ) ATR Volatility Model             │ │
│  │                                                                │ │
│  │  [Fixed: SL % from entry]    [ATR: manual value × multiplier] │ │
│  │  Stop Loss %  [2.0%]         ATR Value  [$1,890.50]           │ │
│  │                               ATR Multi  [1.5]                │ │
│  │                                                                │ │
│  │                        [ CALCULATE ]                           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ RESULT CARDS ─────────────────────────────────────────────────┐ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │ │
│  │  │ Dollar   │ │ Position │ │ Notional │ │ Margin   │         │ │
│  │  │ Risk     │ │ Size     │ │ Value    │ │ Required │         │ │
│  │  │ $10.00   │ │0.0048 BTC│ │ $500     │ │ $100     │         │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │ │
│  │  │ Entry    │ │ Stop Loss│ │ SL Dist  │ │ Liq.     │         │ │
│  │  │ Price    │ │ Price    │ │ (% / $)  │ │ Price    │         │ │
│  │  │$104,250  │ │$102,165  │ │2%/$2,085 │ │$83,921   │         │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ RISK BREAKDOWN TABLE ─────────────────────────────────────────┐ │
│  │  Metric                    │  Value                            │ │
│  │  ─────────────────────────────────────────────────────         │ │
│  │  Account Capital           │  $500.00                          │ │
│  │  Risk Per Trade            │  2.0% → $10.00                   │ │
│  │  Leverage                  │  5x                               │ │
│  │  Notional Value            │  $500.00 (sized by risk, not lev) │ │
│  │  Position Size             │  0.004796 BTC                     │ │
│  │  Entry Price               │  $104,250.00                      │ │
│  │  Stop Loss Price           │  $102,165.00 (Long)              │ │
│  │  SL Distance               │  2.00% ($2,085.00 per BTC)       │ │
│  │  Dollar at Risk            │  $10.00                           │ │
│  │  Margin Required           │  $100.00 (= notional / leverage) │ │
│  │  Liquidation Price         │  $83,921.25 (est.)               │ │
│  │  Distance to Liquidation   │  19.51%                          │ │
│  │  Risk/Reward @ 1:2         │  TP $106,335 → profit $20.00    │ │
│  │  Risk/Reward @ 1:3         │  TP $110,505 → profit $30.00    │ │
│  │  ─────────────────────────────────────────────────────         │ │
│  │  ATR (14, 4H)              │  $1,890.50 (1.81%)   ← only if  │ │
│  │  ATR-Based SL              │  $1,890.50 × 1.5 = $2,835.75    │ │  ATR model
│  │  ATR SL %                  │  2.72%                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─ LEVERAGE COMPARISON TABLE ────────────────────────────────────┐ │
│  │  Lev │ Max Not. │ Margin │ SL Dist% │ SL Price │ Liq Price   │ │
│  │  ──────────────────────────────────────────────────────────    │ │
│  │  1x  │ $500     │ $500   │ 2.00%    │ $102,165 │ N/A         │ │
│  │  2x  │ $1,000   │ $500   │ 1.00%    │ $103,208 │ $52,646     │ │
│  │  3x  │ $1,500   │ $500   │ 0.67%    │ $103,554 │ $69,849     │ │
│  │ →5x  │ $2,500   │ $500   │ 0.40%    │ $103,833 │ $83,921     │ │
│  │  10x │ $5,000   │ $500   │ 0.20%    │ $104,042 │ $94,346     │ │
│  │  20x │ $10,000  │ $500   │ 0.10%    │ $104,146 │ $99,559     │ │
│  │  50x │ $25,000  │ $500   │ 0.04%    │ $104,208 │ $102,686    │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ↑ ไฮไลท์แถวที่ user เลือก (→) + สีแดงถ้า SL Dist < ATR (ถ้าใส่ ATR value) │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Input Panel — Fields

### Row 1: Asset & Price

| Field | Type | Default | Notes |
|---|---|---|---|
| **Asset** | Text input | BTC | Free-type — พิมพ์ชื่อเหรียญเอง (ใช้แค่แสดงใน result, ไม่ fetch อะไร) |
| **Entry Price** | Number input | — (required) | **User ใส่เอง** — ดูราคาจาก exchange ที่จะเทรดจริง, ไม่ดึง API เพราะราคาต่าง exchange ต่างกัน |
| **Direction** | Toggle | Long | `Long` / `Short` — กระทบทิศทาง SL price |
| **Capital** | Number input | — (required) | เงินทุนทั้งหมดของ account เช่น $500 |
| **Leverage** | Dropdown | 5x | Options: `1x, 2x, 3x, 5x, 7x, 10x, 15x, 20x, 25x, 50x, 75x, 100x, 125x` |
| **Risk %** | Number input | 2.0 | % ของ **capital** ที่ยอมเสียได้ต่อ 1 trade — **editable**, default 2% แต่เปลี่ยนได้ตามต้องการ |

### Row 2: Stop Loss Model

Radio toggle ระหว่าง 2 models:

#### Model A: Fixed Stop Loss

| Field | Type | Default | Notes |
|---|---|---|---|
| **SL Distance %** | Number input | 2.0 | ระยะห่าง SL จาก entry เป็น % |

→ User กำหนด SL % เอง, calculator คำนวณ position size ที่ทำให้ dollar risk ตรงกับ risk %

#### Model B: ATR Volatility Model

| Field | Type | Default | Notes |
|---|---|---|---|
| **ATR Value** | Number input | — (required) | ค่า ATR เป็น dollar ที่ user ดูมาจาก TradingView / charting platform เอง |
| **ATR Multiplier** | Number input | 1.5 | SL = entry ± (ATR × multiplier) |

→ User ใส่ค่า ATR เอง (เพราะรู้อยู่แล้วว่าจะเทรด TF ไหน, ดูจาก chart ก่อนมาคำนวณ)
→ Calculator เอา ATR × multiplier = SL distance → แล้วคำนวณ position size จาก SL distance นั้น
→ **ไม่ fetch จาก Binance** — เพราะ ATR ต่าง TF ต่างค่า, user ตัดสินใจเองว่าจะใช้ค่าไหน

---

## Calculation Formulas

### Core Formulas (ใช้ทั้ง 2 models)

```
─── INPUTS ────────────────────────────────────────
capital          = user input (e.g., $500)
risk_pct         = user input (e.g., 2.0%)
leverage         = user input (e.g., 5)
entry_price      = user input (manual)
direction        = LONG or SHORT

─── DERIVED ───────────────────────────────────────
dollar_risk      = capital × (risk_pct / 100)
                 = $500 × 0.02 = $10.00
                 # Risk คิดจาก capital เท่านั้น
                 # Leverage ไม่เปลี่ยน dollar risk

max_buying_power = capital × leverage
                 = $500 × 5 = $2,500.00   # ใช้เป็น constraint

─── FROM STOP LOSS MODEL ──────────────────────────
sl_distance_pct  = (Fixed model: user input)
                   (ATR model: atr_value × multiplier / entry_price × 100)

─── POSITION SIZING ───────────────────────────────
# Given SL % → calculate position size that fits risk budget
notional_value   = dollar_risk / (sl_distance_pct / 100)
                 = $10 / 0.02 = $500.00
position_size    = notional_value / entry_price
                 = $500 / $104,250 = 0.004796 BTC
margin_required  = notional_value / leverage
                 = $500 / 5 = $100.00

# Check: does the position fit within leverage constraint?
if margin_required > capital:
    # Position too big for this leverage — cap at max buying power
    notional_value = max_buying_power
    position_size = notional_value / entry_price
    actual_risk = notional_value × (sl_distance_pct / 100)
    # WARNING: actual risk ($X) exceeds target ($Y)

─── STOP LOSS PRICE ───────────────────────────────
if direction == LONG:
    sl_price = entry_price × (1 - sl_distance_pct / 100)
else:  # SHORT
    sl_price = entry_price × (1 + sl_distance_pct / 100)

─── LIQUIDATION PRICE (estimated) ─────────────────
# Simplified Binance-style (cross margin, 0.5% maintenance margin rate)
maint_margin_rate = 0.005
if direction == LONG:
    liq_price = entry_price × (1 - 1/leverage + maint_margin_rate)
else:
    liq_price = entry_price × (1 + 1/leverage - maint_margin_rate)

distance_to_liq  = abs(entry_price - liq_price) / entry_price × 100

─── RISK/REWARD PROJECTIONS ───────────────────────
for ratio in [1, 1.5, 2, 3]:
    reward_distance = sl_distance_pct × ratio
    if direction == LONG:
        tp_price = entry_price × (1 + reward_distance / 100)
    else:
        tp_price = entry_price × (1 - reward_distance / 100)
    potential_profit = dollar_risk × ratio
```

### ATR Calculation (Model B only)

```
─── ATR INPUT (manual) ────────────────────────────
# User ดูค่า ATR จาก TradingView / charting platform แล้วใส่เอง
# เช่น BTC ATR(14) บน 4H = $1,890.50
atr_value = user_input                     # e.g., 1890.50

─── ATR-BASED STOP LOSS ──────────────────────────
atr_sl_distance = atr_value × atr_multiplier               # in dollar terms
                = $1,890.50 × 1.5 = $2,835.75

atr_sl_pct      = atr_sl_distance / entry_price × 100      # as percentage
                = $2,835.75 / $104,250 × 100 = 2.72%

# Then use atr_sl_pct as sl_distance_pct in core formulas
```

> **ทำไมไม่ fetch ATR จาก Binance?**
> เพราะ ATR ขึ้นกับ timeframe ที่ใช้เทรด — ATR(14) บน 1H ≠ 4H ≠ 1D
> Trader รู้อยู่แล้วว่าจะเทรด TF ไหน และดูค่า ATR จาก chart ก่อนมาคำนวณ
> การให้ user ใส่เองตรงกว่า ถูกกว่า และไม่ต้องพึ่ง API call

---

## Result Cards — 8 Cards

ด้านบนของ output, แสดงเป็น card grid 4×2

| Card | Value | Color Rule |
|---|---|---|
| **Dollar Risk** | `$10.00` | Red always (this is what you can lose) |
| **Position Size** | `0.004796 BTC` | Neutral — accent color |
| **Notional Value** | `$500.00` | Neutral |
| **Margin Required** | `$100.00` | Neutral |
| **Entry Price** | `$104,250.00` | Neutral |
| **Stop Loss Price** | `$102,165.00` | Red |
| **SL Distance** | `2.00% / $2,085` | Red |
| **Liquidation Price** | `$83,609` | Red, dimmer if far away |

Card layout:

```css
.calc-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
@media (max-width: 767px) {
  .calc-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
```

---

## Risk Breakdown Table

Detailed breakdown ด้านล่าง cards — แสดงทุก step ของ calculation

| Row | Label | Value | Notes |
|---|---|---|---|
| 1 | Account Capital | `$500.00` | Input |
| 2 | Risk Per Trade | `2.0% → $10.00` | `capital × risk_pct = dollar_risk` |
| 3 | Leverage | `5x` | Input |
| 4 | Notional Value | `$500.00` | `dollar_risk / sl_distance` (sized by risk, not by leverage) |
| 5 | Position Size | `0.004796 BTC` | `notional / entry_price` |
| 6 | Entry Price | `$104,250.00` | User input (manual) |
| 7 | Stop Loss Price | `$102,165.00 (Long)` | Calculated, shows direction |
| 8 | SL Distance | `2.00% ($2,085.00/BTC)` | Both % and dollar per unit |
| 9 | Dollar at Risk | `$10.00` | **The answer** — bold, red |
| 10 | Margin Required | `$100.00` | `notional / leverage` — ใช้ margin น้อยกว่า capital |
| 11 | Liquidation Price | `$83,921.25 (est.)` | Estimated, with disclaimer |
| 12 | Distance to Liquidation | `19.51%` | Green if > 10%, yellow 5-10%, red < 5% |
| 13 | — | — | Divider |
| 14 | R:R @ 1:1 | `TP $106,335 → profit $10.00` | Green |
| 15 | R:R @ 1:1.5 | `TP $107,378 → profit $15.00` | Green |
| 16 | R:R @ 1:2 | `TP $108,420 → profit $20.00` | Green |
| 17 | R:R @ 1:3 | `TP $110,505 → profit $30.00` | Green |
| — | — | — | ATR section (only if ATR model selected) |
| 17 | ATR Value | `$1,890.50 (1.81%)` | User input, % = ATR / entry_price |
| 18 | ATR × Multiplier | `$1,890.50 × 1.5 = $2,835.75` | Raw ATR SL distance |
| 19 | ATR SL % | `2.72%` | ATR distance as % of entry |

---

## Leverage Comparison Table

**หัวใจของ tab นี้** — แสดงให้เห็นชัดว่าถ้าใช้ full buying power ที่แต่ละ leverage → SL ต้องแคบลงแค่ไหน

ตารางนี้สมมติว่าเปิด position เต็ม buying power (capital × leverage) แล้วดูว่า:
SL ต้องแคบเท่าไหร่ถึงจะเสียไม่เกิน $10 (dollar risk)

| Column | Description |
|---|---|
| **Lev** | Leverage level |
| **Max Not.** | `capital × leverage` — max notional ถ้าใช้เต็ม |
| **Margin** | Always = capital (same for all rows) |
| **SL Dist %** | `dollar_risk / max_notional × 100` — **ยิ่ง leverage สูง ยิ่งแคบ** |
| **SL Price** | Entry ± SL Dist |
| **Liq Price** | Estimated liquidation price — **ยิ่ง leverage สูง ยิ่งใกล้ SL** |

> **Key Insight:** ที่ 5x → SL ต้องแคบเหลือ 0.40% ราคาขยับนิดเดียวก็โดน SL
> ที่ 50x → SL แค่ 0.04% แทบจะ noise stop-out ทันที
> นี่คือเหตุผลที่ Position Size ควรกำหนดจาก risk budget ไม่ใช่จาก leverage เต็ม

### Fixed rows: `1x, 2x, 3x, 5x, 10x, 20x, 50x`

### Visual rules:

```
Current leverage row:
  → highlight with accent background
  → show "→" marker on left

SL Dist % < ATR range (if user filled ATR value, regardless of model):
  → Red background tint
  → Tooltip: "SL tighter than 1 ATR — high chance of noise stop-out"

SL Dist % > 0.5%:
  → Normal (white text)

SL Dist % 0.1% – 0.5%:
  → Yellow text (tight)

SL Dist % < 0.1%:
  → Red text (extremely tight, likely noise stop-out)

Distance between SL and Liquidation < 5%:
  → Red warning icon ⚠️
  → Tooltip: "SL dangerously close to liquidation price"
```

---

## Warnings & Safety Alerts

แสดงเป็น alert box ด้านบน result section เมื่อเจอ edge case:

### Warning 1: Risk exceeds target

```
⚠️ Actual risk ($50.00) exceeds target ($10.00)
Position capped at full buying power ($2,500) because SL (2%) is wider than risk budget allows.
Actual dollar risk: $50.00 (10% of capital). Consider: tighter SL or lower leverage.
```

**Trigger:** `required_margin > capital` (position size limited by capital, not by risk %)

### Warning 2: SL inside noise range (only if ATR value filled)

```
⚠️ Stop loss (0.40%) is tighter than 1 ATR (1.81%)
At 5x leverage with 2% risk, your SL will be hit by normal price fluctuation.
Consider: lower leverage, wider risk %, or switch to ATR model.
```

**Trigger:** Fixed model selected AND user has filled ATR value AND `sl_distance_pct < (atr_value / entry_price × 100)`
(เปรียบเทียบ Fixed SL กับ ATR ที่ user ใส่ไว้ — ถ้า ATR value ว่าง ไม่ trigger)

### Warning 3: SL close to liquidation

```
🔴 Stop loss ($103,833) is within 5% of liquidation ($103,609)
Slippage or a wick could liquidate you before SL triggers.
Reduce leverage or widen stop loss.
```

**Trigger:** `abs(sl_price - liq_price) / entry_price < 0.05`

### Warning 4: Extreme leverage

```
⚠️ At 50x+ leverage, exchange fees (~0.04% per side) consume a significant
portion of your SL distance (0.04%). Effective risk may be 2-3x stated risk.
```

**Trigger:** `leverage >= 50`

---

## Backend Endpoint

### ไม่ต้องสร้าง endpoint ใหม่ — Zero API Calls

Tab นี้เป็น **100% frontend calculation** — ไม่มี API call เลยแม้แต่ตัวเดียว

| Data | Source | Notes |
|---|---|---|
| Entry Price | **User input** | ดูราคาจาก exchange ที่จะเทรดจริง (ต่าง exchange ต่างราคา) |
| ATR Value | **User input** | ดูจาก TradingView แล้วใส่เอง |
| ทุก calculation อื่น | **Frontend pure math** | Position size, SL, liquidation, R:R, leverage table |

> **ทำไมไม่ดึงราคาจาก API?**
> เพราะ trader เทรดหลาย exchange (Binance, OKX, Bybit, Hyperliquid)
> ราคาต่าง exchange ต่างกัน — ถ้าดึงจาก Binance แต่เทรด Hyperliquid ค่าจะเพี้ยน
> User ดูราคาจาก exchange ที่จะเปิด position จริงแล้วมาใส่เอง = ถูกต้อง 100%

ผลลัพธ์: update real-time ทันทีเมื่อ user พิมพ์ (ไม่มี loading, ไม่มี network latency)

---

## Frontend Component Structure

### File: `frontend/src/pages/Calc.jsx`

```
Calc (page)
├── PageHeader ("Position Calculator")
├── InputPanel
│   ├── AssetPriceRow (asset dropdown + entry price + direction)
│   ├── CapitalRow (capital + leverage + risk %)
│   └── StopLossModelSection
│       ├── RadioToggle (Fixed / ATR)
│       ├── FixedInputs (SL %) — visible when Fixed selected
│       └── AtrInputs (period + multiplier + timeframe) — visible when ATR selected
├── WarningAlerts (conditional)
├── ResultCards (8 cards grid)
├── RiskBreakdownTable
└── LeverageComparisonTable
```

### State Management

```javascript
// All state in single useState or useReducer
const [inputs, setInputs] = useState({
  asset: 'BTC',
  entryPrice: '',         // user ใส่เองจาก exchange ที่จะเทรด
  direction: 'LONG',
  capital: '',
  leverage: 5,
  riskPct: 2.0,           // default 2%, editable
  slModel: 'fixed',       // 'fixed' | 'atr'
  fixedSlPct: 2.0,
  atrValue: '',           // user ใส่เอง — ATR in dollar จาก TradingView
  atrMultiplier: 1.5,
});

// Zero state — no loading, no API calls
// Results computed reactively — instant re-calc on every keystroke
const results = useMemo(() => {
  return calculatePosition(inputs);
}, [inputs]);
```

### Reactivity (no API calls at all)

```
User types in ANY field (asset, price, capital, leverage, risk%, SL%, ATR, multiplier):
  → Results re-compute instantly via useMemo (pure math, zero latency)
  → No debounce needed — calculation is trivial arithmetic

User switches SL model (Fixed ↔ ATR):
  → Show/hide relevant input fields
  → Results re-compute with new model's SL distance

No API calls. No loading states. No network dependency.
Tab works completely offline.
```

---

## API Additions to `api.js`

ไม่ต้องเพิ่ม — tab นี้ไม่เรียก API เลยแม้แต่ตัวเดียว

---

## Route Addition to `App.jsx`

```javascript
import Calc from './pages/Calc.jsx';

// In nav:
<NavLink to="/calc">Calculator</NavLink>

// In routes:
<Route path="/calc" element={<Calc />} />
```

Nav position: **after Statistics, before Performance**
(เพราะ flow คือ: ดู stats → คำนวณ position → ดู performance)

```
Dashboard | New Order | Trade History | Statistics | Calculator | Performance | ...
```

---

## Styling

### Input Panel

```css
.calc-input-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--radius);
  padding: 20px;
}

.calc-input-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.calc-input-group label {
  display: block;
  font-size: 11px;
  color: var(--txt-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.calc-input-group input,
.calc-input-group select {
  width: 100%;
  padding: 8px 12px;
  background: var(--bg-mid);
  border: 1px solid var(--border-card);
  border-radius: 6px;
  color: var(--txt-primary);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.calc-input-group input:focus {
  border-color: var(--accent);
  outline: none;
}
```

### SL Model Radio Toggle

```css
.sl-model-toggle {
  display: flex;
  gap: 0;
  border: 1px solid var(--border-card);
  border-radius: 8px;
  overflow: hidden;
  width: fit-content;
}

.sl-model-toggle button {
  padding: 8px 20px;
  background: var(--bg-mid);
  border: none;
  color: var(--txt-secondary);
  cursor: pointer;
  font-size: 13px;
}

.sl-model-toggle button.active {
  background: var(--accent-dim);
  color: var(--accent);
  font-weight: 600;
}
```

### Warning Alerts

```css
.calc-warning {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.calc-warning.yellow {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  color: #f59e0b;
}

.calc-warning.red {
  background: var(--red-dim);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: var(--red);
}
```

### Leverage Comparison Table Highlight

```css
.lev-table tr.current-lev {
  background: var(--accent-dim);
}

.lev-table tr.current-lev td:first-child::before {
  content: '→ ';
  color: var(--accent);
  font-weight: bold;
}

.lev-table td.danger-sl {
  color: var(--red);
}

.lev-table td.tight-sl {
  color: #f59e0b;
}
```

---

## Responsive Layout

### Desktop (≥ 1024px)

```
Input Panel: 3 columns grid
Result Cards: 4 columns
Breakdown + Leverage: full width
```

### Tablet (768px – 1023px)

```
Input Panel: 2 columns
Result Cards: 4 columns (smaller)
```

### Mobile (< 768px)

```
Input Panel: 1 column (stacked)
Result Cards: 2 columns
Tables: horizontal scroll
```

---

## Edge Cases & Validation

| Case | Behavior |
|---|---|
| Capital = 0 or empty | Disable CALCULATE, show "Enter capital" |
| Entry Price = 0 | Disable CALCULATE |
| Risk % > 100 | Cap at 100, show warning |
| Risk % = 0 | Disable CALCULATE |
| SL % = 0 (fixed model) | Disable CALCULATE, show "SL distance required" |
| SL % > 50% | Allow but show warning "Extremely wide stop loss" |
| ATR value = 0 or empty | Disable CALCULATE when ATR model selected, show "Enter ATR value from your chart" |
| Position size < exchange minimum | Show warning "Position below minimum order size" |
| Leverage 1x + LONG | Liquidation = $0 → show "N/A (spot equivalent)" |
| Asset empty | Optional — ใช้แค่แสดงใน result, ไม่ block calculation |

---

## Implementation Checklist

### Backend
- [ ] ไม่ต้องแตะ backend เลย — zero API calls

### Frontend
- [ ] Create `frontend/src/pages/Calc.jsx`
- [ ] Add route + nav link in `App.jsx`
- [ ] Implement `calculatePosition()` pure function (all formulas)
- [ ] Implement InputPanel with asset/price auto-fill
- [ ] Implement SL model radio toggle (Fixed / ATR)
- [ ] Implement ResultCards (8 cards)
- [ ] Implement RiskBreakdownTable
- [ ] Implement LeverageComparisonTable with highlight + warnings
- [ ] Implement warning alerts (4 types)
- [ ] Add CSS to `styles.css`

### Verify
- [ ] Enter $500 capital, 5x, 2% risk → dollar risk = $10 (2% of capital, leverage ไม่เปลี่ยน risk) ✓
- [ ] Fixed SL 2% → position size correct ✓
- [ ] Switch to ATR model → ใส่ ATR value $1,890 × 1.5 → SL = 2.72% ✓
- [ ] Change leverage in dropdown → leverage table highlights correct row ✓
- [ ] Short direction → SL price above entry ✓
- [ ] Leverage 50x → warning about fees ✓
- [ ] SL closer than ATR → warning about noise ✓
- [ ] Mobile layout → cards 2-col, tables scroll ✓
