"""
交易成本模型

计算交易成本，包括手续费、滑点等
"""

from typing import Dict, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class CostModel:
    """交易成本模型"""
    commission_rate: float = 0.0003  # 手续费率，默认0.03%
    slippage_rate: float = 0.001  # 滑点率，默认0.1%
    min_commission: float = 5.0  # 最低手续费，默认5元
    
    # 其他费用
    stamp_duty_rate: float = 0.001  # 印花税率，仅卖出时收取，0.1%
    
    def __post_init__(self):
        """初始化后处理"""
        logger.info(f"成本模型初始化完成，手续费率: {self.commission_rate*100:.3f}%，"
                   f"滑点率: {self.slippage_rate*100:.2f}%，最低手续费: {self.min_commission}")
    
    def calculate_commission(self, amount: float, is_sell: bool = False) -> float:
        """
        计算手续费
        
        Args:
            amount: 交易金额
            is_sell: 是否为卖出交易
            
        Returns:
            手续费金额
        """
        # 计算佣金
        commission = max(amount * self.commission_rate, self.min_commission)
        
        # 如果是卖出交易，还需计算印花税
        if is_sell:
            stamp_duty = amount * self.stamp_duty_rate
            commission += stamp_duty
            logger.debug(f"印花税: {stamp_duty:.2f}（税率: {self.stamp_duty_rate*100:.2f}%）")
        
        logger.debug(f"手续费计算: 金额 {amount:.2f}，佣金 {commission:.2f}，"
                   f"佣金率 {self.commission_rate*100:.3f}%")
        
        return commission
    
    def calculate_slippage(self, amount: float) -> float:
        """
        计算滑点成本
        
        Args:
            amount: 交易金额
            
        Returns:
            滑点成本
        """
        slippage = amount * self.slippage_rate
        logger.debug(f"滑点计算: 金额 {amount:.2f}，滑点 {slippage:.2f}，"
                   f"滑点率 {self.slippage_rate*100:.2f}%")
        
        return slippage
    
    def calculate_total_cost(self, amount: float, is_sell: bool = False) -> Dict[str, float]:
        """
        计算总交易成本
        
        Args:
            amount: 交易金额
            is_sell: 是否为卖出交易
            
        Returns:
            成本明细字典
        """
        commission = self.calculate_commission(amount, is_sell)
        slippage = self.calculate_slippage(amount)
        total_cost = commission + slippage
        
        return {
            'commission': commission,
            'slippage': slippage,
            'stamp_duty': amount * self.stamp_duty_rate if is_sell else 0.0,
            'total_cost': total_cost
        }
    
    def update_rates(self, commission_rate: float = None, slippage_rate: float = None):
        """
        更新费率
        
        Args:
            commission_rate: 新的手续费率
            slippage_rate: 新的滑点率
        """
        if commission_rate is not None:
            self.commission_rate = commission_rate
            logger.info(f"手续费率更新为: {commission_rate*100:.3f}%")
        
        if slippage_rate is not None:
            self.slippage_rate = slippage_rate
            logger.info(f"滑点率更新为: {slippage_rate*100:.2f}%")
    
    def get_cost_summary(self, trades: list) -> Dict[str, Any]:
        """
        获取交易成本汇总
        
        Args:
            trades: 交易记录列表
            
        Returns:
            成本汇总字典
        """
        total_commission = 0.0
        total_slippage = 0.0
        total_stamp_duty = 0.0
        total_amount = 0.0
        
        for trade in trades:
            amount = abs(trade.get('volume', 0) * trade.get('price', 0))
            is_sell = trade.get('direction') == 'SELL'
            
            cost_breakdown = self.calculate_total_cost(amount, is_sell)
            
            total_commission += cost_breakdown['commission']
            total_slippage += cost_breakdown['slippage']
            total_stamp_duty += cost_breakdown['stamp_duty']
            total_amount += amount
        
        avg_commission_rate = total_commission / total_amount * 100 if total_amount > 0 else 0
        avg_slippage_rate = total_slippage / total_amount * 100 if total_amount > 0 else 0
        
        return {
            'total_trades': len(trades),
            'total_amount': total_amount,
            'total_commission': total_commission,
            'total_slippage': total_slippage,
            'total_stamp_duty': total_stamp_duty,
            'total_cost': total_commission + total_slippage + total_stamp_duty,
            'avg_commission_rate': avg_commission_rate,
            'avg_slippage_rate': avg_slippage_rate
        }