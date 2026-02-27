"""
市场数据结构
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd


@dataclass
class BarData:
    """
    K线数据结构
    
    包含单个交易周期的完整市场数据
    """
    symbol: str          # 股票代码
    datetime: datetime   # 时间戳
    open: float          # 开盘价
    high: float          # 最高价
    low: float           # 最低价
    close: float         # 收盘价
    volume: int          # 成交量
    turnover: Optional[float] = None  # 成交额
    
    def __post_init__(self):
        """数据验证"""
        if self.high < max(self.open, self.close):
            raise ValueError(f"最高价({self.high})不能小于开盘价({self.open})和收盘价({self.close})中的较大值")
        
        if self.low > min(self.open, self.close):
            raise ValueError(f"最低价({self.low})不能大于开盘价({self.open})和收盘价({self.close})中的较小值")
    
    @property
    def is_up(self) -> bool:
        """是否上涨"""
        return self.close > self.open
    
    @property
    def is_down(self) -> bool:
        """是否下跌"""
        return self.close < self.open
    
    @property
    def price_change(self) -> float:
        """价格变动"""
        return self.close - self.open
    
    @property
    def price_change_pct(self) -> float:
        """价格变动百分比"""
        if self.open == 0:
            return 0
        return (self.close - self.open) / self.open
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'datetime': self.datetime,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'turnover': self.turnover
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BarData':
        """从字典创建实例"""
        return cls(
            symbol=data['symbol'],
            datetime=data['datetime'],
            open=float(data['open']),
            high=float(data['high']),
            low=float(data['low']),
            close=float(data['close']),
            volume=int(data['volume']),
            turnover=float(data.get('turnover', 0)) if data.get('turnover') else None
        )
    
    @classmethod
    def from_dataframe_row(cls, row: pd.Series, symbol: str) -> 'BarData':
        """从DataFrame行创建实例"""
        return cls(
            symbol=symbol,
            datetime=pd.to_datetime(row['trade_date']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=int(row['volume']),
            turnover=float(row['amount']) if 'amount' in row and pd.notna(row['amount']) else None
        )


@dataclass
class TickData:
    """
    逐笔成交数据结构
    
    包含单笔交易的详细信息
    """
    symbol: str          # 股票代码
    datetime: datetime   # 时间戳
    price: float          # 成交价
    volume: int          # 成交量
    direction: str        # 买卖方向 (BUY/SELL)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'datetime': self.datetime,
            'price': self.price,
            'volume': self.volume,
            'direction': self.direction
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TickData':
        """从字典创建实例"""
        return cls(
            symbol=data['symbol'],
            datetime=data['datetime'],
            price=float(data['price']),
            volume=int(data['volume']),
            direction=data['direction']
        )