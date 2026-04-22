from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.common.config import Config
from src.data.data_fetcher import DataFetcher
from src.data.data_storage import DataStorage
from src.data.data_processor import DataProcessor
from src.backtesting.backtest_engine import BacktestConfig, BacktestEngine
from src.trading.strategy import Strategy
from src.trading.bar_data import BarData


class NoSignalStrategy(Strategy):
    def on_init(self) -> None:
        pass

    def on_bar(self, bar: BarData) -> None:
        pass


def _make_raw_df(ts_code: str, rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["ts_code"] = ts_code
    return df


def test_data_quality_status_from_fixed_thresholds():
    # pass data
    pass_df = _make_raw_df(
        "000001.SZ",
        [
            {"trade_date": "20240102", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 1000},
            {"trade_date": "20240103", "open": 10.6, "high": 11.2, "low": 10.2, "close": 11.0, "volume": 1200},
        ],
    )
    pass_report = DataProcessor.evaluate_quality(pass_df)
    assert pass_report["status"] == "pass"

    # warning data: one duplicate row in 40 rows => 2.5%
    base_rows = [
        {"trade_date": f"202401{day:02d}", "open": 10 + day * 0.01, "high": 11 + day * 0.01, "low": 9 + day * 0.01, "close": 10.5 + day * 0.01, "volume": 1000}
        for day in range(1, 41)
    ]
    warning_df = _make_raw_df("000002.SZ", base_rows + [base_rows[0]])
    warning_report = DataProcessor.evaluate_quality(warning_df)
    assert warning_report["status"] in {"warning", "failed"}


def test_quality_report_json_written_per_symbol(tmp_path: Path):
    db_path = tmp_path / "quality.db"
    cfg_path = tmp_path / "config.yaml"

    cfg_path.write_text(
        "\n".join(
            [
                "database:",
                f"  path: \"{db_path.as_posix()}\"",
                "quality:",
                f"  report_dir: \"{(tmp_path / 'quality_reports').as_posix()}\"",
            ]
        ),
        encoding="utf-8",
    )

    storage = DataStorage(str(db_path))
    df = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open": [10.0, 10.2],
            "high": [10.4, 10.6],
            "low": [9.8, 10.0],
            "close": [10.1, 10.5],
            "volume": [1000, 1200],
            "amount": [10100, 12600],
        }
    )
    storage.save_stock_daily(df)

    fetcher = DataFetcher(Config(str(cfg_path)))
    report = fetcher.assess_stock_quality("000001.SZ", force=True)

    assert report["symbol"] == "000001.SZ"
    report_path = tmp_path / "quality_reports" / "000001.SZ.json"
    assert report_path.exists()

    parsed = json.loads(report_path.read_text(encoding="utf-8"))
    assert parsed["symbol"] == "000001.SZ"
    assert parsed["status"] in {"pass", "warning", "failed"}


def test_backtest_auto_assess_and_block_failed_quality(tmp_path: Path):
    db_path = tmp_path / "bt.db"
    cfg_path = tmp_path / "config.yaml"

    cfg_path.write_text(
        "\n".join(
            [
                "database:",
                f"  path: \"{db_path.as_posix()}\"",
                "quality:",
                f"  report_dir: \"{(tmp_path / 'quality_reports').as_posix()}\"",
                "  gate_warning_allow: true",
                "  missing_ratio_warning: 0.05",
                "  missing_ratio_failed: 0.20",
            ]
        ),
        encoding="utf-8",
    )

    storage = DataStorage(str(db_path))
    # sparse data in a long window to trigger high missing ratio
    storage.save_stock_daily(
        pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20240102",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.5,
                    "close": 10.1,
                    "volume": 1000,
                    "amount": 10100,
                },
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20240220",
                    "open": 10.2,
                    "high": 10.6,
                    "low": 9.8,
                    "close": 10.4,
                    "volume": 1200,
                    "amount": 12480,
                },
            ]
        )
    )

    bt_cfg = BacktestConfig(
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 2, 20),
        initial_cash=100000,
    )
    engine = BacktestEngine(bt_cfg, app_config=Config(str(cfg_path)))
    strategy = NoSignalStrategy("noop", "noop")

    with pytest.raises(ValueError):
        engine.run_backtest(strategy, ["000001.SZ"])
