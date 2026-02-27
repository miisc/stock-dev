"""
策略基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import pandas as pd
from loguru import logger

from .bar_data import BarData
from .signal import Signal, SignalResult


@dataclass
class Position:
    """
    持仓信息
    """
    symbol: str          # 股票代码
    volume: int = 0       # 持仓数量
    avg_price: float = 0 # 平均成本价
    market_value: float = 0  # 市值
    last_update: Optional[datetime] = None  # 最后更新时间
    
    @property
    def is_long(self) -> bool:
        """是否多头持仓"""
        return self.volume > 0
    
    @property
    def is_short(self) -> bool:
        """是否空头持仓"""
        return self.volume < 0
    
    @property
    def is_empty(self) -> bool:
        """是否空仓"""
        return self.volume == 0
    
    def update_market_value(self, current_price: float) -> None:
        """更新市值"""
        self.market_value = abs(self.volume) * current_price
        self.last_update = datetime.now()


@dataclass
class Account:
    """
    账户信息
    """
    initial_capital: float = 100000  # 初始资金
    cash: float = 100000            # 可用资金
    positions: Dict[str, Position] = field(default_factory=dict)  # 持仓
    
    @property
    def total_assets(self) -> float:
        """总资产"""
        return self.cash + sum(pos.market_value for pos in self.positions.values())
    
    @property
    def position_value(self) -> float:
        """持仓市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_profit(self) -> float:
        """总盈亏"""
        return self.total_assets - self.initial_capital
    
    @property
    def total_profit_pct(self) -> float:
        """总盈亏百分比"""
        if self.initial_capital == 0:
            return 0
        return self.total_profit / self.initial_capital
    
    def get_position(self, symbol: str) -> Position:
        """获取持仓"""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]
    
    def update_position(self, symbol: str, volume: int, price: float) -> None:
        """更新持仓"""
        position = self.get_position(symbol)
        
        if position.volume == 0:
            # 新建仓位
            position.volume = volume
            position.avg_price = price
        elif (position.volume > 0 and volume > 0) or (position.volume < 0 and volume < 0):
            # 加仓
            total_amount = abs(position.volume) * position.avg_price + abs(volume) * price
            total_volume = abs(position.volume) + abs(volume)
            position.avg_price = total_amount / total_volume
            position.volume += volume
        else:
            # 减仓或反向开仓
            if abs(volume) >= abs(position.volume):
                # 平仓并反向开仓
                remaining_volume = volume + position.volume
                position.volume = remaining_volume
                if remaining_volume != 0:
                    position.avg_price = price
            else:
                # 部分平仓
                position.volume += volume
        
        # 如果持仓为0，清空该持仓
        if position.volume == 0:
            if symbol in self.positions:
                del self.positions[symbol]
        
        position.update_market_value(price)


class Strategy(ABC):
    """
    策略基类
    
    定义了策略的标准接口和通用功能
    """
    
    def __init__(self, strategy_id: str, name: str, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        
        Args:
            strategy_id: 策略唯一标识
            name: 策略名称
            params: 策略参数
        """
        self.strategy_id = strategy_id
        self.name = name
        self.params = params or {}
        
        # 策略状态
        self.account = Account()
        self.signals: List[Signal] = []
        self.signal_results: List[SignalResult] = []
        
        # 数据缓存
        self.bars: Dict[str, List[BarData]] = {}
        
        # 策略状态
        self.inited = False
        self.trading = True
        
        # 日志记录
        self.logger = logger.bind(strategy_id=strategy_id, strategy_name=name)
    
    @abstractmethod
    def on_init(self) -> None:
        """
        策略初始化
        
        在策略开始运行前调用，用于设置策略参数、初始化指标等
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar: BarData) -> None:
        """
        K线数据推送
        
        Args:
            bar: K线数据
        """
        pass
    
    def on_start(self) -> None:
        """
        策略启动
        
        在策略开始交易时调用
        """
        self.trading = True
        self.logger.info("策略启动")
    
    def on_stop(self) -> None:
        """
        策略停止
        
        在策略停止交易时调用
        """
        self.trading = False
        self.logger.info("策略停止")
    
    def update_bar(self, bar: BarData) -> None:
        """
        更新K线数据
        
        Args:
            bar: K线数据
        """
        # 缓存K线数据
        if bar.symbol not in self.bars:
            self.bars[bar.symbol] = []
        self.bars[bar.symbol].append(bar)
        
        # 更新持仓市值
        if bar.symbol in self.account.positions:
            self.account.positions[bar.symbol].update_market_value(bar.close)
        
        # 调用策略的on_bar方法
        if self.inited:
            self.on_bar(bar)
    
    def buy(self, symbol: str, price: float, volume: int, 
            reason: str = "", confidence: float = 1.0) -> Signal:
        """
        生成买入信号
        
        Args:
            symbol: 股票代码
            price: 价格
            volume: 数量
            reason: 原因
            confidence: 置信度
            
        Returns:
            交易信号
        """
        signal = Signal(
            symbol=symbol,
            datetime=datetime.now(),
            direction=Direction.BUY,
            price=price,
            volume=volume,
            reason=reason,
            confidence=confidence,
            strategy_id=self.strategy_id
        )
        
        self.signals.append(signal)
        self.logger.info(f"生成买入信号: {signal}")
        return signal
    
    def sell(self, symbol: str, price: float, volume: int,
             reason: str = "", confidence: float = 1.0) -> Signal:
        """
        生成卖出信号
        
        Args:
            symbol: 股票代码
            price: 价格
            volume: 数量
            reason: 原因
            confidence: 置信度
            
        Returns:
            交易信号
        """
        signal = Signal(
            symbol=symbol,
            datetime=datetime.now(),
            direction=Direction.SELL,
            price=price,
            volume=volume,
            reason=reason,
            confidence=confidence,
            strategy_id=self.strategy_id
        )
        
        self.signals.append(signal)
        self.logger.info(f"生成卖出信号: {signal}")
        return signal
    
    def get_bars(self, symbol: str, count: int = 1) -> List[BarData]:
        """
        获取K线数据
        
        Args:
            symbol: 股票代码
            count: 数据数量
            
        Returns:
            K线数据列表
        """
        if symbol not in self.bars:
            return []
        
        return self.bars[symbol][-count:]
    
    def get_latest_bar(self, symbol: str) -> Optional[BarData]:
        """
        获取最新K线数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            最新K线数据
        """
        bars = self.get_bars(symbol, 1)
        return bars[0] if bars else None
    
    def get_position(self, symbol: str) -> Position:
        """
        获取持仓
        
        Args:
            symbol: 股票代码
            
        Returns:
            持仓信息
        """
        return self.account.get_position(symbol)
    
    def set_parameter(self, name: str, value: Any) -> None:
        """
        设置策略参数
        
        Args:
            name: 参数名
            value: 参数值
        """
        self.params[name] = value
        self.logger.debug(f"设置参数 {name} = {value}")
    
    def get_parameter(self, name: str, default: Any = None) -> Any:
        """
        获取策略参数
        
        Args:
            name: 参数名
            default: 默认值
            
        Returns:
            参数值
        """
        return self.params.get(name, default)
    
    def execute_signal(self, signal: Signal, execution_price: float, 
                       execution_volume: int) -> SignalResult:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            execution_price: 执行价格
            execution_volume: 执行数量
            
        Returns:
            信号执行结果
        """
        result = SignalResult(
            signal=signal,
            executed=True,
            execution_price=execution_price,
            execution_volume=execution_volume,
            execution_time=datetime.now()
        )
        
        # 更新账户
        if signal.is_buy:
            cost = execution_price * execution_volume
            self.account.cash -= cost
            self.account.update_position(signal.symbol, execution_volume, execution_price)
        elif signal.is_sell:
            income = execution_price * execution_volume
            self.account.cash += income
            self.account.update_position(signal.symbol, -execution_volume, execution_price)
        
        self.signal_results.append(result)
        self.logger.info(f"执行信号: {signal}, 价格: {execution_price}, 数量: {execution_volume}")
        
        return result
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        获取策略绩效摘要
        
        Returns:
            绩效摘要
        """
        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.name,
            'total_assets': self.account.total_assets,
            'total_profit': self.account.total_profit,
            'total_profit_pct': self.account.total_profit_pct,
            'cash': self.account.cash,
            'position_value': self.account.position_value,
            'signal_count': len(self.signals),
            'executed_signal_count': len(self.signal_results)
        }
    
    def initialize(self) -> None:
        """
        初始化策略
        
        调用策略的on_init方法
        """
        self.logger.info("初始化策略")
        self.on_init()
        self.inited = True
        self.logger.info("策略初始化完成")
    
    def set_parameters(self, params: Dict[str, Any]):
        """
        设置策略参数
        
        Args:
            params: 参数字典
        """
        for name, value in params.items():
            if hasattr(self, name):
                setattr(self, name, value)
                self.logger.debug(f"设置参数 {name} = {value}")
            else:
                self.logger.warning(f"未知参数: {name}")


# 导入Direction枚举
from .signal import Direction