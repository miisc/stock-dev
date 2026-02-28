"""
前视偏差（Look-Ahead Bias）验证测试

核心规则：当日收盘产生的信号，必须在次日开盘时才能成交。
本测试用 mock 数据运行引擎，验证成交价格和成交日期均符合"次日开盘执行"逻辑。

运行方式: python tests/test_lookahead_bias.py
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from unittest.mock import patch
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from src.trading.strategy import Strategy
from src.trading.bar_data import BarData
from src.backtesting.backtest_engine import BacktestEngine, BacktestConfig


# ─── 极简策略：第一根 Bar 结束后发出买入信号 ─────────────────────────────────

class BuyOnFirstBarStrategy(Strategy):
    """
    仅在第一根 Bar 时生成一次 BUY 信号；后续 Bars 什么也不做。
    用于验证：信号在第 0 日（Day0）产生，成交必须在第 1 日开盘（Day1 open）。
    """

    def on_init(self) -> None:
        self._signal_sent = False

    def on_bar(self, bar: BarData) -> None:
        if not self._signal_sent:
            # 使用当前收盘价作为信号价格（引擎会用次日开盘价成交）
            self.buy(bar.symbol, bar.close, 100, reason='first-bar-buy')
            self._signal_sent = True


# ─── 合成行情数据 ────────────────────────────────────────────────────────────

def make_price_df(dates, opens, closes, high_factor=1.01, low_factor=0.99):
    """构造最简 DataFrame，供 DataQuery mock 使用。
    high = max(open, close) * high_factor（保证 high >= max(open, close)）
    low  = min(open, close) * low_factor  （保证 low  <= min(open, close)）
    """
    highs = [max(o, c) * high_factor for o, c in zip(opens, closes)]
    lows  = [min(o, c) * low_factor  for o, c in zip(opens, closes)]
    df = pd.DataFrame({
        'open':   opens,
        'high':   highs,
        'low':    lows,
        'close':  closes,
        'volume': [1_000_000] * len(dates),
    }, index=dates)
    return df


# ─── 测试 ────────────────────────────────────────────────────────────────────

def test_signal_executed_next_day_open():
    """
    Day0 收盘信号 → Day1 开盘成交，成交价 = Day1 open（不是 Day0 close）
    """
    dates = [
        datetime(2023, 1, 3),   # Day0 – 策略在这里发出 BUY 信号
        datetime(2023, 1, 4),   # Day1 – 引擎应在此日开盘执行买入
        datetime(2023, 1, 5),   # Day2 – 额外日期，让引擎有机会更新组合
    ]
    opens  = [10.00, 10.50, 11.00]   # Day1 特意设置不同于 Day0 收盘价
    closes = [10.20, 10.80, 11.20]

    mock_df = make_price_df(dates, opens, closes)

    config = BacktestConfig(
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=100_000.0,
    )
    engine = BacktestEngine(config)
    strategy = BuyOnFirstBarStrategy('test_bias', '前视偏差测试策略')

    # 用 mock 替换 DataQuery，避免真实数据库连接
    with patch.object(engine.data_query, 'get_stock_daily', return_value=mock_df):
        result = engine.run_backtest(strategy, ['000001'])

    # ── 验证 1：应有且仅有 1 笔交易（Day1 的买入）
    assert len(result.trades) == 1, \
        f"应有 1 笔成交，实际 {len(result.trades)} 笔"
    print(f"✓ 成交笔数: {len(result.trades)}")

    trade = result.trades[0]

    # ── 验证 2：成交价格 ≈ Day1 开盘价 × (1 + slippage)，而非 Day0 收盘价
    # 引擎默认 slippage_rate=0.001（买入时价格 = market_price × 1.001）
    slippage_rate = 0.001
    day1_open = opens[1]  # 10.50
    expected_price = day1_open * (1 + slippage_rate)  # 10.5105
    assert abs(trade['price'] - expected_price) < 1e-6, \
        f"成交价应约为 {expected_price:.4f}（Day1 开盘 + 滑点），实际 {trade['price']}"
    print(f"✓ 成交价格 ≈ Day1 开盘价+滑点: {trade['price']:.4f} ≈ {expected_price:.4f}")

    # ── 验证 3：成交价格与 Day0 收盘价+滑点 明显不同（确认无前视偏差）
    day0_close = closes[0]  # 10.20
    day0_close_with_slip = day0_close * (1 + slippage_rate)  # 10.2102
    assert abs(trade['price'] - day0_close_with_slip) > 0.01, \
        f"成交价不应基于信号日收盘价 {day0_close_with_slip}，实际 {trade['price']}"
    print(f"✓ 成交价 ≠ 信号日收盘+滑点（无前视偏差）: {trade['price']:.4f} ≠ {day0_close_with_slip:.4f}")


def test_no_trade_on_signal_day():
    """
    Day0 当天不应有任何成交。pending_orders 机制确保信号在当天不被立即执行。
    """
    dates = [
        datetime(2023, 2, 1),
        datetime(2023, 2, 2),
    ]
    opens  = [20.0, 21.0]
    closes = [20.5, 21.5]
    mock_df = make_price_df(dates, opens, closes)

    config = BacktestConfig(
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=50_000.0,
    )
    engine = BacktestEngine(config)
    strategy = BuyOnFirstBarStrategy('test_no_trade', '当天无成交测试')

    with patch.object(engine.data_query, 'get_stock_daily', return_value=mock_df):
        result = engine.run_backtest(strategy, ['000001'])

    # 与 test_signal_executed_next_day_open 同理：只有 1 笔成交，且发生在 Day1
    assert len(result.trades) >= 1, "至少应有 1 笔成交（Day1 执行）"
    trade = result.trades[0]

    # Day0 close=20.5；Day1 open=21.0+slippage；确认是用 Day1 开盘成交
    slippage_rate = 0.001
    expected = opens[1] * (1 + slippage_rate)
    assert abs(trade['price'] - expected) < 1e-6, \
        f"应在 Day1 开盘成交，成交价应约 {expected:.4f}，实际 {trade['price']}"
    print(f"✓ 信号日无成交，次日开盘执行: {trade['price']:.4f}")


def test_multiple_signals_each_executed_next_day():
    """
    可以扩展：多天内只生成一次信号，确保每次信号都在次日执行。
    这里用一个只买一次的策略验证最基本情形。
    """
    dates = [
        datetime(2023, 3, 1),
        datetime(2023, 3, 2),
        datetime(2023, 3, 3),
        datetime(2023, 3, 6),
    ]
    opens  = [100.0, 105.0, 108.0, 110.0]
    closes = [102.0, 106.0, 107.0, 112.0]
    mock_df = make_price_df(dates, opens, closes)

    config = BacktestConfig(
        start_date=dates[0],
        end_date=dates[-1],
        initial_cash=200_000.0,
    )
    engine = BacktestEngine(config)
    strategy = BuyOnFirstBarStrategy('test_multi', '多日策略测试')

    with patch.object(engine.data_query, 'get_stock_daily', return_value=mock_df):
        result = engine.run_backtest(strategy, ['000001'])

    assert len(result.trades) == 1
    slippage_rate = 0.001
    expected = opens[1] * (1 + slippage_rate)
    assert abs(result.trades[0]['price'] - expected) < 1e-6, \
        f"应在 Day1 开盘（{expected:.4f}）成交，实际 {result.trades[0]['price']}"
    print(f"✓ 多日行情中信号仍在次日执行: {result.trades[0]['price']:.4f}")


def test_pending_orders_cleared_after_execution():
    """
    执行完 pending orders 后列表应被清空，不会重复执行。
    """
    dates = [
        datetime(2023, 4, 3),
        datetime(2023, 4, 4),
        datetime(2023, 4, 5),
    ]
    opens  = [50.0, 51.0, 52.0]
    closes = [50.5, 51.5, 52.5]
    mock_df = make_price_df(dates, opens, closes)

    config = BacktestConfig(start_date=dates[0], end_date=dates[-1], initial_cash=100_000.0)
    engine = BacktestEngine(config)
    strategy = BuyOnFirstBarStrategy('test_clear', '订单清空测试')

    with patch.object(engine.data_query, 'get_stock_daily', return_value=mock_df):
        result = engine.run_backtest(strategy, ['000001'])

    # 只能有 1 笔成交（不能因 pending_orders 未清空而在 Day2 重复执行）
    assert len(result.trades) == 1, \
        f"不应有重复成交，期望 1 笔，实际 {len(result.trades)} 笔"
    print(f"✓ pending_orders 执行后被清空，无重复成交")


if __name__ == '__main__':
    tests = [
        test_signal_executed_next_day_open,
        test_no_trade_on_signal_day,
        test_multiple_signals_each_executed_next_day,
        test_pending_orders_cleared_after_execution,
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
