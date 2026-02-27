"""
数据源基类
定义数据获取的标准接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime


class DataSource(ABC):
    """数据源基类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化数据源
        
        Args:
            config: 数据源配置
        """
        self.config = config or {}
    
    @abstractmethod
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        pass
    
    @abstractmethod
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            包含股票代码和名称的DataFrame
        """
        pass
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码格式
        
        Args:
            symbol: 原始股票代码
            
        Returns:
            标准化后的股票代码
        """
        # 确保股票代码格式为 ts_code 格式 (如 000001.SZ)
        if '.' not in symbol:
            if symbol.startswith('6'):
                return f"{symbol}.SH"
            else:
                return f"{symbol}.SZ"
        return symbol
    
    def validate_date_range(self, start_date: str, end_date: str) -> bool:
        """
        验证日期范围是否有效
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            是否有效
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            return start <= end
        except ValueError:
            return False