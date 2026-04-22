"""
T8: 筛选展示规则 — 排序、Top N、空值处理、并列、多条件筛选

完成标准：
  - 空值、并列、多条件筛选行为可预期且可复现。
  - top_n / bottom_n 结果稳定；无效列名不崩溃。

运行方式: pytest tests/test_filter_rules.py -v
"""
import sys
import math
from pathlib import Path
from datetime import datetime
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.backtesting.result import BacktestResult
from src.analysis.aggregator import ResultAggregator


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _make_result(symbol: str, final_value: float, n_days: int = 252) -> BacktestResult:
    start, end = datetime(2023, 1, 1), datetime(2023, 12, 31)
    initial = 100_000.0
    step = (final_value - initial) / max(n_days - 1, 1)
    dp = [
        {'date': None, 'total_value': initial + step * i,
         'cash': initial + step * i, 'position_value': 0.0, 'positions': {}}
        for i in range(n_days)
    ]
    dp[-1]['total_value'] = final_value
    return BacktestResult(
        strategy_name='T8', symbols=[symbol],
        start_date=start, end_date=end,
        initial_cash=initial, final_value=final_value,
        trades=[], daily_portfolio=dp,
    )


def _agg(*pairs) -> ResultAggregator:
    """pairs = (symbol, final_value), ..."""
    return ResultAggregator([_make_result(s, v) for s, v in pairs])


# ════════════════════════════════════════════════════════════════════════════
# Top N 规则
# ════════════════════════════════════════════════════════════════════════════

class TestTopN:
    def test_top_n_returns_requested_count(self):
        agg = _agg(*[(f'{i:06d}', 100_000 + i * 2_000) for i in range(10)])
        assert len(agg.top_n(5)) == 5

    def test_top_n_descending_order(self):
        agg = _agg(('A', 130_000), ('B', 110_000), ('C', 120_000))
        df = agg.top_n(3, by='total_return')
        returns = df['total_return'].tolist()
        assert returns == sorted(returns, reverse=True)

    def test_top_n_n_exceeds_rows(self):
        """n > 行数时返回所有行，不崩溃"""
        agg = _agg(('A', 110_000), ('B', 120_000))
        df = agg.top_n(100)
        assert len(df) == 2

    def test_top_n_invalid_column_returns_df(self):
        """无效列名不崩溃，返回原始 DataFrame"""
        agg = _agg(('A', 110_000))
        df = agg.top_n(1, by='NONEXISTENT_COLUMN')
        assert isinstance(df, pd.DataFrame)

    def test_top_n_empty_aggregator(self):
        agg = ResultAggregator([])
        df = agg.top_n(5)
        assert df.empty

    def test_top_n_ties_stable(self):
        """并列时 top_n 返回行数正确（不多不少）"""
        # 3 只完全相同收益
        agg = _agg(('A', 110_000), ('B', 110_000), ('C', 110_000), ('D', 120_000))
        df = agg.top_n(2, by='total_return')
        assert len(df) == 2


# ════════════════════════════════════════════════════════════════════════════
# Bottom N 规则
# ════════════════════════════════════════════════════════════════════════════

class TestBottomN:
    def test_bottom_n_ascending_order(self):
        agg = _agg(('A', 80_000), ('B', 130_000), ('C', 70_000))
        df = agg.bottom_n(3, by='total_return')
        returns = df['total_return'].tolist()
        assert returns == sorted(returns)

    def test_bottom_n_returns_correct_count(self):
        agg = _agg(*[(f'{i:06d}', 90_000 + i * 1_000) for i in range(8)])
        assert len(agg.bottom_n(3)) == 3

    def test_bottom_n_n_larger_than_data(self):
        agg = _agg(('X', 95_000))
        df = agg.bottom_n(50)
        assert len(df) == 1


# ════════════════════════════════════════════════════════════════════════════
# 多条件筛选（手动 filter）
# ════════════════════════════════════════════════════════════════════════════

class TestMultiConditionFilter:
    """模拟按 total_return > threshold AND win_rate == 0 的复合筛选。"""

    def test_filter_positive_return(self):
        agg = _agg(('GAIN', 115_000), ('LOSS', 85_000), ('EVEN', 100_000))
        df = agg.summary
        filtered = df[df['total_return'] > 0]
        assert len(filtered) == 1
        assert filtered.iloc[0]['code'] == 'GAIN'

    def test_filter_by_strategy(self):
        """不同策略的同标的可按 strategy 列筛选"""
        r1 = _make_result('000001', 110_000)
        r1.strategy_name = 'StratA'
        r2 = _make_result('000001', 120_000)
        r2.strategy_name = 'StratB'
        agg = ResultAggregator([r1, r2])
        df = agg.summary
        strat_a = df[df['strategy'] == 'StratA']
        assert len(strat_a) == 1
        assert round(strat_a.iloc[0]['total_return'], 1) == 10.0

    def test_combined_filter_return_and_sharpe(self):
        agg = _agg(
            ('GOOD',  140_000),   # high return → high Sharpe
            ('OK',    108_000),   # moderate
            ('BAD',    80_000),   # negative
        )
        df = agg.summary
        positive_and_decent = df[
            (df['total_return'] > 0) & (df['sharpe_ratio'] > 0)
        ]
        codes = positive_and_decent['code'].tolist()
        assert 'BAD' not in codes


# ════════════════════════════════════════════════════════════════════════════
# describe() — 分布视图
# ════════════════════════════════════════════════════════════════════════════

class TestDescribeDistribution:
    def test_describe_returns_series(self):
        agg = _agg(('A', 110_000), ('B', 90_000), ('C', 120_000))
        desc = agg.describe()
        assert isinstance(desc, pd.DataFrame)

    def test_describe_has_expected_stats(self):
        agg = _agg(*[(f'{i:06d}', 100_000 + i * 5_000) for i in range(5)])
        desc = agg.describe()
        for stat in ('mean', 'std', 'min', 'max'):
            assert stat in desc.index

    def test_describe_empty(self):
        agg = ResultAggregator([])
        desc = agg.describe()
        assert isinstance(desc, pd.DataFrame)
