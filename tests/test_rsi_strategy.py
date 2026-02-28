#!/usr/bin/env python
"""
RSI 策略单元测试
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading.strategies.rsi import RSIStrategy
from src.trading import BarData, Direction


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def _make_bar(symbol: str, close: float, day_offset: int = 0, volume: int = 10000) -> BarData:
    """创建测试用 BarData"""
    dt = datetime(2024, 1, 1) + timedelta(days=day_offset)
    return BarData(
        symbol=symbol,
        datetime=dt,
        open=close - 0.1,
        high=close + 0.2,
        low=close - 0.3,
        close=close,
        volume=volume,
    )


def _feed_bars(strategy: RSIStrategy, prices, symbol: str = "TEST"):
    """向策略批量推送 K 线"""
    strategy.initialize()
    for i, price in enumerate(prices):
        bar = _make_bar(symbol, price, day_offset=i)
        strategy.on_bar(bar)


# ---------------------------------------------------------------------------
# 初始化测试
# ---------------------------------------------------------------------------

def test_init_default_params():
    """默认参数初始化"""
    print("测试：默认参数初始化")

    s = RSIStrategy()
    s.initialize()

    assert s.get_parameter("rsi_period") == 14
    assert s.get_parameter("oversold") == 30
    assert s.get_parameter("overbought") == 70
    assert s.get_parameter("position_size") == 100
    assert s.get_parameter("rsi_smooth") is True

    print("  ✓ 默认参数验证通过")


def test_init_custom_params():
    """自定义参数初始化"""
    print("测试：自定义参数初始化")

    s = RSIStrategy(params={"rsi_period": 7, "oversold": 25, "overbought": 75})
    s.initialize()

    assert s.get_parameter("rsi_period") == 7
    assert s.get_parameter("oversold") == 25
    assert s.get_parameter("overbought") == 75

    print("  ✓ 自定义参数验证通过")


def test_init_invalid_params():
    """非法参数应抛出异常"""
    print("测试：非法参数初始化")

    # rsi_period < 2
    try:
        s = RSIStrategy(params={"rsi_period": 1})
        s.initialize()
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass

    # oversold >= overbought
    try:
        s = RSIStrategy(params={"oversold": 70, "overbought": 30})
        s.initialize()
        assert False, "应该抛出 ValueError"
    except ValueError:
        pass

    print("  ✓ 非法参数检测通过")


# ---------------------------------------------------------------------------
# RSI 计算测试
# ---------------------------------------------------------------------------

def test_rsi_simple_calculation():
    """简单均值 RSI 计算正确性"""
    print("测试：简单均值 RSI 计算")

    s = RSIStrategy(params={"rsi_smooth": False, "rsi_period": 5})
    s.initialize()

    # 全部上涨 → RSI 应趋近 100
    prices_up = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
    for price in prices_up:
        s._close_prices.append(price)

    rsi = s._calculate_rsi_simple(s._close_prices, 5)
    assert rsi is not None
    assert rsi > 90, f"全部上涨时 RSI 应 > 90，实际: {rsi:.2f}"

    # 全部下跌 → RSI 应趋近 0
    s2 = RSIStrategy(params={"rsi_smooth": False, "rsi_period": 5})
    s2.initialize()
    prices_down = [15.0, 14.0, 13.0, 12.0, 11.0, 10.0]
    for price in prices_down:
        s2._close_prices.append(price)

    rsi2 = s2._calculate_rsi_simple(s2._close_prices, 5)
    assert rsi2 is not None
    assert rsi2 < 10, f"全部下跌时 RSI 应 < 10，实际: {rsi2:.2f}"

    print(f"  ✓ 上涨 RSI={rsi:.2f}, 下跌 RSI={rsi2:.2f}")


def test_rsi_value_range():
    """RSI 值域应在 0–100"""
    print("测试：RSI 值域 [0, 100]")

    import random
    random.seed(42)

    s = RSIStrategy(params={"rsi_period": 14})
    s.initialize()

    prices = [100.0]
    for _ in range(50):
        prices.append(prices[-1] * (1 + random.uniform(-0.03, 0.03)))

    _feed_bars(s, prices)

    for rsi_val in s._rsi_values:
        assert 0 <= rsi_val <= 100, f"RSI 超出范围: {rsi_val}"

    print(f"  ✓ 共 {len(s._rsi_values)} 个 RSI 值均在 [0, 100] 内")


def test_rsi_insufficient_data():
    """数据不足时不应产生 RSI"""
    print("测试：数据不足时不计算 RSI")

    s = RSIStrategy(params={"rsi_period": 14})
    s.initialize()

    # 只推送 5 条，不够 period+1=15
    _feed_bars(s, [10, 11, 12, 13, 14])

    assert len(s._rsi_values) == 0, "数据不足时不应有 RSI 值"

    print("  ✓ 数据不足时 RSI 为空")


def test_rsi_wilder_smoothing():
    """Wilder 平滑法应产生平滑的 RSI 序列"""
    print("测试：Wilder 平滑法")

    s = RSIStrategy(params={"rsi_period": 14, "rsi_smooth": True})
    s.initialize()

    import random
    random.seed(0)
    prices = [100.0]
    for _ in range(60):
        prices.append(prices[-1] * (1 + random.uniform(-0.02, 0.02)))

    _feed_bars(s, prices)

    assert len(s._rsi_values) > 0
    assert s._avg_gain is not None
    assert s._avg_loss is not None

    # Wilder 平滑后的 RSI 应比简单均值更稳定（相邻差异较小）
    diffs = [abs(s._rsi_values[i] - s._rsi_values[i - 1]) for i in range(1, len(s._rsi_values))]
    avg_diff = sum(diffs) / len(diffs)
    assert avg_diff < 10, f"Wilder 平滑后相邻 RSI 平均差异应 < 10，实际: {avg_diff:.2f}"

    print(f"  ✓ Wilder RSI 相邻平均差异: {avg_diff:.2f}")


# ---------------------------------------------------------------------------
# 信号生成测试
# ---------------------------------------------------------------------------

def _make_oversold_prices(period: int = 5) -> list:
    """
    生成一组保证触发超卖→买入信号的价格序列（使用 period=5 的简单 RSI）：
    - 连续下跌 period+1 天使 RSI → 0 (< oversold=30)
    - 最后一天大幅反弹使 RSI 跳升至 > 30
    """
    # period+1 个价格产生 period 个全负变化 → RSI = 0
    start = 100.0
    drop_prices = [start - i for i in range(period + 1)]  # 长度 period+1
    # 大幅反弹：让 RSI 从 0 跳到 > 30
    # 5期: 1次+9, 4次-1 → avg_gain=1.8, avg_loss=0.8 → RSI≈69
    bounce_price = drop_prices[-1] + (period + 4)
    return drop_prices + [bounce_price]


def _make_overbought_prices(period: int = 5) -> list:
    """
    生成一组保证触发超买→卖出信号的价格序列（使用 period=5 的简单 RSI）：
    - 连续上涨 period+1 天使 RSI → 100 (> overbought=70)
    - 最后一天大幅回落使 RSI 跳降至 <= 70
    """
    start = 100.0
    surge_prices = [start + i for i in range(period + 1)]
    # 大幅回落：让 RSI 从 100 降到 <= 70
    pullback_price = surge_prices[-1] - (period + 4)
    return surge_prices + [pullback_price]


def test_buy_signal_on_oversold_reversal():
    """超卖反转应产生买入信号"""
    print("测试：超卖反转买入信号")

    period = 5
    s = RSIStrategy(params={
        "rsi_period": period,
        "oversold": 30,
        "overbought": 70,
        "position_size": 100,
        "min_hold_bars": 0,       # 不限最少持仓
        "stop_loss_pct": 0.99,    # 关闭止损
        "take_profit_pct": 0.99,  # 关闭止盈
        "rsi_smooth": False,
    })
    s.initialize()

    prices = _make_oversold_prices(period)
    for i, price in enumerate(prices):
        bar = _make_bar("TEST", price, day_offset=i)
        s.on_bar(bar)

    buy_signals = [sig for sig in s.signals if sig.direction == Direction.BUY]
    assert len(buy_signals) >= 1, (
        f"应产生至少 1 个买入信号，实际: {len(buy_signals)}，"
        f"RSI 序列: {[round(r,1) for r in s._rsi_values]}"
    )

    print(f"  ✓ 产生了 {len(buy_signals)} 个买入信号")


def test_sell_signal_on_overbought_reversal():
    """超买反转应产生卖出信号（需要先有持仓）"""
    print("测试：超买反转卖出信号")

    period = 5
    s = RSIStrategy(params={
        "rsi_period": period,
        "oversold": 30,
        "overbought": 70,
        "position_size": 100,
        "min_hold_bars": 0,
        "stop_loss_pct": 0.99,
        "take_profit_pct": 0.99,
        "rsi_smooth": False,
    })
    s.initialize()

    # 先手动建立初始持仓，开仓价格用序列首价
    entry = 100.0
    s.account.update_position("TEST", 100, entry)
    s.position_open_price = entry
    s.position_open_bars = 10  # 满足 min_hold_bars=0

    prices = _make_overbought_prices(period)
    for i, price in enumerate(prices):
        bar = _make_bar("TEST", price, day_offset=i)
        s.on_bar(bar)

    sell_signals = [sig for sig in s.signals if sig.direction == Direction.SELL]
    assert len(sell_signals) >= 1, (
        f"应产生至少 1 个卖出信号，实际: {len(sell_signals)}，"
        f"RSI 序列: {[round(r,1) for r in s._rsi_values]}"
    )

    print(f"  ✓ 产生了 {len(sell_signals)} 个卖出信号")


def test_no_signal_in_neutral_zone():
    """中性区间内不应产生信号"""
    print("测试：中性区间无信号")

    s = RSIStrategy(params={
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
        "rsi_smooth": False,
    })
    s.initialize()

    # 价格小幅随机波动，RSI 应稳定在中性区
    import random
    random.seed(1)
    prices = [100.0]
    for _ in range(40):
        prices.append(prices[-1] * (1 + random.uniform(-0.005, 0.005)))

    _feed_bars(s, prices)

    assert len(s.signals) == 0, f"中性区间不应有信号，实际: {len(s.signals)}"

    print("  ✓ 中性区间确实无信号")


def test_no_buy_when_already_long():
    """已有多头持仓时不重复买入"""
    print("测试：持仓状态不重复买入")

    period = 5
    s = RSIStrategy(params={
        "rsi_period": period,
        "oversold": 30,
        "min_hold_bars": 0,
        "stop_loss_pct": 0.99,
        "take_profit_pct": 0.99,
        "rsi_smooth": False,
    })
    s.initialize()

    # 预置持仓（entry price 与序列首价一致，避免意外触发止损/止盈）
    s.account.update_position("TEST", 100, 100.0)
    s.position_open_price = 100.0

    prices = _make_oversold_prices(period)
    for i, price in enumerate(prices):
        bar = _make_bar("TEST", price, day_offset=i)
        s.on_bar(bar)

    buy_signals = [sig for sig in s.signals if sig.direction == Direction.BUY]
    assert len(buy_signals) == 0, "已有持仓时不应产生买入信号"

    print("  ✓ 持仓状态下未重复买入")


# ---------------------------------------------------------------------------
# 止损止盈测试
# ---------------------------------------------------------------------------

def test_stop_loss_triggered():
    """触发止损时应产生卖出信号"""
    print("测试：止损触发")

    s = RSIStrategy(params={
        "rsi_period": 14,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.99,
        "min_hold_bars": 0,
        "rsi_smooth": False,
    })
    s.initialize()

    # 先热身，积累足够 RSI 历史
    warmup_prices = [100.0] * 16
    for i, p in enumerate(warmup_prices):
        s._close_prices.append(p)

    # 建立持仓
    entry_price = 100.0
    s.account.update_position("TEST", 100, entry_price)
    s.position_open_price = entry_price
    s.position_open_bars = 5  # 满足 min_hold_bars

    # 推送一根跌破止损价的 K 线
    crash_price = entry_price * (1 - 0.06)  # 跌 6%，超过 5% 止损
    bar = _make_bar("TEST", crash_price, day_offset=20)

    # 手动填充足够的 RSI 数据，使 on_bar 能进入止损检查
    s._rsi_values = [50.0, 50.0]  # 中性，不触发方向信号
    s.on_bar(bar)

    sell_signals = [sig for sig in s.signals if sig.direction == Direction.SELL]
    assert len(sell_signals) >= 1, "触发止损时应产生卖出信号"

    print("  ✓ 止损信号正确生成")


def test_take_profit_triggered():
    """触发止盈时应产生卖出信号"""
    print("测试：止盈触发")

    s = RSIStrategy(params={
        "rsi_period": 14,
        "stop_loss_pct": 0.99,
        "take_profit_pct": 0.10,
        "min_hold_bars": 0,
        "rsi_smooth": False,
    })
    s.initialize()

    # 先热身，积累足够收盘价历史（period+1 条）
    warmup_prices = [100.0] * 16
    for p in warmup_prices:
        s._close_prices.append(p)

    entry_price = 100.0
    s.account.update_position("TEST", 100, entry_price)
    s.position_open_price = entry_price
    s.position_open_bars = 5

    # 推送涨幅超过止盈阈值的 K 线
    profit_price = entry_price * 1.12  # 涨 12%，超过 10% 止盈
    bar = _make_bar("TEST", profit_price, day_offset=20)

    s._rsi_values = [50.0, 50.0]
    s.on_bar(bar)

    sell_signals = [sig for sig in s.signals if sig.direction == Direction.SELL]
    assert len(sell_signals) >= 1, "触发止盈时应产生卖出信号"

    print("  ✓ 止盈信号正确生成")


# ---------------------------------------------------------------------------
# 置信度测试
# ---------------------------------------------------------------------------

def test_confidence_range():
    """信号置信度应在 [0, 1] 内"""
    print("测试：信号置信度范围")

    s = RSIStrategy()
    s.initialize()
    s._rsi_values = [20.0]  # 超卖区

    c_buy = s._calculate_signal_confidence(Direction.BUY)
    c_sell = s._calculate_signal_confidence(Direction.SELL)

    assert 0.0 <= c_buy <= 1.0, f"买入置信度超出范围: {c_buy}"
    assert 0.0 <= c_sell <= 1.0, f"卖出置信度超出范围: {c_sell}"

    print(f"  ✓ 买入置信度={c_buy:.4f}, 卖出置信度={c_sell:.4f}")


def test_oversold_confidence_higher_when_rsi_lower():
    """RSI 越低，超卖买入置信度应越高"""
    print("测试：超卖程度越深置信度越高")

    s = RSIStrategy()
    s.initialize()

    s._rsi_values = [25.0]
    c_25 = s._calculate_signal_confidence(Direction.BUY)

    s._rsi_values = [10.0]
    c_10 = s._calculate_signal_confidence(Direction.BUY)

    assert c_10 > c_25, f"RSI=10 时置信度({c_10:.4f})应高于 RSI=25 时({c_25:.4f})"

    print(f"  ✓ RSI=10 置信度={c_10:.4f} > RSI=25 置信度={c_25:.4f}")


# ---------------------------------------------------------------------------
# 状态查询测试
# ---------------------------------------------------------------------------

def test_get_current_rsi():
    """get_current_rsi 应返回最新 RSI"""
    print("测试：get_current_rsi")

    s = RSIStrategy(params={"rsi_period": 5, "rsi_smooth": False})
    s.initialize()

    prices = [10.0, 11.0, 12.0, 11.0, 10.0, 11.0, 12.0]
    _feed_bars(s, prices)

    current = s.get_current_rsi()
    if s._rsi_values:
        assert current == s._rsi_values[-1], "get_current_rsi 应返回 _rsi_values 末尾值"
        print(f"  ✓ 当前 RSI={current:.2f}")
    else:
        assert current is None
        print("  ✓ 数据不足时返回 None")


def test_get_strategy_status():
    """get_strategy_status 应返回完整状态字典"""
    print("测试：get_strategy_status")

    s = RSIStrategy()
    s.initialize()

    status = s.get_strategy_status()

    required_keys = [
        "strategy_id", "strategy_name", "parameters",
        "current_rsi", "rsi_history_length",
        "avg_gain", "avg_loss",
        "position_open_bars", "position_open_price",
        "signal_count", "executed_signal_count",
    ]
    for key in required_keys:
        assert key in status, f"状态字典缺少键: {key}"

    print(f"  ✓ 状态字典包含所有必要字段")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_init_default_params,
        test_init_custom_params,
        test_init_invalid_params,
        test_rsi_simple_calculation,
        test_rsi_value_range,
        test_rsi_insufficient_data,
        test_rsi_wilder_smoothing,
        test_buy_signal_on_oversold_reversal,
        test_sell_signal_on_overbought_reversal,
        test_no_signal_in_neutral_zone,
        test_no_buy_when_already_long,
        test_stop_loss_triggered,
        test_take_profit_triggered,
        test_confidence_range,
        test_oversold_confidence_higher_when_rsi_lower,
        test_get_current_rsi,
        test_get_strategy_status,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR ({type(e).__name__}): {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过 / {failed} 失败 (共 {len(tests)} 个测试)")
    print("=" * 50)

    sys.exit(0 if failed == 0 else 1)
