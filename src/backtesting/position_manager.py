"""
仓位管理器

负责管理交易仓位，包括持仓跟踪、资金管理等
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

from ..trading.bar_data import BarData


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    volume: int = 0  # 持仓数量（正数为多头，负数为空头）
    avg_price: float = 0.0  # 平均成本价
    market_value: float = 0.0  # 市值
    
    def update_market_value(self, price: float):
        """更新市值"""
        self.market_value = abs(self.volume) * price
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'volume': self.volume,
            'avg_price': self.avg_price,
            'market_value': self.market_value
        }


class PositionManager:
    """仓位管理器"""
    
    def __init__(self):
        """初始化仓位管理器"""
        self.positions: Dict[str, Position] = {}
        self.initial_cash: float = 0.0
        self.cash: float = 0.0
        
        logger.info("仓位管理器初始化完成")
    
    def initialize(self, initial_cash: float):
        """
        初始化账户
        
        Args:
            initial_cash: 初始资金
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions = {}
        
        logger.info(f"账户初始化完成，初始资金: {initial_cash:.2f}")
    
    def add_position(self, symbol: str, volume: int, price: float):
        """
        增加持仓
        
        Args:
            symbol: 股票代码
            volume: 增持数量
            price: 成交价格
        """
        if symbol not in self.positions:
            # 新建仓位
            self.positions[symbol] = Position(
                symbol=symbol,
                volume=volume,
                avg_price=price
            )
            logger.debug(f"新建仓位: {symbol} {volume}股 @ {price:.2f}")
        else:
            # 加仓
            position = self.positions[symbol]
            total_amount = abs(position.volume) * position.avg_price + volume * price
            total_volume = abs(position.volume) + volume
            
            position.avg_price = total_amount / total_volume
            position.volume += volume
            
            logger.debug(f"加仓: {symbol} {volume}股 @ {price:.2f}，新均价: {position.avg_price:.2f}")
        
        # 更新市值
        self.positions[symbol].update_market_value(price)
    
    def reduce_position(self, symbol: str, volume: int):
        """
        减少持仓
        
        Args:
            symbol: 股票代码
            volume: 减少数量
        """
        if symbol not in self.positions:
            logger.warning(f"尝试减少不存在的持仓: {symbol}")
            return
        
        position = self.positions[symbol]
        
        if position.volume < volume:
            logger.warning(f"持仓不足，无法减少: {symbol} 持仓{position.volume}，尝试减少{volume}")
            return
        
        position.volume -= volume
        
        # 如果仓位为0，删除持仓记录
        if position.volume == 0:
            del self.positions[symbol]
            logger.debug(f"清仓: {symbol}")
        else:
            logger.debug(f"减仓: {symbol} {volume}股，剩余{position.volume}股")
    
    def get_position(self, symbol: str) -> Position:
        """
        获取持仓信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            持仓信息
        """
        if symbol not in self.positions:
            return Position(symbol=symbol)
        
        return self.positions[symbol]
    
    def update_market_values(self, prices: Dict[str, float]):
        """
        更新所有持仓的市值
        
        Args:
            prices: 价格字典 {symbol: price}
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_market_value(prices[symbol])
    
    def calculate_portfolio_value(self, prices: Dict[str, float]) -> float:
        """
        计算组合总价值
        
        Args:
            prices: 价格字典 {symbol: price}
            
        Returns:
            组合总价值
        """
        # 更新持仓市值
        self.update_market_values(prices)
        
        # 计算持仓总市值
        position_value = sum(pos.market_value for pos in self.positions.values())
        
        # 组合总价值 = 现金 + 持仓市值
        return self.cash + position_value
    
    def get_positions_snapshot(self) -> List[Dict[str, Any]]:
        """获取当前持仓快照"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    @property
    def total_assets(self) -> float:
        """总资产"""
        position_value = sum(pos.market_value for pos in self.positions.values())
        return self.cash + position_value
    
    @property
    def position_value(self) -> float:
        """持仓市值"""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_positions(self) -> int:
        """持仓数量"""
        return len(self.positions)
    
    def reset(self):
        """重置仓位管理器"""
        self.positions = {}
        self.cash = self.initial_cash
        logger.debug("仓位管理器状态已重置")
    
    def print_summary(self):
        """打印持仓摘要"""
        print("\n持仓摘要:")
        print(f"  现金: {self.cash:.2f}")
        print(f"  持仓数量: {self.total_positions}")
        print(f"  持仓市值: {self.position_value:.2f}")
        print(f"  总资产: {self.total_assets:.2f}")
        
        if self.positions:
            print("\n持仓明细:")
            for symbol, position in self.positions.items():
                print(f"  {symbol}: {position.volume}股 @ {position.avg_price:.2f}，市值: {position.market_value:.2f}")