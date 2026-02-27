"""
数据获取器
整合数据获取、处理和存储功能
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

from .akshare_source import AKShareSource
from .data_processor import DataProcessor
from .data_storage import DataStorage
from .data_query import DataQuery
from ..common.config import Config


class DataFetcher:
    """数据获取器类"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化数据获取器
        
        Args:
            config: 配置对象
        """
        self.config = config or Config()
        
        # 获取配置
        db_path = self.config.get('database.path', 'data/stock_data.db')
        data_source_config = self.config.get('data_source', {})
        
        # 初始化组件
        self.data_source = AKShareSource(data_source_config)
        self.data_processor = DataProcessor()
        self.data_storage = DataStorage(db_path)
        self.data_query = DataQuery(db_path)
        
        logger.info("数据获取器初始化完成")
    
    def fetch_and_store_data(self, symbol: str, days: int = 5 * 365) -> bool:
        """
        获取并存储股票数据
        
        Args:
            symbol: 股票代码
            days: 获取天数，默认5年
            
        Returns:
            是否成功
        """
        try:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            logger.info(f"开始获取股票 {symbol} 从 {start_date_str} 到 {end_date_str} 的数据")
            
            # 获取原始数据
            raw_data = self.data_source.get_stock_daily(symbol, start_date_str, end_date_str)
            
            if raw_data.empty:
                logger.error(f"未获取到股票 {symbol} 的数据")
                return False
            
            # 处理数据
            processed_data = self.data_processor.process_data(raw_data)
            
            if processed_data.empty:
                logger.error(f"数据处理后为空")
                return False
            
            # 存储数据
            saved_count = self.data_storage.save_stock_daily(processed_data)
            
            if saved_count > 0:
                logger.info(f"成功获取并存储股票 {symbol} 的数据，共 {saved_count} 条记录")
                return True
            else:
                logger.warning(f"股票 {symbol} 的数据可能已存在，未新增记录")
                return True
                
        except Exception as e:
            logger.error(f"获取并存储股票 {symbol} 数据失败: {str(e)}")
            return False
    
    def fetch_and_store_stock_list(self) -> bool:
        """
        获取并存储股票列表
        
        Returns:
            是否成功
        """
        try:
            logger.info("开始获取股票列表")
            
            # 获取股票列表
            stock_list = self.data_source.get_stock_list()
            
            if stock_list.empty:
                logger.error("未获取到股票列表")
                return False
            
            # 存储股票列表
            saved_count = self.data_storage.save_stock_list(stock_list)
            
            if saved_count > 0:
                logger.info(f"成功获取并存储股票列表，共 {saved_count} 只股票")
                return True
            else:
                logger.error("存储股票列表失败")
                return False
                
        except Exception as e:
            logger.error(f"获取并存储股票列表失败: {str(e)}")
            return False
    
    def update_data(self, symbol: str, force_update: bool = False) -> bool:
        """
        更新股票数据
        
        Args:
            symbol: 股票代码
            force_update: 是否强制更新
            
        Returns:
            是否成功
        """
        try:
            # 获取最新数据日期
            latest_date = self.data_query.get_latest_date(symbol)
            
            if latest_date and not force_update:
                # 从最新日期的下一天开始更新
                latest_dt = datetime.strptime(latest_date, '%Y%m%d')
                start_date = latest_dt + timedelta(days=1)
                start_date_str = start_date.strftime('%Y-%m-%d')
                
                # 如果最新数据是今天，不需要更新
                if start_date.date() >= datetime.now().date():
                    logger.info(f"股票 {symbol} 数据已是最新，无需更新")
                    return True
            else:
                # 强制更新或没有历史数据，获取最近5年数据
                start_date = datetime.now() - timedelta(days=5 * 365)
                start_date_str = start_date.strftime('%Y-%m-%d')
            
            end_date_str = datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"开始更新股票 {symbol} 从 {start_date_str} 到 {end_date_str} 的数据")
            
            # 获取原始数据
            raw_data = self.data_source.get_stock_daily(symbol, start_date_str, end_date_str)
            
            if raw_data.empty:
                logger.warning(f"未获取到股票 {symbol} 的新数据")
                return True  # 没有新数据也算成功
            
            # 处理数据
            processed_data = self.data_processor.process_data(raw_data)
            
            if processed_data.empty:
                logger.error(f"数据处理后为空")
                return False
            
            # 存储数据
            saved_count = self.data_storage.save_stock_daily(processed_data)
            
            if saved_count > 0:
                logger.info(f"成功更新股票 {symbol} 的数据，新增 {saved_count} 条记录")
                return True
            else:
                logger.warning(f"股票 {symbol} 没有新数据需要更新")
                return True
                
        except Exception as e:
            logger.error(f"更新股票 {symbol} 数据失败: {str(e)}")
            return False
    
    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            股票数据DataFrame
        """
        # 标准化股票代码
        ts_code = self.data_source.normalize_symbol(symbol)
        return self.data_query.get_stock_daily(ts_code, start_date, end_date)
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            股票列表DataFrame
        """
        return self.data_query.get_stock_list()
    
    def search_stocks(self, keyword: str) -> pd.DataFrame:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的股票列表DataFrame
        """
        return self.data_query.search_stocks(keyword)
    
    def get_stock_summary(self) -> pd.DataFrame:
        """
        获取所有股票的数据摘要
        
        Returns:
            股票数据摘要DataFrame
        """
        return self.data_query.get_stock_summary()
    
    def batch_fetch_data(self, symbols: list, days: int = 5 * 365) -> Dict[str, bool]:
        """
        批量获取股票数据
        
        Args:
            symbols: 股票代码列表
            days: 获取天数，默认5年
            
        Returns:
            获取结果字典 {股票代码: 是否成功}
        """
        results = {}
        
        for symbol in symbols:
            logger.info(f"正在获取股票 {symbol} 的数据...")
            success = self.fetch_and_store_data(symbol, days)
            results[symbol] = success
            
            # 添加延迟，避免请求过于频繁
            import time
            time.sleep(1)
        
        success_count = sum(results.values())
        total_count = len(symbols)
        
        logger.info(f"批量获取完成，成功 {success_count}/{total_count} 只股票")
        
        return results