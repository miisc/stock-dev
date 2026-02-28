"""
回测引擎

负责协调整个回测流程，包括数据加载、策略执行、交易模拟等
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
import pandas as pd
from loguru import logger

from ..data.data_query import DataQuery
from ..trading.strategy import Strategy
from ..trading.bar_data import BarData
from ..trading.signal import Signal, Direction
from .executor import ExecutionExecutor
from .position_manager import PositionManager
from .cost_model import CostModel
from .result import BacktestResult


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: datetime
    end_date: datetime
    initial_cash: float = 100000.0
    benchmark: Optional[str] = None  # 基准指数代码
    
    # 回测参数
    commission_rate: float = 0.0003  # 手续费率
    slippage_rate: float = 0.001  # 滑点率
    
    # 输出参数
    output_path: Optional[str] = None
    progress_callback: Optional[Callable[[int, int], None]] = None


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: BacktestConfig):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config
        
        # 初始化组件
        self.data_query = DataQuery(db_path="data/stock_data.db")
        self.executor = ExecutionExecutor(
            commission_rate=config.commission_rate,
            slippage_rate=config.slippage_rate
        )
        self.position_manager = PositionManager()
        self.cost_model = CostModel(
            commission_rate=config.commission_rate,
            slippage_rate=config.slippage_rate
        )
        
        # 回测状态
        self.current_date: Optional[datetime] = None
        self.current_bar: Optional[BarData] = None
        self.total_bars: int = 0
        self.processed_bars: int = 0
        
        # 回测结果
        self.signals: List[Signal] = []
        self.trades: List[Dict[str, Any]] = []
        self.daily_portfolio: List[Dict[str, Any]] = []
        # 待执行订单（当日生成信号，次日开盘执行，避免前视偏差）
        self.pending_orders: List[Signal] = []
        
        logger.info(f"回测引擎初始化完成，时间范围: {config.start_date} 到 {config.end_date}")
    
    def load_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """
        加载回测数据
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            股票数据字典 {symbol: DataFrame}
        """
        logger.info(f"开始加载回测数据，股票数量: {len(symbols)}")
        
        data_dict = {}
        for symbol in symbols:
            try:
                df = self.data_query.get_stock_daily(
                    symbol, 
                    self.config.start_date, 
                    self.config.end_date
                )
                
                if df.empty:
                    logger.warning(f"未获取到股票 {symbol} 的数据")
                    continue
                
                data_dict[symbol] = df
                logger.info(f"加载股票 {symbol} 数据，共 {len(df)} 条记录")
                
            except Exception as e:
                logger.error(f"加载股票 {symbol} 数据失败: {str(e)}")
        
        if not data_dict:
            raise ValueError("未能加载任何有效数据")
        
        # 计算总K线数量
        self.total_bars = min(len(df) for df in data_dict.values())
        logger.info(f"数据加载完成，总K线数: {self.total_bars}")
        
        return data_dict
    
    def run_backtest(self, strategy: Strategy, symbols: List[str]) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy: 交易策略
            symbols: 股票代码列表
            
        Returns:
            回测结果
        """
        logger.info(f"开始运行回测，策略: {strategy.name}，股票: {symbols}")
        
        # 重置状态
        self._reset_state()
        
        # 加载数据
        data_dict = self.load_data(symbols)
        
        # 初始化策略
        strategy.initialize()
        
        # 初始化账户
        self.position_manager.initialize(self.config.initial_cash)
        
        # 获取所有交易日期
        all_dates = set()
        for df in data_dict.values():
            all_dates.update(df.index)
        
        sorted_dates = sorted(all_dates)
        
        # 逐日处理
        for i, date in enumerate(sorted_dates):
            self.current_date = date
            self.processed_bars = i + 1
            
            # 更新进度
            if self.config.progress_callback:
                self.config.progress_callback(i + 1, len(sorted_dates))
            
            # 获取当日所有股票的K线数据，同时收集今日开盘价
            daily_bars = []
            today_open_prices: Dict[str, float] = {}
            for symbol, df in data_dict.items():
                if date in df.index:
                    row = df.loc[date]
                    today_open_prices[symbol] = float(row['open'])
                    bar = BarData(
                        symbol=symbol,
                        datetime=date,
                        open=row['open'],
                        high=row['high'],
                        low=row['low'],
                        close=row['close'],
                        volume=row['volume']
                    )
                    daily_bars.append(bar)
            
            # 执行前一交易日收集的待执行订单（以今日开盘价成交，消除前视偏差）
            self._execute_pending_orders(today_open_prices)
            
            # 更新策略（今日K线数据喂入策略，策略产生信号）
            for bar in daily_bars:
                self.current_bar = bar
                strategy.update_bar(bar)
            
            # 收集今日新信号到 pending_orders，次日开盘执行
            self._collect_signals(strategy)
            
            # 更新每日组合价值（使用今日收盘价）
            self._update_daily_portfolio(date, data_dict)
            
            # 定期输出进度
            if (i + 1) % 100 == 0 or i == len(sorted_dates) - 1:
                logger.info(f"回测进度: {i+1}/{len(sorted_dates)} ({(i+1)/len(sorted_dates)*100:.1f}%)")
        
        # 完成回测
        # strategy.on_backtest_end()  # 暂时注释掉，因为策略基类中没有这个方法
        
        # 生成回测结果
        result = self._generate_result(strategy, symbols)
        
        logger.info(f"回测完成，总收益率: {result.total_return:.2f}%")
        
        return result
    
    def _reset_state(self):
        """重置回测状态"""
        self.current_date = None
        self.current_bar = None
        self.total_bars = 0
        self.processed_bars = 0
        self.signals = []
        self.trades = []
        self.daily_portfolio = []
        self.pending_orders = []
        
        # 重置组件状态
        self.executor.reset()
        self.position_manager.reset()
    
    def _execute_pending_orders(self, open_prices: Dict[str, float]):
        """以今日开盘价执行前一交易日收集的待执行订单（消除前视偏差）"""
        for signal in self.pending_orders:
            open_price = open_prices.get(signal.symbol)
            if open_price is None:
                logger.warning(f"无法获取 {signal.symbol} 今日开盘价，跳过信号执行")
                continue
            trade = self.executor.execute_signal(
                signal,
                self.position_manager,
                open_price
            )
            if trade:
                self.trades.append(trade)
                logger.debug(f"次日开盘执行: {signal.symbol} {signal.direction.value} "
                             f"@ {open_price:.2f} x {signal.volume}")
        self.pending_orders.clear()

    def _collect_signals(self, strategy: Strategy):
        """收集策略今日产生的新信号，存入 pending_orders，次日开盘执行"""
        new_signals = [s for s in strategy.signals if s not in self.signals]
        self.pending_orders.extend(new_signals)
        self.signals.extend(new_signals)
    
    def _update_daily_portfolio(self, date: datetime, data_dict: Dict[str, pd.DataFrame]):
        """更新每日组合价值"""
        # 获取当日收盘价
        prices = {}
        for symbol, df in data_dict.items():
            if date in df.index:
                prices[symbol] = df.loc[date, 'close']
        
        # 计算组合价值
        portfolio_value = self.position_manager.calculate_portfolio_value(prices)
        
        # 保存每日组合状态
        self.daily_portfolio.append({
            'date': date,
            'total_value': portfolio_value,
            'cash': self.position_manager.cash,
            'position_value': portfolio_value - self.position_manager.cash,
            'positions': self.position_manager.get_positions_snapshot()
        })
    
    def _generate_result(self, strategy: Strategy, symbols: List[str]) -> BacktestResult:
        """生成回测结果"""
        return BacktestResult(
            strategy_name=strategy.name,
            symbols=symbols,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_cash=self.config.initial_cash,
            final_value=self.position_manager.total_assets,
            signals=self.signals,
            trades=self.trades,
            daily_portfolio=self.daily_portfolio,
            benchmark=self.config.benchmark
        )