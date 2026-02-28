"""
RSI 策略实现

基于相对强弱指数（Relative Strength Index）的均值回归策略：
- RSI 低于超卖阈值且向上反转时买入
- RSI 高于超买阈值且向下反转时卖出

RSI 计算公式:
    RS  = 平均上涨幅度 / 平均下跌幅度（基于 Wilder 平滑法）
    RSI = 100 - 100 / (1 + RS)
"""

import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.trading import Strategy, BarData, Signal, Direction


class RSIStrategy(Strategy):
    """
    RSI 策略

    利用 RSI 指标识别超买超卖区间，在均值回归时产生交易信号。
    """

    def __init__(
        self,
        strategy_id: str = "rsi",
        name: str = "RSI 策略",
        params: Optional[dict] = None,
    ):
        """
        初始化 RSI 策略

        Args:
            strategy_id: 策略唯一标识
            name: 策略名称
            params: 策略参数（会覆盖默认值）
        """
        default_params = {
            "rsi_period": 14,          # RSI 计算周期
            "oversold": 30,            # 超卖阈值，RSI 低于此值视为超卖
            "overbought": 70,          # 超买阈值，RSI 高于此值视为超买
            "position_size": 100,      # 每次交易数量（股）
            "min_hold_bars": 3,        # 最少持仓 K 线数，避免频繁交易
            "stop_loss_pct": 0.05,     # 止损百分比
            "take_profit_pct": 0.15,   # 止盈百分比
            "rsi_smooth": True,        # 是否使用 Wilder 平滑法（否则用简单均值）
        }

        if params:
            default_params.update(params)

        super().__init__(strategy_id, name, default_params)

        # 内部状态
        self._close_prices: List[float] = []    # 收盘价历史
        self._rsi_values: List[float] = []       # RSI 序列

        # Wilder 平滑法所需的滚动均值
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None

        # 持仓跟踪
        self.position_open_bars: int = 0
        self.position_open_price: float = 0.0

        self.logger.info(f"RSI 策略初始化完成，参数: {self.params}")

    # ------------------------------------------------------------------
    # 生命周期钩子
    # ------------------------------------------------------------------

    def on_init(self):
        """策略初始化 —— 参数合法性检验"""
        period = self.get_parameter("rsi_period")
        oversold = self.get_parameter("oversold")
        overbought = self.get_parameter("overbought")

        if period < 2:
            raise ValueError(f"rsi_period 必须 >= 2，当前值: {period}")
        if not (0 < oversold < overbought < 100):
            raise ValueError(
                f"阈值不合法，需满足 0 < oversold({oversold}) < overbought({overbought}) < 100"
            )

        self.logger.info(
            f"RSI 策略参数验证通过: period={period}, "
            f"oversold={oversold}, overbought={overbought}"
        )

    def on_bar(self, bar: BarData):
        """
        处理新 K 线数据

        Args:
            bar: 当前 K 线
        """
        self._close_prices.append(bar.close)

        period = self.get_parameter("rsi_period")

        # 数据不足时跳过
        if len(self._close_prices) < period + 1:
            return

        # 计算 RSI
        rsi = self._calculate_rsi(self._close_prices, period)
        if rsi is None:
            return

        self._rsi_values.append(rsi)

        # 更新持仓计数
        position = self.get_position(bar.symbol)
        if position.is_long:
            self.position_open_bars += 1

            # 止损 / 止盈检查
            if self._check_stop_loss(bar, position):
                return
            if self._check_take_profit(bar, position):
                return

        # 需要至少两个 RSI 值才能判断方向
        if len(self._rsi_values) < 2:
            return

        prev_rsi = self._rsi_values[-2]
        curr_rsi = self._rsi_values[-1]

        # 超卖区域向上反转 → 买入
        if (
            prev_rsi < self.get_parameter("oversold")
            and curr_rsi >= self.get_parameter("oversold")
            and not position.is_long
        ):
            self._generate_buy_signal(bar, f"RSI 超卖反转买入 ({curr_rsi:.1f})")

        # 超买区域向下反转 → 卖出
        elif (
            prev_rsi > self.get_parameter("overbought")
            and curr_rsi <= self.get_parameter("overbought")
            and position.is_long
        ):
            self._generate_sell_signal(bar, f"RSI 超买反转卖出 ({curr_rsi:.1f})")

    # ------------------------------------------------------------------
    # RSI 计算
    # ------------------------------------------------------------------

    def _calculate_rsi(self, prices: List[float], period: int) -> Optional[float]:
        """
        计算 RSI 值

        选择 Wilder 平滑法（指数移动平均）或简单均值，由参数 rsi_smooth 控制。

        Args:
            prices: 收盘价序列（最新值在末尾）
            period: RSI 周期

        Returns:
            RSI 值（0–100），数据不足时返回 None
        """
        if len(prices) < period + 1:
            return None

        use_smooth = self.get_parameter("rsi_smooth")

        if use_smooth:
            return self._calculate_rsi_wilder(prices, period)
        else:
            return self._calculate_rsi_simple(prices, period)

    def _calculate_rsi_simple(self, prices: List[float], period: int) -> Optional[float]:
        """
        用简单均值计算 RSI（适合首次计算或单步验证）

        Args:
            prices: 收盘价序列
            period: 计算周期

        Returns:
            RSI 值
        """
        if len(prices) < period + 1:
            return None

        changes = [prices[i] - prices[i - 1] for i in range(len(prices) - period, len(prices))]
        gains = [c for c in changes if c > 0]
        losses = [-c for c in changes if c < 0]

        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def _calculate_rsi_wilder(self, prices: List[float], period: int) -> Optional[float]:
        """
        用 Wilder 平滑法（指数移动平均）计算 RSI

        首次调用时使用简单均值热身，之后增量更新。

        Args:
            prices: 收盘价序列
            period: 计算周期

        Returns:
            RSI 值
        """
        if len(prices) < period + 1:
            return None

        if self._avg_gain is None or self._avg_loss is None:
            # 热身：使用最近 period 个变化量的简单均值
            warmup = [prices[i] - prices[i - 1] for i in range(1, period + 1)]
            gains_w = [c for c in warmup if c > 0]
            losses_w = [-c for c in warmup if c < 0]
            self._avg_gain = sum(gains_w) / period
            self._avg_loss = sum(losses_w) / period
        else:
            # 增量更新：只需用最新的一个变化量
            change = prices[-1] - prices[-2]
            gain = change if change > 0 else 0.0
            loss = -change if change < 0 else 0.0

            alpha = 1.0 / period  # Wilder: alpha = 1/period
            self._avg_gain = self._avg_gain * (1 - alpha) + gain * alpha
            self._avg_loss = self._avg_loss * (1 - alpha) + loss * alpha

        if self._avg_loss == 0:
            return 100.0

        rs = self._avg_gain / self._avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    # ------------------------------------------------------------------
    # 信号生成
    # ------------------------------------------------------------------

    def _generate_buy_signal(self, bar: BarData, reason: str):
        """生成买入信号"""
        position = self.get_position(bar.symbol)
        if position.is_long:
            return

        # 最少持仓 K 线数检查（此处用于防止开仓后立即反向）
        if self.position_open_bars > 0 and self.position_open_bars < self.get_parameter("min_hold_bars"):
            return

        volume = self.get_parameter("position_size")
        confidence = self._calculate_signal_confidence(Direction.BUY)

        signal = self.buy(
            symbol=bar.symbol,
            price=bar.close,
            volume=volume,
            reason=reason,
            confidence=confidence,
        )

        self.position_open_bars = 0
        self.position_open_price = bar.close

        self.logger.info(f"生成买入信号: {signal}, 原因: {reason}")

    def _generate_sell_signal(self, bar: BarData, reason: str):
        """生成卖出信号"""
        position = self.get_position(bar.symbol)
        if not position.is_long:
            return

        # 最少持仓 K 线数检查
        if self.position_open_bars < self.get_parameter("min_hold_bars"):
            return

        volume = position.volume
        confidence = self._calculate_signal_confidence(Direction.SELL)

        signal = self.sell(
            symbol=bar.symbol,
            price=bar.close,
            volume=volume,
            reason=reason,
            confidence=confidence,
        )

        self.position_open_bars = 0
        self.position_open_price = 0.0

        self.logger.info(f"生成卖出信号: {signal}, 原因: {reason}")

    # ------------------------------------------------------------------
    # 风险控制
    # ------------------------------------------------------------------

    def _check_stop_loss(self, bar: BarData, position) -> bool:
        """
        检查止损条件

        Args:
            bar: 当前 K 线
            position: 当前持仓

        Returns:
            是否触发止损
        """
        if self.position_open_price <= 0:
            return False

        pnl_pct = (bar.close - self.position_open_price) / self.position_open_price

        if pnl_pct <= -self.get_parameter("stop_loss_pct"):
            self._generate_sell_signal(bar, f"止损卖出，亏损 {pnl_pct:.2%}")
            return True

        return False

    def _check_take_profit(self, bar: BarData, position) -> bool:
        """
        检查止盈条件

        Args:
            bar: 当前 K 线
            position: 当前持仓

        Returns:
            是否触发止盈
        """
        if self.position_open_price <= 0:
            return False

        pnl_pct = (bar.close - self.position_open_price) / self.position_open_price

        if pnl_pct >= self.get_parameter("take_profit_pct"):
            self._generate_sell_signal(bar, f"止盈卖出，盈利 {pnl_pct:.2%}")
            return True

        return False

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _calculate_signal_confidence(self, direction: Direction) -> float:
        """
        根据 RSI 偏离程度估算信号置信度

        Args:
            direction: 交易方向

        Returns:
            置信度（0.0–1.0）
        """
        if not self._rsi_values:
            return 0.5

        current_rsi = self._rsi_values[-1]
        oversold = self.get_parameter("oversold")
        overbought = self.get_parameter("overbought")

        if direction == Direction.BUY:
            # RSI 越低（越远离超卖阈值），置信度越高
            distance = max(oversold - current_rsi, 0)
            confidence = 0.5 + min(distance / oversold, 0.5)
        else:
            # RSI 越高（越远离超买阈值），置信度越高
            distance = max(current_rsi - overbought, 0)
            confidence = 0.5 + min(distance / (100 - overbought), 0.5)

        return round(min(max(confidence, 0.1), 1.0), 4)

    def get_current_rsi(self) -> Optional[float]:
        """
        获取最新 RSI 值

        Returns:
            最新 RSI 值，无数据时返回 None
        """
        return self._rsi_values[-1] if self._rsi_values else None

    def get_strategy_status(self) -> dict:
        """
        获取策略状态摘要

        Returns:
            包含主要状态信息的字典
        """
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.name,
            "parameters": self.params,
            "current_rsi": self.get_current_rsi(),
            "rsi_history_length": len(self._rsi_values),
            "avg_gain": self._avg_gain,
            "avg_loss": self._avg_loss,
            "position_open_bars": self.position_open_bars,
            "position_open_price": self.position_open_price,
            "signal_count": len(self.signals),
            "executed_signal_count": len(self.signal_results),
        }
