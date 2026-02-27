"""
回测引擎模块

提供完整的回测功能，包括策略执行、交易模拟、状态管理等
"""

from .backtest_engine import BacktestEngine, BacktestConfig
from .result import BacktestResult
from .executor import ExecutionExecutor
from .position_manager import PositionManager
from .cost_model import CostModel

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "ExecutionExecutor",
    "PositionManager",
    "CostModel"
]