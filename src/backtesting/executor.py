"""
交易执行器

负责执行交易信号，模拟交易过程，计算交易成本
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from ..trading.signal import Signal, Direction
from ..trading.bar_data import BarData
from .position_manager import PositionManager
from .cost_model import CostModel


@dataclass
class TradeRecord:
    """交易记录"""
    symbol: str
    direction: Direction
    volume: int
    price: float
    datetime: datetime
    commission: float
    slippage: float
    total_cost: float
    pnl: float = 0.0
    return_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'direction': self.direction.value,
            'volume': self.volume,
            'price': self.price,
            'datetime': self.datetime,
            'commission': self.commission,
            'slippage': self.slippage,
            'total_cost': self.total_cost,
            'pnl': self.pnl,
            'return_pct': self.return_pct
        }


class ExecutionExecutor:
    """交易执行器"""
    
    def __init__(self, commission_rate: float = 0.0003, slippage_rate: float = 0.001):
        """
        初始化交易执行器
        
        Args:
            commission_rate: 手续费率，默认0.03%
            slippage_rate: 滑点率，默认0.1%
        """
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.cost_model = CostModel(commission_rate, slippage_rate)
        
        # 执行状态
        self.trades: List[TradeRecord] = []
        self.pending_orders: List[Signal] = []
        
        logger.info(f"交易执行器初始化完成，手续费率: {commission_rate*100:.3f}%，滑点率: {slippage_rate*100:.2f}%")
    
    def execute_signal(self, signal: Signal, position_manager: PositionManager, market_price: float) -> Optional[Dict[str, Any]]:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
            position_manager: 仓位管理器
            market_price: 市场价格
            
        Returns:
            交易记录字典，如果无法执行则返回None
        """
        try:
            # 验证信号
            if not self._validate_signal(signal, position_manager):
                logger.debug(f"信号验证失败，跳过执行: {signal.symbol} {signal.direction.value}")
                return None
            
            # 计算执行价格（考虑滑点）
            execution_price = self._calculate_execution_price(signal, market_price)
            
            # 计算交易成本
            is_sell = signal.direction == Direction.SELL
            commission = self.cost_model.calculate_commission(signal.volume * execution_price, is_sell=is_sell)
            slippage = self.cost_model.calculate_slippage(signal.volume * execution_price)
            total_cost = commission + slippage
            
            # 执行交易
            if signal.direction == Direction.BUY:
                # 买入
                if position_manager.cash < signal.volume * execution_price + total_cost:
                    logger.debug(f"资金不足，无法执行买入信号: {signal.symbol}")
                    return None
                
                # 更新仓位
                position_manager.add_position(signal.symbol, signal.volume, execution_price)
                
                # 扣除成本
                position_manager.cash -= signal.volume * execution_price + total_cost
                
                logger.debug(f"执行买入: {signal.symbol} {signal.volume}股 @ {execution_price:.2f}")
                
            elif signal.direction == Direction.SELL:
                # 卖出
                current_position = position_manager.get_position(signal.symbol)
                if current_position.volume < abs(signal.volume):
                    logger.debug(f"持仓不足，无法执行卖出信号: {signal.symbol}")
                    return None
                
                # 计算盈亏
                avg_price = current_position.avg_price
                pnl = (execution_price - avg_price) * abs(signal.volume) - total_cost
                return_pct = (execution_price - avg_price) / avg_price * 100
                
                # 更新仓位
                position_manager.reduce_position(signal.symbol, abs(signal.volume))
                
                # 增加现金
                position_manager.cash += abs(signal.volume) * execution_price - total_cost
                
                logger.debug(f"执行卖出: {signal.symbol} {abs(signal.volume)}股 @ {execution_price:.2f}，盈亏: {pnl:.2f}")
            
            # 创建交易记录
            trade = TradeRecord(
                symbol=signal.symbol,
                direction=signal.direction,
                volume=signal.volume,
                price=execution_price,
                datetime=signal.datetime,
                commission=commission,
                slippage=slippage,
                total_cost=total_cost,
                pnl=pnl if signal.direction == Direction.SELL else 0.0,
                return_pct=return_pct if signal.direction == Direction.SELL else 0.0
            )
            
            self.trades.append(trade)
            
            return trade.to_dict()
            
        except Exception as e:
            logger.error(f"执行交易信号失败: {str(e)}")
            return None
    
    def _validate_signal(self, signal: Signal, position_manager: PositionManager) -> bool:
        """
        验证交易信号
        
        Args:
            signal: 交易信号
            position_manager: 仓位管理器
            
        Returns:
            是否有效
        """
        # 检查信号基本属性
        if not signal.symbol or signal.volume <= 0:
            return False
        
        # 检查买入信号的资金充足性
        if signal.direction == Direction.BUY:
            # 这里只能做简单检查，因为不知道市场价格
            # 实际的资金检查在execute_signal中进行
            return True
        
        # 检查卖出信号的持仓充足性
        elif signal.direction == Direction.SELL:
            position = position_manager.get_position(signal.symbol)
            return position.volume >= abs(signal.volume)
        
        return False
    
    def _calculate_execution_price(self, signal: Signal, market_price: float) -> float:
        """
        计算执行价格（考虑滑点）
        
        Args:
            signal: 交易信号
            market_price: 市场价格
            
        Returns:
            执行价格
        """
        # 买入时价格向上滑，卖出时价格向下滑
        if signal.direction == Direction.BUY:
            slippage = market_price * self.slippage_rate
            return market_price + slippage
        else:  # SELL
            slippage = market_price * self.slippage_rate
            return market_price - slippage
    
    def reset(self):
        """重置执行器状态"""
        self.trades = []
        self.pending_orders = []
        logger.debug("交易执行器状态已重置")
    
    def get_trade_history(self) -> List[Dict[str, Any]]:
        """获取交易历史"""
        return [trade.to_dict() for trade in self.trades]
    
    def get_total_commission(self) -> float:
        """获取总手续费"""
        return sum(trade.commission for trade in self.trades)
    
    def get_total_slippage(self) -> float:
        """获取总滑点"""
        return sum(trade.slippage for trade in self.trades)
    
    def get_total_cost(self) -> float:
        """获取总交易成本"""
        return sum(trade.total_cost for trade in self.trades)