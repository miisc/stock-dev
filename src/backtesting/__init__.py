"""
回测系统模块
提供策略回测功能
"""

from .engine import BacktestEngine
from .strategies import Strategy, DualMAStrategy, BollingerBandsStrategy, RSIStrategy

__all__ = [
    "BacktestEngine",
    "Strategy",
    "DualMAStrategy",
    "BollingerBandsStrategy",
    "RSIStrategy"
]