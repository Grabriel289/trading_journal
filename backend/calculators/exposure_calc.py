"""Exposure analysis — sector breakdown, Herfindahl concentration, leverage."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SectorExposure:
    sector: str
    gross_value: Decimal
    net_value: Decimal
    pct_of_nav: Decimal
    position_count: int
    assets: List[str]


@dataclass(frozen=True)
class ConcentrationMetrics:
    herfindahl_index: float
    top_1_pct: Decimal
    top_3_pct: Decimal
    top_5_pct: Decimal
    effective_positions: float


@dataclass(frozen=True)
class ExposureAnalysis:
    total_nav: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage_ratio: Decimal
    long_exposure: Decimal
    short_exposure: Decimal
    long_short_ratio: Optional[Decimal]
    sectors: List[SectorExposure]
    concentration: ConcentrationMetrics


def _empty(total_nav: Decimal) -> ExposureAnalysis:
    return ExposureAnalysis(
        total_nav=total_nav,
        gross_exposure=Decimal("0"),
        net_exposure=Decimal("0"),
        leverage_ratio=Decimal("0"),
        long_exposure=Decimal("0"),
        short_exposure=Decimal("0"),
        long_short_ratio=None,
        sectors=[],
        concentration=ConcentrationMetrics(
            herfindahl_index=0.0,
            top_1_pct=Decimal("0"), top_3_pct=Decimal("0"),
            top_5_pct=Decimal("0"), effective_positions=0.0,
        ),
    )


def calc_exposure(
    positions: list,
    asset_sectors: Dict[str, str],
    total_nav: Decimal,
) -> ExposureAnalysis:
    if not positions or total_nav <= 0:
        return _empty(total_nav)

    long_exp = Decimal("0")
    short_exp = Decimal("0")
    sector_map: Dict[str, dict] = {}
    weights_pct: List[float] = []

    for p in positions:
        mv = abs(Decimal(p.market_value))
        is_short = p.direction and p.direction.value == "SHORT"
        if is_short:
            short_exp += mv
            signed = -mv
        else:
            long_exp += mv
            signed = mv

        weights_pct.append(float(mv / total_nav * Decimal("100")))

        sector = asset_sectors.get(p.asset, "OTHER")
        bucket = sector_map.setdefault(sector, {
            "gross": Decimal("0"), "net": Decimal("0"),
            "count": 0, "assets": set(),
        })
        bucket["gross"] += mv
        bucket["net"] += signed
        bucket["count"] += 1
        bucket["assets"].add(p.asset)

    gross = long_exp + short_exp
    net = long_exp - short_exp
    leverage = gross / total_nav if total_nav > 0 else Decimal("0")
    ls_ratio = long_exp / short_exp if short_exp > 0 else None

    sectors = sorted([
        SectorExposure(
            sector=s,
            gross_value=v["gross"],
            net_value=v["net"],
            pct_of_nav=(
                v["gross"] / total_nav * Decimal("100")
                if total_nav > 0 else Decimal("0")
            ),
            position_count=v["count"],
            assets=sorted(v["assets"]),
        )
        for s, v in sector_map.items()
    ], key=lambda x: x.gross_value, reverse=True)

    hhi = sum(w * w for w in weights_pct)  # weights in %, HHI in 0..10000
    sorted_w = sorted(weights_pct, reverse=True)
    top_1 = Decimal(str(sorted_w[0])) if sorted_w else Decimal("0")
    top_3 = Decimal(str(sum(sorted_w[:3])))
    top_5 = Decimal(str(sum(sorted_w[:5])))
    eff_n = 10000.0 / hhi if hhi > 0 else 0.0

    return ExposureAnalysis(
        total_nav=total_nav,
        gross_exposure=gross,
        net_exposure=net,
        leverage_ratio=leverage,
        long_exposure=long_exp,
        short_exposure=short_exp,
        long_short_ratio=ls_ratio,
        sectors=sectors,
        concentration=ConcentrationMetrics(
            herfindahl_index=hhi,
            top_1_pct=top_1,
            top_3_pct=top_3,
            top_5_pct=top_5,
            effective_positions=eff_n,
        ),
    )
