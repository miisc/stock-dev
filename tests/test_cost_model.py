"""
CostModel 单元测试

测试交易成本计算的准确性，包括佣金、印花税、滑点等。
运行方式: python tests/test_cost_model.py
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.cost_model import CostModel


def test_commission_buy_large_amount():
    """大额买入：佣金 = amount × 0.0003（超过最低5元）"""
    model = CostModel()
    commission = model.calculate_commission(100_000, is_sell=False)
    expected = 100_000 * 0.0003  # 30.0
    assert abs(commission - expected) < 1e-9, f"Expected {expected}, got {commission}"
    print(f"✓ 大额买入佣金: {commission:.2f}（期望 {expected:.2f}）")


def test_commission_buy_small_amount():
    """小额买入：触发最低佣金 5.0"""
    model = CostModel()
    commission = model.calculate_commission(100, is_sell=False)
    expected = 5.0  # max(100 * 0.0003, 5.0) = 5.0
    assert abs(commission - expected) < 1e-9, f"Expected {expected}, got {commission}"
    print(f"✓ 小额买入最低佣金: {commission:.2f}（期望 {expected:.2f}）")


def test_commission_sell_large_amount():
    """大额卖出：佣金 + 印花税（0.1%）"""
    model = CostModel()
    commission = model.calculate_commission(100_000, is_sell=True)
    base = 100_000 * 0.0003       # 30.0
    stamp = 100_000 * 0.001       # 100.0
    expected = base + stamp        # 130.0
    assert abs(commission - expected) < 1e-9, f"Expected {expected}, got {commission}"
    print(f"✓ 大额卖出佣金+印花税: {commission:.2f}（期望 {expected:.2f}）")


def test_commission_sell_small_amount():
    """小额卖出：最低佣金 + 印花税"""
    model = CostModel()
    commission = model.calculate_commission(100, is_sell=True)
    base = 5.0                    # min floor
    stamp = 100 * 0.001           # 0.1
    expected = base + stamp        # 5.1
    assert abs(commission - expected) < 1e-9, f"Expected {expected}, got {commission}"
    print(f"✓ 小额卖出佣金+印花税: {commission:.2f}（期望 {expected:.2f}）")


def test_slippage():
    """滑点 = amount × 0.001"""
    model = CostModel()
    slippage = model.calculate_slippage(100_000)
    expected = 100_000 * 0.001    # 100.0
    assert abs(slippage - expected) < 1e-9, f"Expected {expected}, got {slippage}"
    print(f"✓ 滑点: {slippage:.2f}（期望 {expected:.2f}）")


def test_total_cost_buy():
    """总成本（买入）= 佣金 + 滑点"""
    model = CostModel()
    result = model.calculate_total_cost(100_000, is_sell=False)
    expected_commission = 30.0
    expected_slippage = 100.0
    expected_total = expected_commission + expected_slippage
    assert abs(result['commission'] - expected_commission) < 1e-9
    assert abs(result['slippage'] - expected_slippage) < 1e-9
    assert abs(result['total_cost'] - expected_total) < 1e-9
    assert result['stamp_duty'] == 0.0
    print(f"✓ 总成本（买入）: {result['total_cost']:.2f}（期望 {expected_total:.2f}）")


def test_total_cost_sell():
    """总成本（卖出）= 佣金 + 印花税 + 滑点"""
    model = CostModel()
    result = model.calculate_total_cost(100_000, is_sell=True)
    expected_commission = 30.0
    expected_stamp = 100.0
    expected_slippage = 100.0
    expected_total = expected_commission + expected_stamp + expected_slippage
    assert abs(result['commission'] - (expected_commission + expected_stamp)) < 1e-9
    assert abs(result['slippage'] - expected_slippage) < 1e-9
    assert abs(result['total_cost'] - expected_total) < 1e-9
    print(f"✓ 总成本（卖出）: {result['total_cost']:.2f}（期望 {expected_total:.2f}）")


def test_custom_rates():
    """自定义费率"""
    model = CostModel(commission_rate=0.001, slippage_rate=0.002, min_commission=10.0)
    commission = model.calculate_commission(5_000, is_sell=False)
    expected = 5_000 * 0.001   # 5.0，低于min_commission=10.0
    assert abs(commission - 10.0) < 1e-9, f"Expected 10.0, got {commission}"
    commission2 = model.calculate_commission(20_000, is_sell=False)
    expected2 = 20_000 * 0.001  # 20.0，高于min_commission
    assert abs(commission2 - expected2) < 1e-9
    print(f"✓ 自定义费率: {commission:.2f} / {commission2:.2f}")


def test_zero_amount():
    """零金额时不崩溃"""
    model = CostModel()
    commission = model.calculate_commission(0, is_sell=False)
    slippage = model.calculate_slippage(0)
    # min_commission=5.0 floor still applies
    assert commission == 5.0
    assert slippage == 0.0
    print(f"✓ 零金额: commission={commission}, slippage={slippage}")


if __name__ == '__main__':
    tests = [
        test_commission_buy_large_amount,
        test_commission_buy_small_amount,
        test_commission_sell_large_amount,
        test_commission_sell_small_amount,
        test_slippage,
        test_total_cost_buy,
        test_total_cost_sell,
        test_custom_rates,
        test_zero_amount,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败")
