"""
交易信号结构
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class Direction(Enum):
    """交易方向枚举"""
    BUY = "BUY"      # 买入
    SELL = "SELL"    # 卖出
    HOLD = "HOLD"    # 持有
    
    @classmethod
    def from_str(cls, value: str) -> 'Direction':
        """从字符串创建方向"""
        value = value.upper()
        if value == "BUY":
            return cls.BUY
        elif value == "SELL":
            return cls.SELL
        elif value == "HOLD":
            return cls.HOLD
        else:
            raise ValueError(f"无效的交易方向: {value}")


class SignalType(Enum):
    """信号类型枚举"""
    NORMAL = "NORMAL"          # 普通信号
    STOP_LOSS = "STOP_LOSS"    # 止损信号
    TAKE_PROFIT = "TAKE_PROFIT" # 止盈信号
    FORCE_CLOSE = "FORCE_CLOSE" # 强制平仓
    
    @classmethod
    def from_str(cls, value: str) -> 'SignalType':
        """从字符串创建信号类型"""
        value = value.upper()
        if value == "NORMAL":
            return cls.NORMAL
        elif value == "STOP_LOSS":
            return cls.STOP_LOSS
        elif value == "TAKE_PROFIT":
            return cls.TAKE_PROFIT
        elif value == "FORCE_CLOSE":
            return cls.FORCE_CLOSE
        else:
            raise ValueError(f"无效的信号类型: {value}")


@dataclass
class Signal:
    """
    交易信号结构
    
    包含策略生成的交易信号信息
    """
    symbol: str          # 股票代码
    datetime: datetime   # 信号生成时间
    direction: Direction  # 交易方向
    price: float         # 建议价格
    volume: int          # 建议数量
    signal_type: SignalType = SignalType.NORMAL  # 信号类型
    confidence: float = 1.0  # 信号置信度 (0-1)
    reason: str = ""     # 信号原因说明
    strategy_id: str = ""  # 策略ID
    metadata: Optional[Dict[str, Any]] = None  # 额外元数据
    
    def __post_init__(self):
        """数据验证"""
        if self.price <= 0:
            raise ValueError(f"价格必须大于0，当前值: {self.price}")
        
        if self.volume <= 0:
            raise ValueError(f"数量必须大于0，当前值: {self.volume}")
        
        if not (0 <= self.confidence <= 1):
            raise ValueError(f"置信度必须在0-1之间，当前值: {self.confidence}")
        
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_buy(self) -> bool:
        """是否为买入信号"""
        return self.direction == Direction.BUY
    
    @property
    def is_sell(self) -> bool:
        """是否为卖出信号"""
        return self.direction == Direction.SELL
    
    @property
    def is_hold(self) -> bool:
        """是否为持有信号"""
        return self.direction == Direction.HOLD
    
    @property
    def is_stop_loss(self) -> bool:
        """是否为止损信号"""
        return self.signal_type == SignalType.STOP_LOSS
    
    @property
    def is_take_profit(self) -> bool:
        """是否为止盈信号"""
        return self.signal_type == SignalType.TAKE_PROFIT
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'datetime': self.datetime,
            'direction': self.direction.value,
            'price': self.price,
            'volume': self.volume,
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'reason': self.reason,
            'strategy_id': self.strategy_id,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """从字典创建实例"""
        return cls(
            symbol=data['symbol'],
            datetime=data['datetime'],
            direction=Direction.from_str(data['direction']),
            price=float(data['price']),
            volume=int(data['volume']),
            signal_type=SignalType.from_str(data.get('signal_type', 'NORMAL')),
            confidence=float(data.get('confidence', 1.0)),
            reason=data.get('reason', ''),
            strategy_id=data.get('strategy_id', ''),
            metadata=data.get('metadata', {})
        )
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"Signal({self.symbol}, {self.direction.value}, "
                f"price={self.price}, volume={self.volume}, "
                f"type={self.signal_type.value}, confidence={self.confidence})")


@dataclass
class SignalResult:
    """
    信号执行结果
    
    包含信号执行后的结果信息
    """
    signal: Signal                # 原始信号
    executed: bool                # 是否执行
    execution_price: Optional[float] = None  # 执行价格
    execution_volume: Optional[int] = None  # 执行数量
    execution_time: Optional[datetime] = None  # 执行时间
    error_message: str = ""       # 错误信息
    
    @property
    def is_executed(self) -> bool:
        """是否已执行"""
        return self.executed
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'signal': self.signal.to_dict(),
            'executed': self.executed,
            'execution_price': self.execution_price,
            'execution_volume': self.execution_volume,
            'execution_time': self.execution_time,
            'error_message': self.error_message
        }