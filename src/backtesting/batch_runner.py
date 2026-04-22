"""
批量回测调度器

接收股票列表 + 策略工厂 + 参数 + 时间范围，为每只股票独立运行 BacktestEngine，
汇总结果并持久化到 backtest_results 表。单股票失败不中断整体流程。
"""
from __future__ import annotations

import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from ..common.database import DatabaseManager
from .backtest_engine import BacktestConfig, BacktestEngine
from .result import BacktestResult
from ..trading.strategy import Strategy


class BatchRunner:
    """批量回测调度器"""

    def __init__(self, db_path: str = "data/stock_data.db"):
        """
        Args:
            db_path: SQLite 数据库路径，用于持久化回测结果
        """
        self.db_path = db_path
        self._cancel_event = threading.Event()
        self._last_statuses: Dict[str, str] = {}
        self._last_errors: Dict[str, str] = {}
        self._last_run_args: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """取消正在运行的批量回测"""
        self._cancel_event.set()

    def get_last_run_status(self) -> Dict[str, Any]:
        """获取最近一次批量回测的每标的状态摘要。"""
        statuses = dict(self._last_statuses)
        return {
            "total": len(statuses),
            "statuses": statuses,
            "errors": dict(self._last_errors),
            "success": [c for c, s in statuses.items() if s == "success"],
            "failed": [c for c, s in statuses.items() if s == "failed"],
            "cancelled": [c for c, s in statuses.items() if s == "cancelled"],
            "pending": [c for c, s in statuses.items() if s == "pending"],
        }

    def resume(
        self,
        scope: str = "incomplete",
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        persist_results: Optional[bool] = None,
    ) -> List[BacktestResult]:
        """基于最近一次任务状态续跑。

        Args:
            scope: 续跑范围，支持 `incomplete`（未完成/取消）、`failed`（失败）、`all`（全量）
            on_progress: 可选进度回调，覆盖上次 run 的回调
            persist_results: 是否持久化，None 表示沿用上次 run 参数
        """
        if not self._last_run_args:
            raise ValueError("没有可续跑的历史任务")

        scope = scope.lower().strip()
        if scope not in {"incomplete", "failed", "all"}:
            raise ValueError("scope 仅支持 incomplete/failed/all")

        statuses = self._last_statuses
        if scope == "incomplete":
            ts_codes = [
                code for code, st in statuses.items()
                if st in {"pending", "cancelled"}
            ]
        elif scope == "failed":
            ts_codes = [code for code, st in statuses.items() if st == "failed"]
        else:
            ts_codes = list(self._last_run_args["ts_codes"])

        if not ts_codes:
            logger.info(f"续跑范围 {scope} 无待处理标的")
            return []

        logger.info(f"开始续跑，范围={scope}，标的数={len(ts_codes)}")

        return self.run(
            ts_codes=ts_codes,
            strategy_factory=self._last_run_args["strategy_factory"],
            start_date=self._last_run_args["start_date"],
            end_date=self._last_run_args["end_date"],
            initial_cash=self._last_run_args["initial_cash"],
            commission_rate=self._last_run_args["commission_rate"],
            slippage_rate=self._last_run_args["slippage_rate"],
            on_progress=on_progress,
            persist_results=self._last_run_args["persist_results"] if persist_results is None else persist_results,
        )

    def run(
        self,
        ts_codes: List[str],
        strategy_factory: Callable[[], Strategy],
        start_date: datetime,
        end_date: datetime,
        initial_cash: float = 100_000.0,
        commission_rate: float = 0.0003,
        slippage_rate: float = 0.001,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        persist_results: bool = True,
    ) -> List[BacktestResult]:
        """批量对多只股票运行单一策略的回测。

        Args:
            ts_codes: 股票代码列表（如 ["000001.SZ", "600000.SH"]）
            strategy_factory: 无参可调用对象，每次调用返回一个新鲜的策略实例
                              例：``lambda: DualMAStrategy(params={"short": 5, "long": 20})``
            start_date: 回测开始日期
            end_date: 回测结束日期
            initial_cash: 每只股票的初始资金
            commission_rate: 手续费率（默认 0.03%）
            slippage_rate: 滑点率（默认 0.1%）
            on_progress: 进度回调 (current_index, total, ts_code)
            persist_results: 是否将结果写入数据库

        Returns:
            成功完成回测的 BacktestResult 列表（失败的股票不计入）
        """
        self._cancel_event.clear()
        self._last_run_args = {
            "ts_codes": list(ts_codes),
            "strategy_factory": strategy_factory,
            "start_date": start_date,
            "end_date": end_date,
            "initial_cash": initial_cash,
            "commission_rate": commission_rate,
            "slippage_rate": slippage_rate,
            "persist_results": persist_results,
        }
        self._last_statuses = {code: "pending" for code in ts_codes}
        self._last_errors = {}

        total = len(ts_codes)
        results: List[BacktestResult] = []
        failures: List[Dict[str, str]] = []
        run_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy_snapshot: Dict[str, Any] = {}

        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission_rate=commission_rate,
            slippage_rate=slippage_rate,
        )

        for i, ts_code in enumerate(ts_codes):
            if self._cancel_event.is_set():
                logger.info("批量回测已取消")
                break

            self._last_statuses[ts_code] = "running"

            # 推送进度（开始当前股票前通知）
            if on_progress:
                try:
                    on_progress(i, total, ts_code)
                except Exception:
                    pass

            try:
                strategy = strategy_factory()
                if not strategy_snapshot:
                    strategy_snapshot = {
                        "strategy_id": getattr(strategy, "strategy_id", ""),
                        "strategy_name": getattr(strategy, "name", ""),
                        "strategy_params": deepcopy(getattr(strategy, "params", {}) or {}),
                    }
                engine = BacktestEngine(config)
                result = engine.run_backtest(strategy, [ts_code])
                results.append(result)
                self._last_statuses[ts_code] = "success"
                logger.info(
                    f"[{i + 1}/{total}] {ts_code} 回测完成 — "
                    f"总收益: {result.total_return:.2f}%  "
                    f"年化: {result.annual_return:.2f}%  "
                    f"最大回撤: {result.metrics.max_drawdown:.2f}%"
                )
            except Exception as exc:
                logger.error(f"[{i + 1}/{total}] {ts_code} 回测失败: {exc}")
                self._last_statuses[ts_code] = "failed"
                self._last_errors[ts_code] = str(exc)
                failures.append({"ts_code": ts_code, "error": str(exc)})

        if self._cancel_event.is_set():
            for code, status in self._last_statuses.items():
                if status in {"pending", "running"}:
                    self._last_statuses[code] = "cancelled"

        # 通知全部结束
        if on_progress and not self._cancel_event.is_set():
            try:
                on_progress(total, total, "")
            except Exception:
                pass

        logger.info(
            f"批量回测完成：成功 {len(results)}/{total}，失败 {len(failures)}"
        )

        # 持久化
        if persist_results and results:
            run_ended_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            experiment_snapshot = {
                "ts_codes_snapshot": list(ts_codes),
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "initial_cash": initial_cash,
                "cost_params": {
                    "commission_rate": commission_rate,
                    "slippage_rate": slippage_rate,
                },
                "data_scope": {
                    "market": "A-share",
                    "frequency": "daily",
                    "adjustment": "unspecified",
                },
                "strategy_snapshot": strategy_snapshot,
                "run_started_at": run_started_at,
                "run_ended_at": run_ended_at,
            }
            self._persist_results(results, commission_rate, slippage_rate, experiment_snapshot)

        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _persist_results(
        self,
        results: List[BacktestResult],
        commission_rate: float,
        slippage_rate: float,
        experiment_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将回测结果批量写入 backtest_results 表"""
        try:
            db = DatabaseManager(self.db_path)
        except Exception as exc:
            logger.error(f"连接数据库失败，无法持久化结果: {exc}")
            return

        config_json = {
            "commission_rate": commission_rate,
            "slippage_rate": slippage_rate,
        }
        if experiment_snapshot:
            config_json["experiment_snapshot"] = experiment_snapshot

        for result in results:
            symbol = result.symbols[0] if result.symbols else ""
            try:
                db.save_backtest_result(
                    strategy_name=result.strategy_name,
                    symbol=symbol,
                    start_date=result.start_date.strftime("%Y%m%d"),
                    end_date=result.end_date.strftime("%Y%m%d"),
                    initial_cash=result.initial_cash,
                    final_value=result.final_value,
                    metrics=result.metrics.to_dict(),
                    config_json=config_json,
                )
            except Exception as exc:
                logger.error(f"持久化 {symbol} 结果失败: {exc}")
