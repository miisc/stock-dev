"""
analysis 分析模块 — 提供批量回测结果的聚合、排名与导出功能
"""
from .aggregator import ResultAggregator
from .repeatability import RepeatabilityChecker

__all__ = ["ResultAggregator", "RepeatabilityChecker"]
