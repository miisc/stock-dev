"""
交易模块

提供策略框架的核心功能，包括：
- 市场数据结构 (BarData)
- 交易信号结构 (Signal)
- 策略基类 (Strategy)
- 策略配置管理 (StrategyConfigManager)
"""

from .bar_data import BarData, TickData
from .signal import Signal, SignalResult, Direction, SignalType
from .strategy import Strategy, Position, Account
from .strategy_config import (
    StrategyConfig, StrategyParameter, StrategyConfigManager, 
    strategy_config_manager
)
from .strategies import DualMovingAverageStrategy

__all__ = [
    'BarData',
    'TickData',
    'Signal',
    'SignalResult',
    'Direction',
    'SignalType',
    'Strategy',
    'Position',
    'Account',
    'StrategyConfig',
    'StrategyParameter',
    'StrategyConfigManager',
    'strategy_config_manager',
    'DualMovingAverageStrategy'
]