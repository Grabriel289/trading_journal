from enum import Enum


class SubAccountType(str, Enum):
    SPOT = "SPOT"
    FUTURES = "FUTURES"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"
    CLOSED = "CLOSED"


class DepositType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"


class BaseCurrency(str, Enum):
    USDT = "USDT"
    USDC = "USDC"


# ---------------- Phase 2: order metadata ----------------

class OrderType(str, Enum):
    """How the order was executed on the exchange."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    UNKNOWN = "UNKNOWN"   # imported/legacy orders we have no detail for


class MakerTaker(str, Enum):
    """Whether the order added or removed liquidity."""
    MAKER = "MAKER"
    TAKER = "TAKER"
    UNKNOWN = "UNKNOWN"


class ExecutionVenue(str, Enum):
    """Exchange or OTC venue where the order was filled."""
    BINANCE_SPOT = "BINANCE_SPOT"
    BINANCE_FUTURES = "BINANCE_FUTURES"
    OKX_SPOT = "OKX_SPOT"
    OKX_FUTURES = "OKX_FUTURES"
    BYBIT_SPOT = "BYBIT_SPOT"
    BYBIT_FUTURES = "BYBIT_FUTURES"
    KUCOIN_SPOT = "KUCOIN_SPOT"
    KUCOIN_FUTURES = "KUCOIN_FUTURES"
    HYPERLIQUID = "HYPERLIQUID"
    DERIBIT = "DERIBIT"
    DEX = "DEX"
    OTC = "OTC"
    MANUAL = "MANUAL"     # manually entered, no exchange


# ---------------- Phase 2: asset classification ----------------

class Sector(str, Enum):
    """Crypto sector classification for exposure analysis."""
    LAYER_1 = "LAYER_1"           # BTC, ETH, SOL, AVAX
    LAYER_2 = "LAYER_2"           # ARB, OP, MATIC
    DEFI = "DEFI"                 # UNI, AAVE, MKR
    INFRASTRUCTURE = "INFRA"      # LINK, GRT, FIL
    GAMING = "GAMING"             # AXS, SAND, IMX
    AI = "AI"                     # RNDR, FET, OCEAN
    MEME = "MEME"                 # DOGE, SHIB, PEPE
    STABLECOIN = "STABLECOIN"     # USDT, USDC, DAI
    EXCHANGE = "EXCHANGE"         # BNB, CRO, FTT
    OTHER = "OTHER"


class Chain(str, Enum):
    """Primary blockchain for exposure breakdown."""
    BITCOIN = "BITCOIN"
    ETHEREUM = "ETHEREUM"
    SOLANA = "SOLANA"
    BNB_CHAIN = "BNB_CHAIN"
    AVALANCHE = "AVALANCHE"
    ARBITRUM = "ARBITRUM"
    OPTIMISM = "OPTIMISM"
    POLYGON = "POLYGON"
    BASE = "BASE"
    MULTI_CHAIN = "MULTI_CHAIN"
    OTHER = "OTHER"
