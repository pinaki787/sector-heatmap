from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.refresh_official_weights import install_candidate
from sector_heatmap.market_data import FyersLiveFeed
from sector_heatmap.official_weights import OFFICIAL_WEIGHT_SET, load_weight_document, validate_weight_document
from sector_heatmap.sectors import SECTOR_DEFINITIONS, SectorDefinition, equity_symbol


class OfficialWeightDataTests(unittest.TestCase):
    def test_every_supported_sector_uses_versioned_official_data(self):
        self.assertEqual({sector.sector_id for sector in SECTOR_DEFINITIONS}, set(OFFICIAL_WEIGHT_SET.indices))
        self.assertEqual(OFFICIAL_WEIGHT_SET.source_as_of, "2026-07-31")
        self.assertEqual(OFFICIAL_WEIGHT_SET.summary()["complete_indices"], 3)
        self.assertEqual(OFFICIAL_WEIGHT_SET.summary()["partial_indices"], 11)

    def test_complete_and_partial_coverage_are_not_conflated(self):
        self.assertTrue(OFFICIAL_WEIGHT_SET.indices["it"].is_complete)
        self.assertAlmostEqual(OFFICIAL_WEIGHT_SET.indices["it"].weight_coverage_pct, 100.01)
        bank = OFFICIAL_WEIGHT_SET.indices["bank"]
        self.assertFalse(bank.is_complete)
        self.assertEqual(bank.provenance()["status"], "OFFICIAL_PARTIAL")
        self.assertAlmostEqual(bank.weight_coverage_pct, 87.03)

    def test_known_official_weight_is_loaded_exactly_as_published(self):
        hdfc = OFFICIAL_WEIGHT_SET.indices["bank"].constituents[0]
        self.assertEqual((hdfc.ticker, hdfc.weight), ("HDFCBANK", 18.20))
        fmcg_tickers = {item.ticker for item in OFFICIAL_WEIGHT_SET.indices["fmcg"].constituents}
        self.assertIn("UNITDSPR", fmcg_tickers)
        self.assertNotIn("MCDOWELL-N", fmcg_tickers)

    def test_sector_without_authoritative_weights_is_explicitly_unavailable(self):
        unsupported = SectorDefinition("unsupported", "Unsupported", "NSE:UNSUPPORTED-INDEX")
        self.assertEqual(unsupported.constituents, ())
        self.assertEqual(unsupported.attribution["status"], "UNAVAILABLE")
        self.assertFalse(unsupported.attribution["is_complete"])

    def test_validator_rejects_non_official_provenance(self):
        source = Path(__file__).parents[1] / "sector_heatmap" / "data" / "nse_weights" / "2026-07-31.json"
        document = deepcopy(load_weight_document(source))
        document["indices"]["bank"]["factsheet_url"] = "https://example.com/proxy.pdf"
        with self.assertRaisesRegex(ValueError, "official HTTPS"):
            validate_weight_document(document)

    def test_refresh_is_versioned_atomic_and_refuses_overwrite(self):
        source = Path(__file__).parents[1] / "sector_heatmap" / "data" / "nse_weights" / "2026-07-31.json"
        document = deepcopy(load_weight_document(source))
        document["dataset_version"] = document["source_as_of"] = "2026-08-31"
        with TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            candidate = destination / "candidate.json"
            candidate.write_text(json.dumps(document), encoding="utf-8")
            expected = destination.resolve() / "2026-08-31.json"
            self.assertEqual(install_candidate(candidate, destination, check_only=True), expected)
            self.assertFalse(expected.exists())
            self.assertEqual(install_candidate(candidate, destination), expected)
            self.assertTrue(expected.exists())
            with self.assertRaises(ValueError):
                install_candidate(candidate, destination)


class OfficialAttributionTests(unittest.TestCase):
    def test_snapshot_uses_unrounded_move_and_preserves_provider_timestamp(self):
        feed = FyersLiveFeed("unused")
        feed.connected = True
        raw_timestamp = 1_785_000_123
        feed.ticks = {
            "NSE:NIFTYBANK-INDEX": {"ltp": 50_100.25, "prev_close_price": 50_000, "exch_feed_time": raw_timestamp - 1},
            equity_symbol("HDFCBANK"): {"ltp": 101.234567, "prev_close_price": 100.0, "last_traded_time": raw_timestamp},
        }
        snapshot = feed.snapshot()
        bank = next(row for row in snapshot["sectors"] if row["sector_id"] == "bank")
        hdfc = next(row for row in bank["drivers"] if row["ticker"] == "HDFCBANK")
        expected_change = (101.234567 - 100.0) / 100.0 * 100
        self.assertAlmostEqual(hdfc["change"], expected_change, places=10)
        self.assertAlmostEqual(hdfc["contribution"], 18.20 * expected_change / 100, places=10)
        self.assertEqual(hdfc["provider_tick_timestamp"], raw_timestamp)
        self.assertIsNotNone(hdfc["provider_tick_timestamp_iso"])
        self.assertEqual(bank["top_contributors"][0]["ticker"], "HDFCBANK")
        self.assertEqual(bank["attribution"]["status"], "OFFICIAL_PARTIAL")
        self.assertEqual(snapshot["weight_source"]["source_as_of"], "2026-07-31")
        self.assertIsNotNone(snapshot["updated_at"])
        self.assertIsNotNone(snapshot["snapshot_at"])

    def test_missing_live_tick_does_not_fabricate_contribution(self):
        feed = FyersLiveFeed("unused")
        bank = next(row for row in feed.snapshot()["sectors"] if row["sector_id"] == "bank")
        self.assertEqual(bank["top_contributors"], [])
        self.assertTrue(all(item["change"] is None and item["contribution"] is None for item in bank["drivers"]))
        self.assertEqual(bank["attribution"]["available_weight_pct"], 0)


if __name__ == "__main__":
    unittest.main()
