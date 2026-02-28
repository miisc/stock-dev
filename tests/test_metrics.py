"""
BacktestResult / PerformanceMetrics 单元测试

使用合成数据验证绩效指标计算公式的准确性（无需数据库或网络）。
运行方式: python tests/test_metrics.py
"""

import sys
import math
from pathlib import Path
from datetime import datetime
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from src.backtesting.result import BacktestResult


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def build_result(daily_values, trades=None,
                 initial_cash=100_000.0,
                 start='2023-01-01', end='2023-12-31'):
    """
    用给定的每日组合总值列表构造 BacktestResult，省掉策略字段。
    daily_values: [100000, 101000, ...] → final_value = daily_values[-1]
    """
    start_dt = datetime.strptime(start, '%Y-%m-%d')
    end_dt   = datetime.strptime(end,   '%Y-%m-%d')
    daily_portfolio = [
        {'date': None, 'total_value': v, 'cash': v, 'position_value': 0.0, 'positions': {}}
        for v in daily_values
    ]
    return BacktestResult(
        strategy_name='test',
        symbols=['000001'],
        start_date=start_dt,
        end_date=end_dt,
        initial_cash=initial_cash,
        final_value=daily_values[-1],
        trades=trades or [],
        daily_portfolio=daily_portfolio,
    )


# ─── 总收益率 ────────────────────────────────────────────────────────────────

def test_total_return_positive():
    r = build_result([100_000, 110_000])
    expected = 10.0
    assert abs(r.total_return - expected) < 1e-9, f"{r.total_return}"
    print(f"✓ 总收益率（盈利）: {r.total_return:.2f}%")


def test_total_return_negative():
    r = build_result([100_000, 80_000])
    expected = -20.0
    assert abs(r.total_return - expected) < 1e-9, f"{r.total_return}"
    print(f"✓ 总收益率（亏损）: {r.total_return:.2f}%")


def test_total_return_flat():
    r = build_result([100_000, 100_000])
    assert abs(r.total_return) < 1e-9
    print("✓ 总收益率（持平）: 0.00%")


# ─── 年化收益率 ──────────────────────────────────────────────────────────────

def test_annual_return_formula():
    """
    126 个交易日（约半年），总收益 10% → 年化 ≈ (1.10)^(252/126) - 1 = 21%
    """
    n = 126
    start_val = 100_000.0
    end_val   = 110_000.0  # +10%
    values = [start_val] * n
    values[-1] = end_val
    r = build_result(values)
    total_ret = (end_val - start_val) / start_val   # 0.10
    expected = ((1 + total_ret) ** (252.0 / n) - 1) * 100
    assert abs(r.annual_return - expected) < 0.01, f"{r.annual_return:.4f} vs {expected:.4f}"
    print(f"✓ 年化收益率: {r.annual_return:.2f}% (期望 {expected:.2f}%)")


def test_annual_return_requires_at_least_2_days():
    r = build_result([100_000])
    assert r.annual_return == 0.0
    print("✓ 年化收益率（不足2日）: 0.00%")


# ─── 最大回撤 ────────────────────────────────────────────────────────────────

def test_max_drawdown_simple():
    """100k → 120k → 90k: 最大回撤 = (120-90)/120*100 = 25%"""
    r = build_result([100_000, 120_000, 90_000])
    expected = (120_000 - 90_000) / 120_000 * 100  # 25.0
    assert abs(r.metrics.max_drawdown - expected) < 1e-6, f"{r.metrics.max_drawdown}"
    print(f"✓ 最大回撤: {r.metrics.max_drawdown:.2f}% (期望 {expected:.2f}%)")


def test_max_drawdown_monotone_up():
    """单调上涨 → 最大回撤 = 0"""
    r = build_result([100_000, 105_000, 110_000, 120_000])
    assert r.metrics.max_drawdown == 0.0
    print("✓ 最大回撤（单调上涨）: 0.00%")


def test_max_drawdown_peak_then_recover():
    """高峰后回撤再恢复，最大回撤以历史峰值计算"""
    r = build_result([100_000, 150_000, 100_000, 160_000])
    expected = (150_000 - 100_000) / 150_000 * 100  # 33.33%
    assert abs(r.metrics.max_drawdown - expected) < 1e-6
    print(f"✓ 最大回撤（回升后高峰再创新高）: {r.metrics.max_drawdown:.2f}%")


# ─── 夏普比率 ────────────────────────────────────────────────────────────────

def test_sharpe_ratio_formula():
    """
    用已知序列手动计算夏普，与 result.metrics.sharpe_ratio 对比。
    """
    # 构建每日值：30日，固定1%日涨幅（正收益以确保夏普>0）
    n = 30
    values = [100_000 * (1.01 ** i) for i in range(n)]
    r = build_result(values)

    daily_ret_arr = np.array([(values[i] - values[i-1]) / values[i-1] for i in range(1, n)])
    vol = float(np.std(daily_ret_arr)) * math.sqrt(252) * 100
    total_ret = (values[-1] - values[0]) / values[0]
    annual_ret = ((1 + total_ret) ** (252.0 / n) - 1) * 100
    expected_sharpe = (annual_ret / 100 - 0.02) / (vol / 100) if vol > 0 else 0.0

    assert abs(r.metrics.sharpe_ratio - expected_sharpe) < 0.001, \
        f"{r.metrics.sharpe_ratio:.4f} vs {expected_sharpe:.4f}"
    print(f"✓ 夏普比率: {r.metrics.sharpe_ratio:.4f} (期望 {expected_sharpe:.4f})")


def test_sharpe_ratio_zero_volatility():
    """所有日涨幅相同(波动率=0) → 夏普比率 = 0"""
    # BacktestResult 中 volatility=0 → sharpe=0
    r = build_result([100_000] * 5)  # flat portfolio → zero volatility
    assert r.metrics.sharpe_ratio == 0.0
    print("✓ 夏普比率（零波动）: 0.00")


# ─── 胜率 ───────────────────────────────────────────────────────────────────

def test_win_rate():
    """3赢 1平 1负 → 胜率 60%"""
    trades = [
        {'pnl': 500},
        {'pnl': 200},
        {'pnl': 100},
        {'pnl': 0},
        {'pnl': -300},
    ]
    r = build_result([100_000, 100_500], trades=trades)
    expected = 3 / 5 * 100  # 60.0
    assert abs(r.metrics.win_rate - expected) < 1e-9
    print(f"✓ 胜率: {r.metrics.win_rate:.2f}% (期望 {expected:.2f}%)")


def test_win_rate_no_trades():
    r = build_result([100_000, 100_000])
    assert r.metrics.win_rate == 0.0
    print("✓ 胜率（无交易）: 0.00%")


# ─── 盈亏比 ─────────────────────────────────────────────────────────────────

def test_profit_loss_ratio():
    """均盈 300, 均亏 100 → 盈亏比 = 3.0"""
    trades = [
        {'pnl': 300}, {'pnl': 300},   # 盈利
        {'pnl': -100}, {'pnl': -100}, # 亏损
    ]
    r = build_result([100_000, 100_400], trades=trades)
    assert abs(r.metrics.profit_loss_ratio - 3.0) < 1e-9
    print(f"✓ 盈亏比: {r.metrics.profit_loss_ratio:.2f} (期望 3.00)")


def test_profit_loss_ratio_no_losses():
    """无亏损交易 → inf"""
    trades = [{'pnl': 100}, {'pnl': 200}]
    r = build_result([100_000, 100_300], trades=trades)
    assert math.isinf(r.metrics.profit_loss_ratio)
    print("✓ 盈亏比（无亏损）: inf")


if __name__ == '__main__':
    tests = [
        test_total_return_positive,
        test_total_return_negative,
        test_total_return_flat,
        test_annual_return_formula,
        test_annual_return_requires_at_least_2_days,
        test_max_drawdown_simple,
        test_max_drawdown_monotone_up,
        test_max_drawdown_peak_then_recover,
        test_sharpe_ratio_formula,
        test_sharpe_ratio_zero_volatility,
        test_win_rate,
        test_win_rate_no_trades,
        test_profit_loss_ratio,
        test_profit_loss_ratio_no_losses,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败")
