"""
结果聚合器

将多只股票的 BacktestResult 汇总为 DataFrame，提供排名、整体胜率统计
和 CSV 导出功能。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from loguru import logger

from ..backtesting.result import BacktestResult


class ResultAggregator:
    """批量回测结果聚合器"""

    # 汇总表的全部列（顺序固定，便于 GUI 展示）
    COLUMNS = [
        "code",
        "strategy",
        "start_date",
        "end_date",
        "initial_cash",
        "final_value",
        "total_return",
        "annual_return",
        "max_drawdown",
        "sharpe_ratio",
        "calmar_ratio",
        "volatility",
        "total_trades",
        "win_rate",
        "profit_loss_ratio",
    ]

    def __init__(self, results: List[BacktestResult]):
        """
        Args:
            results: BatchRunner.run() 返回的 BacktestResult 列表
        """
        self.results = results
        self._df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # 汇总 DataFrame 构建
    # ------------------------------------------------------------------

    def build_summary(self) -> pd.DataFrame:
        """将所有结果汇总为 DataFrame。

        Returns:
            每行对应一只股票回测结果的 DataFrame
        """
        rows = []
        for r in self.results:
            symbol = r.symbols[0] if r.symbols else ""
            m = r.metrics
            rows.append(
                {
                    "code": symbol,
                    "strategy": r.strategy_name,
                    "start_date": r.start_date.strftime("%Y-%m-%d"),
                    "end_date": r.end_date.strftime("%Y-%m-%d"),
                    "initial_cash": r.initial_cash,
                    "final_value": round(r.final_value, 2),
                    "total_return": round(r.total_return, 2),
                    "annual_return": round(r.annual_return, 2),
                    "max_drawdown": round(m.max_drawdown, 2),
                    "sharpe_ratio": round(m.sharpe_ratio, 4),
                    "calmar_ratio": round(m.calmar_ratio, 4),
                    "volatility": round(m.volatility, 2),
                    "total_trades": m.total_trades,
                    "win_rate": round(m.win_rate, 2),
                    "profit_loss_ratio": round(m.profit_loss_ratio, 4),
                }
            )
        self._df = pd.DataFrame(rows, columns=self.COLUMNS)
        return self._df

    @property
    def summary(self) -> pd.DataFrame:
        """懒惰构建并缓存汇总 DataFrame"""
        if self._df is None:
            self.build_summary()
        return self._df

    # ------------------------------------------------------------------
    # 统计功能
    # ------------------------------------------------------------------

    def overall_win_rate(self) -> float:
        """整体胜率：总收益 > 0 的股票数 / 股票总数（%）"""
        df = self.summary
        if df.empty:
            return 0.0
        positive = (df["total_return"] > 0).sum()
        return round(positive / len(df) * 100, 2)

    def top_n(self, n: int = 10, by: str = "sharpe_ratio") -> pd.DataFrame:
        """按指定列降序返回 Top N 股票。

        Args:
            n: 返回行数
            by: 排序依据列名（如 "sharpe_ratio"、"total_return"、"annual_return"）

        Returns:
            Top N 行 DataFrame
        """
        df = self.summary
        if df.empty or by not in df.columns:
            return df
        return df.sort_values(by=by, ascending=False).head(n).reset_index(drop=True)

    def bottom_n(self, n: int = 10, by: str = "total_return") -> pd.DataFrame:
        """按指定列升序返回 Bottom N（最差）股票"""
        df = self.summary
        if df.empty or by not in df.columns:
            return df
        return df.sort_values(by=by, ascending=True).head(n).reset_index(drop=True)

    def describe(self) -> pd.Series:
        """对主要指标列进行统计描述（均值/中位数/标准差等）"""
        stat_cols = [
            "total_return", "annual_return", "max_drawdown",
            "sharpe_ratio", "volatility", "win_rate",
        ]
        df = self.summary
        available = [c for c in stat_cols if c in df.columns]
        if df.empty or not available:
            return pd.DataFrame(index=["mean", "std", "min", "50%", "max"])
        return df[available].describe().loc[["mean", "std", "min", "50%", "max"]]

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def to_csv(self, path: str) -> str:
        """将汇总 DataFrame 导出为 UTF-8 BOM CSV（Excel 可直接打开）。

        Args:
            path: 输出文件路径

        Returns:
            实际写入的绝对路径字符串
        """
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.summary.to_csv(output, index=False, encoding="utf-8-sig")
        logger.info(f"回测汇总已导出: {output.resolve()}")
        return str(output.resolve())

    def trades_to_csv(self, path: str, ts_code: Optional[str] = None) -> str:
        """将单标的或全部交易记录导出为 UTF-8 BOM CSV。

        字段顺序固定为: ts_code, trade_date, direction, price, volume, amount, pnl

        Args:
            path: 输出文件路径
            ts_code: 过滤特定标的，None 表示导出全部

        Returns:
            实际写入的绝对路径字符串
        """
        TRADE_COLUMNS = ["ts_code", "trade_date", "direction", "price", "volume", "amount", "pnl"]
        rows = []
        for r in self.results:
            code = r.symbols[0] if r.symbols else ""
            if ts_code is not None and code != ts_code:
                continue
            for t in r.trades:
                row = {col: t.get(col, "") for col in TRADE_COLUMNS}
                row["ts_code"] = code
                # Normalize trade_date to string
                td = row.get("trade_date", "")
                if hasattr(td, "strftime"):
                    row["trade_date"] = td.strftime("%Y-%m-%d")
                # Round numeric fields to 4 decimal places
                for col in ("price", "amount", "pnl"):
                    try:
                        row[col] = round(float(row[col]), 4)
                    except (TypeError, ValueError):
                        pass
                rows.append(row)

        df = pd.DataFrame(rows, columns=TRADE_COLUMNS)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output, index=False, encoding="utf-8-sig")
        logger.info(f"交易记录已导出: {output.resolve()}")
        return str(output.resolve())
