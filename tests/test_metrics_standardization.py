"""
T7: 指标字段标准化 — 验证单标的视图与汇总视图的字段名、定义、精度一致

完成标准：
  1. BacktestResult.metrics 字段名与 ResultAggregator.COLUMNS 中对应列一致。
  2. 两个视图中同一指标的数值口径相同（汇总表的值来自 result.metrics）。
  3. 数值单位统一（收益率、胜率均为百分比形式）。

运行方式: pytest tests/test_metrics_standardization.py -v
"""
import sys
from pathlib import Path
from datetime import datetime
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.result import BacktestResult, PerformanceMetrics
from src.analysis.aggregator import ResultAggregator


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _make_result(symbol: str = '000001', final_value: float = 110_000.0,
                 n_days: int = 252) -> BacktestResult:
    start = datetime(2023, 1, 1)
    end   = datetime(2023, 12, 31)
    initial_cash = 100_000.0
    step = (final_value - initial_cash) / max(n_days - 1, 1)
    dp = [
        {'date': None, 'total_value': initial_cash + step * i,
         'cash': initial_cash + step * i, 'position_value': 0.0, 'positions': {}}
        for i in range(n_days)
    ]
    dp[-1]['total_value'] = final_value
    return BacktestResult(
        strategy_name='T7Strategy',
        symbols=[symbol],
        start_date=start, end_date=end,
        initial_cash=initial_cash, final_value=final_value,
        trades=[], daily_portfolio=dp,
    )


# ════════════════════════════════════════════════════════════════════════════
# 字段名对齐
# ════════════════════════════════════════════════════════════════════════════

class TestFieldAlignment:
    """汇总表列名 ↔ PerformanceMetrics / BacktestResult 属性名对齐"""

    # 汇总表中来自 PerformanceMetrics 的列
    METRICS_COLS = {
        "max_drawdown", "sharpe_ratio", "calmar_ratio", "volatility",
        "total_trades", "win_rate", "profit_loss_ratio",
    }

    def test_aggregator_columns_cover_metrics_fields(self):
        """ResultAggregator.COLUMNS 必须覆盖 METRICS_COLS 中的所有字段"""
        for col in self.METRICS_COLS:
            assert col in ResultAggregator.COLUMNS, f"COLUMNS 缺少 {col}"

    def test_performance_metrics_has_all_metrics_cols(self):
        """PerformanceMetrics 必须拥有 METRICS_COLS 中的所有属性"""
        m = PerformanceMetrics()
        for col in self.METRICS_COLS:
            assert hasattr(m, col), f"PerformanceMetrics 缺少属性 {col}"

    def test_result_level_fields_in_columns(self):
        """BacktestResult 级别的字段（total_return, annual_return 等）也在 COLUMNS"""
        for col in ("total_return", "annual_return", "initial_cash", "final_value",
                    "code", "strategy", "start_date", "end_date"):
            assert col in ResultAggregator.COLUMNS, f"COLUMNS 缺少 {col}"


# ════════════════════════════════════════════════════════════════════════════
# 数值口径一致
# ════════════════════════════════════════════════════════════════════════════

class TestValueConsistency:
    """汇总表中同一指标的数值应来源于 BacktestResult，不应被二次处理导致口径偏差"""

    def test_total_return_matches(self):
        r = _make_result(final_value=115_000.0)
        agg = ResultAggregator([r])
        df = agg.build_summary()
        expected = round(r.total_return, 2)
        actual = df.iloc[0]['total_return']
        assert abs(actual - expected) < 0.01, \
            f"total_return 口径不一致: summary={actual}, result={expected}"

    def test_annual_return_matches(self):
        r = _make_result(final_value=120_000.0)
        agg = ResultAggregator([r])
        df = agg.build_summary()
        expected = round(r.annual_return, 2)
        actual = df.iloc[0]['annual_return']
        assert abs(actual - expected) < 0.01

    def test_max_drawdown_matches(self):
        r = _make_result(final_value=90_000.0)
        agg = ResultAggregator([r])
        df = agg.build_summary()
        expected = round(r.metrics.max_drawdown, 2)
        actual = df.iloc[0]['max_drawdown']
        assert abs(actual - expected) < 0.01

    def test_sharpe_ratio_matches(self):
        r = _make_result(final_value=130_000.0)
        agg = ResultAggregator([r])
        df = agg.build_summary()
        expected = round(r.metrics.sharpe_ratio, 4)
        actual = df.iloc[0]['sharpe_ratio']
        assert abs(actual - expected) < 0.001


# ════════════════════════════════════════════════════════════════════════════
# 单位标准化（百分比）
# ════════════════════════════════════════════════════════════════════════════

class TestUnitsStandard:
    def test_total_return_is_percentage(self):
        """total_return 应以百分比表达（+10% → ≈ 10.0，而非 0.10）"""
        r = _make_result(final_value=110_000.0)
        assert r.total_return >= 1.0, \
            f"total_return={r.total_return} 疑似小数形式，应为百分比"

    def test_annual_return_unit(self):
        r = _make_result(final_value=120_000.0)
        # 年化 20%+ 时数值应 > 1.0
        assert r.annual_return >= 1.0

    def test_max_drawdown_unit(self):
        """max_drawdown 以百分比表达（>0 时应 > 0.0001 而非接近 0）"""
        r = _make_result(final_value=90_000.0)
        md = r.metrics.max_drawdown
        # 有回撤时应有可见值（10%+ 的损失对应 max_drawdown > 1.0）
        assert md >= 1.0, f"max_drawdown={md} 疑似小数形式"

    def test_win_rate_percentage(self):
        """win_rate 以百分比表达（0-100 区间）"""
        r = _make_result()
        assert 0.0 <= r.metrics.win_rate <= 100.0
