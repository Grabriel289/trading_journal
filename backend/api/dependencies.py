from fastapi import Depends
from sqlalchemy.orm import Session

from backend.db.database import SessionLocal, get_db
from backend.exchange.binance import BinanceExchange
from backend.exchange.coingecko import CoinGeckoExchange
from backend.exchange.kucoin import KucoinExchange
from backend.services.asset_service import AssetService
from backend.services.backfill_service import BackfillService
from backend.services.deposit_service import DepositService
from backend.services.order_service import OrderService
from backend.services.portfolio_service import PortfolioService
from backend.services.price_service import PriceService
from backend.services.snapshot_service import SnapshotService
from backend.services.stats_service import StatsService
from backend.services.strategy_service import StrategyService

_binance   = BinanceExchange()
_kucoin    = KucoinExchange()
_coingecko = CoinGeckoExchange()
_price_service = PriceService(
    primary=_binance,
    kucoin=_kucoin,
    coingecko=_coingecko,
    session_factory=SessionLocal,
)


def get_price_service() -> PriceService:
    return _price_service


def get_portfolio_service(
    db: Session = Depends(get_db),
    prices: PriceService = Depends(get_price_service),
) -> PortfolioService:
    return PortfolioService(db=db, price_service=prices)


def get_order_service(
    db: Session = Depends(get_db),
    prices: PriceService = Depends(get_price_service),
) -> OrderService:
    return OrderService(db=db, price_service=prices)


def get_deposit_service(db: Session = Depends(get_db)) -> DepositService:
    return DepositService(db=db)


def get_snapshot_service(
    db: Session = Depends(get_db),
    portfolios: PortfolioService = Depends(get_portfolio_service),
) -> SnapshotService:
    return SnapshotService(db=db, portfolio_service=portfolios)


def get_stats_service(
    db: Session = Depends(get_db),
    prices: PriceService = Depends(get_price_service),
) -> StatsService:
    return StatsService(db=db, price_service=prices)


def get_backfill_service(
    db: Session = Depends(get_db),
    prices: PriceService = Depends(get_price_service),
) -> BackfillService:
    return BackfillService(db=db, price_service=prices)


def get_asset_service(db: Session = Depends(get_db)) -> AssetService:
    return AssetService(db=db)


def get_strategy_service(db: Session = Depends(get_db)) -> StrategyService:
    return StrategyService(db=db)
