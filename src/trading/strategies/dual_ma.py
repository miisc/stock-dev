"""
双均线策略实现

基于移动平均线的经典趋势跟踪策略：
- 短期均线上穿长期均线时买入（金叉）
- 短期均线下穿长期均线时卖出（死叉）
"""

import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.trading import Strategy, BarData, Signal, Direction


class DualMovingAverageStrategy(Strategy):
    """
    双均线策略
    
    使用短期和长期移动平均线的交叉来产生交易信号
    """
    
    def __init__(self, strategy_id: str = "dual_ma", name: str = "双均线策略", 
                 params: Optional[dict] = None):
        """
        初始化双均线策略
        
        Args:
            strategy_id: 策略唯一标识
            name: 策略名称
            params: 策略参数
        """
        # 默认参数
        default_params = {
            "short_window": 5,      # 短期均线窗口
            "long_window": 20,      # 长期均线窗口
            "position_size": 100,   # 每次交易数量
            "min_hold_bars": 3,     # 最少持仓K线数
            "signal_threshold": 0.01,  # 信号确认阈值
            "stop_loss_pct": 0.05,  # 止损百分比
            "take_profit_pct": 0.10, # 止盈百分比
        }
        
        if params:
            default_params.update(params)
        
        super().__init__(strategy_id, name, default_params)
        
        # 策略内部状态
        self.short_ma_values: List[float] = []
        self.long_ma_values: List[float] = []
        self.position_open_bars: int = 0  # 持仓K线数
        self.position_open_price: float = 0  # 开仓价格
        
        self.logger.info(f"双均线策略初始化完成，参数: {self.params}")
    
    def on_init(self):
        """策略初始化"""
        # 验证参数
        short_window = self.get_parameter("short_window")
        long_window = self.get_parameter("long_window")
        
        if short_window >= long_window:
            raise ValueError(f"短期均线窗口({short_window})必须小于长期均线窗口({long_window})")
        
        if short_window < 1 or long_window < 1:
            raise ValueError("均线窗口必须大于0")
        
        self.logger.info(f"双均线策略参数验证通过: 短期={short_window}, 长期={long_window}")
    
    def on_bar(self, bar: BarData):
        """
        K线数据处理
        
        Args:
            bar: K线数据
        """
        # 更新K线数据
        symbol = bar.symbol
        bars = self.get_bars(symbol, max(self.get_parameter("long_window") + 1, 2))
        
        if len(bars) < self.get_parameter("long_window"):
            # 数据不足，无法计算均线
            return
        
        # 计算移动平均线
        close_prices = [b.close for b in bars]
        short_ma = self._calculate_ma(close_prices, self.get_parameter("short_window"))
        long_ma = self._calculate_ma(close_prices, self.get_parameter("long_window"))
        
        # 保存均线值
        self.short_ma_values.append(short_ma)
        self.long_ma_values.append(long_ma)
        
        # 获取当前持仓
        position = self.get_position(symbol)
        
        # 检查止损止盈
        if position.is_long:
            if self._check_stop_loss(bar, position):
                return
            if self._check_take_profit(bar, position):
                return
            
            self.position_open_bars += 1
        
        # 生成交易信号
        if len(self.short_ma_values) >= 2 and len(self.long_ma_values) >= 2:
            # 检查金叉（买入信号）
            if (self.short_ma_values[-2] <= self.long_ma_values[-2] and 
                self.short_ma_values[-1] > self.long_ma_values[-1]):
                
                # 确认信号强度
                ma_diff = (self.short_ma_values[-1] - self.long_ma_values[-1]) / self.long_ma_values[-1]
                if ma_diff > self.get_parameter("signal_threshold"):
                    self._generate_buy_signal(bar, "金叉买入信号")
            
            # 检查死叉（卖出信号）
            elif (self.short_ma_values[-2] >= self.long_ma_values[-2] and 
                  self.short_ma_values[-1] < self.long_ma_values[-1]):
                
                # 确认信号强度
                ma_diff = (self.long_ma_values[-1] - self.short_ma_values[-1]) / self.long_ma_values[-1]
                if ma_diff > self.get_parameter("signal_threshold"):
                    self._generate_sell_signal(bar, "死叉卖出信号")
    
    def _calculate_ma(self, prices: List[float], window: int) -> float:
        """
        计算移动平均线
        
        Args:
            prices: 价格列表
            window: 窗口大小
            
        Returns:
            移动平均值
        """
        if len(prices) < window:
            return 0.0
        
        return sum(prices[-window:]) / window
    
    def _generate_buy_signal(self, bar: BarData, reason: str):
        """
        生成买入信号
        
        Args:
            bar: K线数据
            reason: 信号原因
        """
        position = self.get_position(bar.symbol)
        
        # 检查是否已有持仓
        if position.is_long:
            return
        
        # 检查最小持仓时间
        if self.position_open_bars < self.get_parameter("min_hold_bars"):
            return
        
        # 生成买入信号
        volume = self.get_parameter("position_size")
        confidence = self._calculate_signal_confidence(bar, Direction.BUY)
        
        signal = self.buy(
            symbol=bar.symbol,
            price=bar.close,
            volume=volume,
            reason=reason,
            confidence=confidence
        )
        
        # 更新持仓状态
        self.position_open_bars = 0
        self.position_open_price = bar.close
        
        self.logger.info(f"生成买入信号: {signal}, 原因: {reason}")
    
    def _generate_sell_signal(self, bar: BarData, reason: str):
        """
        生成卖出信号
        
        Args:
            bar: K线数据
            reason: 信号原因
        """
        position = self.get_position(bar.symbol)
        
        # 检查是否有持仓
        if not position.is_long:
            return
        
        # 生成卖出信号
        volume = position.volume
        confidence = self._calculate_signal_confidence(bar, Direction.SELL)
        
        signal = self.sell(
            symbol=bar.symbol,
            price=bar.close,
            volume=volume,
            reason=reason,
            confidence=confidence
        )
        
        # 重置持仓状态
        self.position_open_bars = 0
        self.position_open_price = 0
        
        self.logger.info(f"生成卖出信号: {signal}, 原因: {reason}")
    
    def _check_stop_loss(self, bar: BarData, position) -> bool:
        """
        检查止损
        
        Args:
            bar: K线数据
            position: 持仓信息
            
        Returns:
            是否触发止损
        """
        if self.position_open_price <= 0:
            return False
        
        # 计算当前盈亏百分比
        pnl_pct = (bar.close - self.position_open_price) / self.position_open_price
        
        # 检查是否触发止损
        if pnl_pct <= -self.get_parameter("stop_loss_pct"):
            self._generate_sell_signal(bar, f"止损卖出，亏损{pnl_pct:.2%}")
            return True
        
        return False
    
    def _check_take_profit(self, bar: BarData, position) -> bool:
        """
        检查止盈
        
        Args:
            bar: K线数据
            position: 持仓信息
            
        Returns:
            是否触发止盈
        """
        if self.position_open_price <= 0:
            return False
        
        # 计算当前盈亏百分比
        pnl_pct = (bar.close - self.position_open_price) / self.position_open_price
        
        # 检查是否触发止盈
        if pnl_pct >= self.get_parameter("take_profit_pct"):
            self._generate_sell_signal(bar, f"止盈卖出，盈利{pnl_pct:.2%}")
            return True
        
        return False
    
    def _calculate_signal_confidence(self, bar: BarData, direction: Direction) -> float:
        """
        计算信号置信度
        
        Args:
            bar: K线数据
            direction: 交易方向
            
        Returns:
            信号置信度 (0-1)
        """
        if len(self.short_ma_values) < 2 or len(self.long_ma_values) < 2:
            return 0.5
        
        # 计算均线差值百分比
        ma_diff = abs(self.short_ma_values[-1] - self.long_ma_values[-1]) / self.long_ma_values[-1]
        
        # 基础置信度
        base_confidence = min(ma_diff * 10, 0.8)  # 限制最大基础置信度为0.8
        
        # 根据趋势强度调整
        if direction == Direction.BUY:
            # 买入信号：上涨趋势增强置信度
            trend_strength = (bar.close - bar.open) / bar.open
            confidence = base_confidence + max(trend_strength * 2, 0)
        else:
            # 卖出信号：下跌趋势增强置信度
            trend_strength = (bar.open - bar.close) / bar.open
            confidence = base_confidence + max(trend_strength * 2, 0)
        
        # 限制置信度范围
        return min(max(confidence, 0.1), 1.0)
    
    def get_strategy_status(self) -> dict:
        """
        获取策略状态
        
        Returns:
            策略状态信息
        """
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.name,
            "parameters": self.params,
            "current_short_ma": self.short_ma_values[-1] if self.short_ma_values else None,
            "current_long_ma": self.long_ma_values[-1] if self.long_ma_values else None,
            "position_open_bars": self.position_open_bars,
            "position_open_price": self.position_open_price,
            "signal_count": len(self.signals),
            "executed_signal_count": len(self.signal_results)
        }