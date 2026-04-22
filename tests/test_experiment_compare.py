import json
from pathlib import Path

from src.common.database import DatabaseManager


def _save_result(db: DatabaseManager, symbol: str, total_return: float, short_window: int) -> int:
    config_json = {
        "commission_rate": 0.0003,
        "slippage_rate": 0.001,
        "experiment_snapshot": {
            "ts_codes_snapshot": [symbol],
            "start_date": "20230101",
            "end_date": "20231231",
            "initial_cash": 100000,
            "cost_params": {
                "commission_rate": 0.0003,
                "slippage_rate": 0.001,
            },
            "data_scope": {
                "market": "A-share",
                "frequency": "daily",
                "adjustment": "unspecified",
            },
            "strategy_snapshot": {
                "strategy_id": "dual_ma",
                "strategy_name": "DualMA",
                "strategy_params": {
                    "short": short_window,
                    "long": 20,
                },
            },
            "run_started_at": "2026-04-21 10:00:00",
            "run_ended_at": "2026-04-21 10:01:00",
        },
    }

    return db.save_backtest_result(
        strategy_name="DualMA",
        symbol=symbol,
        start_date="20230101",
        end_date="20231231",
        initial_cash=100000,
        final_value=100000 * (1 + total_return / 100),
        metrics={
            "total_return": total_return,
            "annual_return": 8.0,
            "max_drawdown": 6.0,
            "sharpe_ratio": 1.2,
            "total_trades": 12,
            "win_rate": 55.0,
        },
        config_json=config_json,
    )


def test_search_backtest_results_by_name_and_time(tmp_path: Path):
    db = DatabaseManager(str(tmp_path / "exp.db"))
    _save_result(db, "000001.SZ", 10.0, 5)
    _save_result(db, "000002.SZ", 12.0, 8)

    all_rows = db.search_backtest_results(strategy_name_keyword="Dual")
    assert len(all_rows) >= 2

    no_rows = db.search_backtest_results(
        strategy_name_keyword="Dual",
        created_start="2099-01-01 00:00:00",
        created_end="2099-12-31 23:59:59",
    )
    assert no_rows == []


def test_compare_backtest_results_returns_metric_and_source_diff(tmp_path: Path):
    db = DatabaseManager(str(tmp_path / "compare.db"))
    id_a = _save_result(db, "000001.SZ", 10.0, 5)
    id_b = _save_result(db, "000001.SZ", 14.0, 10)

    diff = db.compare_backtest_results(id_a, id_b)

    assert diff["result_id_a"] == id_a
    assert diff["result_id_b"] == id_b
    assert diff["metric_diff"]["total_return"]["delta_b_minus_a"] == 4.0
    assert "策略参数不同" in diff["source_diff"]
