"""Validated, versioned official NSE Indices factsheet weights."""

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse


DATA_DIRECTORY = Path(__file__).resolve().parent / "data" / "nse_weights"
OFFICIAL_HOSTS = {"niftyindices.com", "www.niftyindices.com"}


@dataclass(frozen=True)
class OfficialConstituent:
    ticker: str
    name: str
    weight: float


@dataclass(frozen=True)
class OfficialIndexWeights:
    sector_id: str
    official_index_name: str
    source_as_of: str
    constituent_count: int
    constituents: tuple[OfficialConstituent, ...]
    factsheet_url: str
    constituent_url: str

    @property
    def weight_coverage_pct(self):
        return round(sum(item.weight for item in self.constituents), 2)

    @property
    def is_complete(self):
        return len(self.constituents) == self.constituent_count

    def provenance(self):
        status = "OFFICIAL_COMPLETE" if self.is_complete else "OFFICIAL_PARTIAL"
        return {
            "status": status,
            "label": "Official NSE factsheet weights" if self.is_complete else "Official NSE factsheet top-10 weights",
            "publisher": "NSE Indices Limited",
            "source_as_of": self.source_as_of,
            "weight_coverage_pct": self.weight_coverage_pct,
            "published_constituents": len(self.constituents),
            "index_constituents": self.constituent_count,
            "is_complete": self.is_complete,
            "factsheet_url": self.factsheet_url,
            "constituent_url": self.constituent_url,
        }


@dataclass(frozen=True)
class OfficialWeightSet:
    dataset_version: str
    source_as_of: str
    indices: dict[str, OfficialIndexWeights]

    def summary(self):
        return {
            "dataset_version": self.dataset_version,
            "source_as_of": self.source_as_of,
            "publisher": "NSE Indices Limited",
            "complete_indices": sum(index.is_complete for index in self.indices.values()),
            "partial_indices": sum(not index.is_complete for index in self.indices.values()),
        }


def validate_weight_document(document):
    if document.get("schema_version") != 1:
        raise ValueError("Official weight data must use schema_version 1")
    source_as_of = document.get("source_as_of")
    try:
        parsed_date = date.fromisoformat(source_as_of)
    except (TypeError, ValueError) as error:
        raise ValueError("source_as_of must be an ISO date") from error
    if parsed_date.isoformat() != document.get("dataset_version"):
        raise ValueError("dataset_version must equal source_as_of")
    if document.get("publisher") != "NSE Indices Limited":
        raise ValueError("publisher must be NSE Indices Limited")
    indices = document.get("indices")
    if not isinstance(indices, dict) or not indices:
        raise ValueError("indices must be a non-empty object")
    for sector_id, index in indices.items():
        count = index.get("constituent_count")
        constituents = index.get("constituents")
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"{sector_id}: constituent_count must be positive")
        if not isinstance(constituents, list) or not constituents or len(constituents) > count:
            raise ValueError(f"{sector_id}: invalid published constituent coverage")
        for url_key in ("factsheet_url", "constituent_url"):
            url = index.get(url_key, "")
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
                raise ValueError(f"{sector_id}: {url_key} must be an official HTTPS Nifty Indices URL")
        tickers = set()
        weight_total = 0.0
        for item in constituents:
            ticker = item.get("ticker")
            name = item.get("name")
            weight = item.get("weight")
            if not isinstance(ticker, str) or not ticker or ticker in tickers:
                raise ValueError(f"{sector_id}: duplicate or invalid ticker")
            if not isinstance(name, str) or not name:
                raise ValueError(f"{sector_id}: constituent name is required")
            if not isinstance(weight, (int, float)) or not 0 < float(weight) <= 100:
                raise ValueError(f"{sector_id}: weight must be in (0, 100]")
            tickers.add(ticker)
            weight_total += float(weight)
        if weight_total > 100.1:
            raise ValueError(f"{sector_id}: published weights exceed 100%")
        if len(constituents) == count and not 99.8 <= weight_total <= 100.2:
            raise ValueError(f"{sector_id}: complete published coverage must total approximately 100%")
    return document


def load_weight_document(path):
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Could not load official NSE weight data from {path}") from error
    return validate_weight_document(document)


def latest_weight_file(data_directory=DATA_DIRECTORY):
    candidates = sorted(Path(data_directory).glob("????-??-??.json"))
    if not candidates:
        raise RuntimeError("No versioned official NSE weight dataset is installed")
    return candidates[-1]


def load_latest_weight_set(data_directory=DATA_DIRECTORY):
    document = load_weight_document(latest_weight_file(data_directory))
    indices = {}
    for sector_id, index in document["indices"].items():
        constituents = tuple(OfficialConstituent(item["ticker"], item["name"], float(item["weight"])) for item in index["constituents"])
        indices[sector_id] = OfficialIndexWeights(
            sector_id=sector_id,
            official_index_name=index["official_index_name"],
            source_as_of=document["source_as_of"],
            constituent_count=index["constituent_count"],
            constituents=constituents,
            factsheet_url=index["factsheet_url"],
            constituent_url=index["constituent_url"],
        )
    return OfficialWeightSet(document["dataset_version"], document["source_as_of"], indices)


OFFICIAL_WEIGHT_SET = load_latest_weight_set()
