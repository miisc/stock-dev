"""
回测结果

存储和计算回测结果，包括绩效指标、交易记录等
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from loguru import logger

from ..trading.signal import Signal


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    # 收益指标
    total_return: float = 0.0  # 总收益率
    annual_return: float = 0.0  # 年化收益率
    benchmark_return: float = 0.0  # 基准收益率
    excess_return: float = 0.0  # 超额收益率
    
    # 风险指标
    max_drawdown: float = 0.0  # 最大回撤
    volatility: float = 0.0  # 波动率
    sharpe_ratio: float = 0.0  # 夏普比率
    calmar_ratio: float = 0.0  # 卡玛比率
    
    # 交易指标
    total_trades: int = 0  # 总交易次数
    win_rate: float = 0.0  # 胜率
    profit_loss_ratio: float = 0.0  # 盈亏比
    avg_trade_return: float = 0.0  # 平均每笔交易收益率
    
    # 其他指标
    beta: float = 0.0  # Beta系数
    alpha: float = 0.0  # Alpha系数
    
    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'benchmark_return': self.benchmark_return,
            'excess_return': self.excess_return,
            'max_drawdown': self.max_drawdown,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'calmar_ratio': self.calmar_ratio,
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_loss_ratio': self.profit_loss_ratio,
            'avg_trade_return': self.avg_trade_return,
            'beta': self.beta,
            'alpha': self.alpha
        }


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_cash: float
    final_value: float
    signals: List[Signal] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    daily_portfolio: List[Dict[str, Any]] = field(default_factory=list)
    benchmark: Optional[str] = None
    
    # 计算属性
    def __post_init__(self):
        """初始化后计算"""
        self.metrics = self._calculate_metrics()
        self.equity_curve = self._calculate_equity_curve()
    
    @property
    def total_return(self) -> float:
        """总收益率"""
        return (self.final_value - self.initial_cash) / self.initial_cash * 100
    
    @property
    def total_days(self) -> int:
        """总天数"""
        return (self.end_date - self.start_date).days
    
    @property
    def annual_return(self) -> float:
        """年化收益率 (复利公式)"""
        trading_days = len(self.daily_portfolio)
        if trading_days < 2:
            return 0.0
        total_ret = self.total_return / 100  # convert from percentage
        return ((1 + total_ret) ** (252.0 / trading_days) - 1) * 100
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """计算绩效指标"""
        try:
            # 基础数据
            total_return = self.total_return
            annual_return = self.annual_return
            
            # 计算每日收益率
            daily_returns = self._calculate_daily_returns()
            
            # 计算风险指标
            volatility = np.std(daily_returns) * np.sqrt(252) * 100 if daily_returns else 0.0
            max_drawdown = self._calculate_max_drawdown()
            
            # 计算夏普比率 (假设无风险利率为2%，参考中国国债)
            risk_free_rate = 0.02
            sharpe_ratio = (annual_return/100 - risk_free_rate) / (volatility/100) if volatility > 0 else 0.0
            
            # 计算卡玛比率
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
            
            # 计算交易指标
            total_trades = len(self.trades)
            win_rate = self._calculate_win_rate()
            profit_loss_ratio = self._calculate_profit_loss_ratio()
            avg_trade_return = self._calculate_avg_trade_return()
            
            # 计算基准收益率和超额收益率
            benchmark_return = self._calculate_benchmark_return()
            excess_return = total_return - benchmark_return
            
            return PerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                benchmark_return=benchmark_return,
                excess_return=excess_return,
                max_drawdown=max_drawdown,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                calmar_ratio=calmar_ratio,
                total_trades=total_trades,
                win_rate=win_rate,
                profit_loss_ratio=profit_loss_ratio,
                avg_trade_return=avg_trade_return
            )
            
        except Exception as e:
            logger.error(f"计算绩效指标失败: {str(e)}")
            return PerformanceMetrics()
    
    def _calculate_daily_returns(self) -> List[float]:
        """计算每日收益率"""
        if not self.daily_portfolio:
            return []
        
        returns = []
        for i in range(1, len(self.daily_portfolio)):
            prev_value = self.daily_portfolio[i-1]['total_value']
            curr_value = self.daily_portfolio[i]['total_value']
            
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                returns.append(daily_return)
        
        return returns
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.daily_portfolio:
            return 0.0
        
        peak = self.daily_portfolio[0]['total_value']
        max_drawdown = 0.0
        
        for item in self.daily_portfolio:
            value = item['total_value']
            
            if value > peak:
                peak = value
            
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_win_rate(self) -> float:
        """计算胜率"""
        if not self.trades:
            return 0.0
        
        profitable_trades = 0
        for trade in self.trades:
            if trade.get('pnl', 0) > 0:
                profitable_trades += 1
        
        return profitable_trades / len(self.trades) * 100
    
    def _calculate_profit_loss_ratio(self) -> float:
        """计算盈亏比"""
        if not self.trades:
            return 0.0
        
        profits = []
        losses = []
        
        for trade in self.trades:
            pnl = trade.get('pnl', 0)
            if pnl > 0:
                profits.append(pnl)
            elif pnl < 0:
                losses.append(abs(pnl))
        
        if not losses:
            return float('inf') if profits else 0.0
        
        avg_profit = np.mean(profits) if profits else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        return avg_profit / avg_loss if avg_loss > 0 else float('inf')
    
    def _calculate_avg_trade_return(self) -> float:
        """计算平均每笔交易收益率"""
        if not self.trades:
            return 0.0
        
        returns = [trade.get('return_pct', 0) for trade in self.trades]
        return np.mean(returns) * 100 if returns else 0.0
    
    def _calculate_benchmark_return(self) -> float:
        """计算基准收益率"""
        # TODO: 实现基准收益率计算
        # 这里需要根据基准代码获取基准数据并计算收益率
        return 0.0
    
    def _calculate_equity_curve(self) -> pd.DataFrame:
        """计算权益曲线"""
        if not self.daily_portfolio:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.daily_portfolio)
        df.set_index('date', inplace=True)
        
        # 计算累计收益率
        df['cumulative_return'] = (df['total_value'] / self.initial_cash - 1) * 100
        
        return df
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'strategy_name': self.strategy_name,
            'symbols': self.symbols,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_cash': self.initial_cash,
            'final_value': self.final_value,
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'total_days': self.total_days,
            'metrics': self.metrics.to_dict(),
            'total_trades': len(self.trades),
            'total_signals': len(self.signals)
        }
    
    def print_summary(self):
        """打印回测摘要"""
        print("\n" + "="*60)
        print(f"回测结果摘要: {self.strategy_name}")
        print("="*60)
        
        print(f"\n回测期间: {self.start_date.strftime('%Y-%m-%d')} 到 {self.end_date.strftime('%Y-%m-%d')}")
        print(f"测试股票: {', '.join(self.symbols)}")
        
        print(f"\n收益指标:")
        print(f"  总收益率: {self.total_return:.2f}%")
        print(f"  年化收益率: {self.annual_return:.2f}%")
        print(f"  基准收益率: {self.metrics.benchmark_return:.2f}%")
        print(f"  超额收益率: {self.metrics.excess_return:.2f}%")
        
        print(f"\n风险指标:")
        print(f"  最大回撤: {self.metrics.max_drawdown:.2f}%")
        print(f"  年化波动率: {self.metrics.volatility:.2f}%")
        print(f"  夏普比率: {self.metrics.sharpe_ratio:.2f}")
        print(f"  卡玛比率: {self.metrics.calmar_ratio:.2f}")
        
        print(f"\n交易指标:")
        print(f"  总交易次数: {self.metrics.total_trades}")
        print(f"  胜率: {self.metrics.win_rate:.2f}%")
        print(f"  盈亏比: {self.metrics.profit_loss_ratio:.2f}")
        print(f"  平均每笔收益率: {self.metrics.avg_trade_return:.2f}%")
        
        print("="*60)