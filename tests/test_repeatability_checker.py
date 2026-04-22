from pathlib import Path

from src.analysis.repeatability import RepeatabilityChecker
from src.common.config import Config


def _build_config(tmp_path: Path) -> Config:
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "repeatability:",
                "  warning:",
                "    total_return: 0.2",
                "    annual_return: 0.2",
                "    max_drawdown: 0.2",
                "    sharpe_ratio: 0.1",
                "    win_rate: 1.0",
                "  failed:",
                "    total_return: 0.5",
                "    annual_return: 0.5",
                "    max_drawdown: 0.5",
                "    sharpe_ratio: 0.2",
                "    win_rate: 2.0",
                "performance:",
                "  download_p95_seconds: 30",
                "  batch_download_p95_minutes: 30",
                "  single_backtest_p95_seconds: 5",
                "  batch_backtest_p95_minutes: 30",
            ]
        ),
        encoding="utf-8",
    )
    return Config(str(cfg_path))


def test_repeatability_status_pass_warning_failed(tmp_path: Path):
    checker = RepeatabilityChecker(_build_config(tmp_path))

    pass_report = checker.evaluate_metric_diff(
        {
            "total_return": {"a": 10.0, "b": 10.1, "delta_b_minus_a": 0.1},
            "annual_return": {"a": 8.0, "b": 8.1, "delta_b_minus_a": 0.1},
            "max_drawdown": {"a": 6.0, "b": 6.1, "delta_b_minus_a": 0.1},
            "sharpe_ratio": {"a": 1.2, "b": 1.25, "delta_b_minus_a": 0.05},
            "win_rate": {"a": 55.0, "b": 55.5, "delta_b_minus_a": 0.5},
        }
    )
    assert pass_report["status"] == "pass"

    warning_report = checker.evaluate_metric_diff(
        {
            "total_return": {"a": 10.0, "b": 10.3, "delta_b_minus_a": 0.3},
            "annual_return": {"a": 8.0, "b": 8.1, "delta_b_minus_a": 0.1},
            "max_drawdown": {"a": 6.0, "b": 6.1, "delta_b_minus_a": 0.1},
            "sharpe_ratio": {"a": 1.2, "b": 1.25, "delta_b_minus_a": 0.05},
            "win_rate": {"a": 55.0, "b": 55.5, "delta_b_minus_a": 0.5},
        }
    )
    assert warning_report["status"] == "warning"

    failed_report = checker.evaluate_metric_diff(
        {
            "total_return": {"a": 10.0, "b": 10.6, "delta_b_minus_a": 0.6},
            "annual_return": {"a": 8.0, "b": 8.1, "delta_b_minus_a": 0.1},
            "max_drawdown": {"a": 6.0, "b": 6.1, "delta_b_minus_a": 0.1},
            "sharpe_ratio": {"a": 1.2, "b": 1.25, "delta_b_minus_a": 0.05},
            "win_rate": {"a": 55.0, "b": 55.5, "delta_b_minus_a": 0.5},
        }
    )
    assert failed_report["status"] == "failed"


def test_repeatability_acceptance_template_structure(tmp_path: Path):
    checker = RepeatabilityChecker(_build_config(tmp_path))
    report = checker.evaluate_comparison(
        {
            "result_id_a": 1,
            "result_id_b": 2,
            "metric_diff": {
                "total_return": {"a": 10.0, "b": 10.2, "delta_b_minus_a": 0.2},
                "annual_return": {"a": 8.0, "b": 8.1, "delta_b_minus_a": 0.1},
                "max_drawdown": {"a": 6.0, "b": 6.1, "delta_b_minus_a": 0.1},
                "sharpe_ratio": {"a": 1.2, "b": 1.25, "delta_b_minus_a": 0.05},
                "win_rate": {"a": 55.0, "b": 55.5, "delta_b_minus_a": 0.5},
            },
            "source_diff": ["策略参数不同"],
        }
    )

    template = checker.build_acceptance_template(report)
    assert "consistency" in template
    assert "performance_evidence" in template
    assert template["consistency"]["result_id_a"] == 1
    assert template["consistency"]["result_id_b"] == 2
    assert "download_p95_seconds" in template["performance_evidence"]
    assert template["performance_evidence"]["single_backtest_p95_seconds"]["target"] == 5
