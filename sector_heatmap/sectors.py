"""FYERS symbols joined to versioned official NSE Indices constituent weights."""

from dataclasses import dataclass
from typing import Optional

from .official_weights import OFFICIAL_WEIGHT_SET, OfficialConstituent, OfficialIndexWeights


BENCHMARK_SYMBOL = "NSE:NIFTY50-INDEX"


@dataclass(frozen=True)
class SectorDefinition:
    sector_id: str
    name: str
    symbol: str
    official_weights: Optional[OfficialIndexWeights] = None

    @property
    def constituents(self) -> tuple[OfficialConstituent, ...]:
        return self.official_weights.constituents if self.official_weights else ()

    @property
    def attribution(self):
        if self.official_weights:
            return self.official_weights.provenance()
        return {
            "status": "UNAVAILABLE",
            "label": "No authoritative constituent weights",
            "publisher": None,
            "source_as_of": None,
            "weight_coverage_pct": 0.0,
            "published_constituents": 0,
            "index_constituents": None,
            "is_complete": False,
            "factsheet_url": None,
            "constituent_url": None,
        }


def _sector(sector_id, name, symbol):
    return SectorDefinition(sector_id, name, symbol, OFFICIAL_WEIGHT_SET.indices.get(sector_id))


SECTOR_DEFINITIONS = (
    _sector("bank", "Bank", "NSE:NIFTYBANK-INDEX"),
    _sector("financial-services", "Financial Services", "NSE:FINNIFTY-INDEX"),
    _sector("it", "IT", "NSE:NIFTYIT-INDEX"),
    _sector("auto", "Auto", "NSE:NIFTYAUTO-INDEX"),
    _sector("pharma", "Pharma", "NSE:NIFTYPHARMA-INDEX"),
    _sector("healthcare", "Healthcare", "NSE:NIFTYHEALTHCARE-INDEX"),
    _sector("fmcg", "FMCG", "NSE:NIFTYFMCG-INDEX"),
    _sector("metal", "Metal", "NSE:NIFTYMETAL-INDEX"),
    _sector("realty", "Realty", "NSE:NIFTYREALTY-INDEX"),
    _sector("energy", "Energy", "NSE:NIFTYENERGY-INDEX"),
    _sector("oil-gas", "Oil & Gas", "NSE:NIFTYOILANDGAS-INDEX"),
    _sector("psu-bank", "PSU Bank", "NSE:NIFTYPSUBANK-INDEX"),
    _sector("consumer-durables", "Consumer Durables", "NSE:NIFTYCONSRDURBL-INDEX"),
    _sector("media", "Media", "NSE:NIFTYMEDIA-INDEX"),
)

SECTOR_BY_ID = {sector.sector_id: sector for sector in SECTOR_DEFINITIONS}

# Backward-compatible views used by the live WebSocket snapshot.
SECTORS = [(sector.name, sector.symbol, 1.0) for sector in SECTOR_DEFINITIONS]
SECTOR_STOCKS = {sector.name: [(item.ticker, item.weight) for item in sector.constituents] for sector in SECTOR_DEFINITIONS}


def equity_symbol(ticker):
    return f"NSE:{ticker}-EQ"
