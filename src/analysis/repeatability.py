"""
一致性检查器

用于比较两次实验关键指标差异，给出 pass/warning/failed 判定，
并生成固定结构的验收证据模板。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..common.config import Config


class RepeatabilityChecker:
    """实验一致性检查器。"""

    DEFAULT_WARNING_THRESHOLDS = {
        "total_return": 0.2,
        "annual_return": 0.2,
        "max_drawdown": 0.2,
        "sharpe_ratio": 0.1,
        "win_rate": 1.0,
    }

    DEFAULT_FAILED_THRESHOLDS = {
        "total_return": 0.5,
        "annual_return": 0.5,
        "max_drawdown": 0.5,
        "sharpe_ratio": 0.2,
        "win_rate": 2.0,
    }

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.warning_thresholds = self._load_thresholds("repeatability.warning", self.DEFAULT_WARNING_THRESHOLDS)
        self.failed_thresholds = self._load_thresholds("repeatability.failed", self.DEFAULT_FAILED_THRESHOLDS)

    def _load_thresholds(self, prefix: str, defaults: Dict[str, float]) -> Dict[str, float]:
        values: Dict[str, float] = {}
        for key, default in defaults.items():
            values[key] = float(self.config.get(f"{prefix}.{key}", default))
        return values

    def evaluate_metric_diff(
        self,
        metric_diff: Dict[str, Dict[str, Any]],
        result_id_a: Optional[int] = None,
        result_id_b: Optional[int] = None,
    ) -> Dict[str, Any]:
        """根据指标差异进行一致性判定。"""
        checks: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []
        failures: List[str] = []

        for metric, warning_th in self.warning_thresholds.items():
            failed_th = self.failed_thresholds.get(metric, warning_th)
            item = metric_diff.get(metric, {})
            delta = item.get("delta_b_minus_a")

            if delta is None:
                abs_delta = None
                level = "unknown"
            else:
                abs_delta = abs(float(delta))
                if abs_delta > failed_th:
                    level = "failed"
                    failures.append(f"{metric} 偏差 {abs_delta:.6f} 超过失败阈值 {failed_th}")
                elif abs_delta > warning_th:
                    level = "warning"
                    warnings.append(f"{metric} 偏差 {abs_delta:.6f} 超过警告阈值 {warning_th}")
                else:
                    level = "pass"

            checks[metric] = {
                "a": item.get("a"),
                "b": item.get("b"),
                "delta_b_minus_a": delta,
                "abs_delta": abs_delta,
                "warning_threshold": warning_th,
                "failed_threshold": failed_th,
                "level": level,
            }

        if failures:
            status = "failed"
            summary = "一致性检查失败"
        elif warnings:
            status = "warning"
            summary = "一致性检查存在警告"
        else:
            status = "pass"
            summary = "一致性检查通过"

        return {
            "status": status,
            "summary": summary,
            "result_id_a": result_id_a,
            "result_id_b": result_id_b,
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
            "thresholds": {
                "warning": self.warning_thresholds,
                "failed": self.failed_thresholds,
            },
        }

    def evaluate_comparison(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        """对 DatabaseManager.compare_backtest_results 输出执行一致性判定。"""
        report = self.evaluate_metric_diff(
            metric_diff=comparison.get("metric_diff", {}),
            result_id_a=comparison.get("result_id_a"),
            result_id_b=comparison.get("result_id_b"),
        )
        report["source_diff"] = comparison.get("source_diff", [])
        return report

    def build_acceptance_template(self, consistency_report: Dict[str, Any]) -> Dict[str, Any]:
        """生成固定结构的 T12 验收证据模板。"""
        return {
            "consistency": {
                "status": consistency_report.get("status", "failed"),
                "summary": consistency_report.get("summary", ""),
                "result_id_a": consistency_report.get("result_id_a"),
                "result_id_b": consistency_report.get("result_id_b"),
                "warnings": consistency_report.get("warnings", []),
                "failures": consistency_report.get("failures", []),
            },
            "performance_evidence": {
                "download_p95_seconds": {
                    "target": self.config.get("performance.download_p95_seconds", 30),
                    "actual": None,
                    "status": "pending",
                },
                "batch_download_p95_minutes": {
                    "target": self.config.get("performance.batch_download_p95_minutes", 30),
                    "actual": None,
                    "status": "pending",
                },
                "single_backtest_p95_seconds": {
                    "target": self.config.get("performance.single_backtest_p95_seconds", 5),
                    "actual": None,
                    "status": "pending",
                },
                "batch_backtest_p95_minutes": {
                    "target": self.config.get("performance.batch_backtest_p95_minutes", 30),
                    "actual": None,
                    "status": "pending",
                },
            },
        }
