"""
批量回测调度器

接收股票列表 + 策略工厂 + 参数 + 时间范围，为每只股票独立运行 BacktestEngine，
汇总结果并持久化到 backtest_results 表。单股票失败不中断整体流程。
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Type

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

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """取消正在运行的批量回测"""
        self._cancel_event.set()

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

        total = len(ts_codes)
        results: List[BacktestResult] = []
        failures: List[Dict[str, str]] = []

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

            # 推送进度（开始当前股票前通知）
            if on_progress:
                try:
                    on_progress(i, total, ts_code)
                except Exception:
                    pass

            try:
                strategy = strategy_factory()
                engine = BacktestEngine(config)
                result = engine.run_backtest(strategy, [ts_code])
                results.append(result)
                logger.info(
                    f"[{i + 1}/{total}] {ts_code} 回测完成 — "
                    f"总收益: {result.total_return:.2f}%  "
                    f"年化: {result.annual_return:.2f}%  "
                    f"最大回撤: {result.metrics.max_drawdown:.2f}%"
                )
            except Exception as exc:
                logger.error(f"[{i + 1}/{total}] {ts_code} 回测失败: {exc}")
                failures.append({"ts_code": ts_code, "error": str(exc)})

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
            self._persist_results(results, commission_rate, slippage_rate)

        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _persist_results(
        self,
        results: List[BacktestResult],
        commission_rate: float,
        slippage_rate: float,
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
