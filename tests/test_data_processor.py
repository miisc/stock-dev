"""
测试数据处理功能
"""

import sys
import os
import pandas as pd
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.data_processor import DataProcessor
from src.data.data_storage import DataStorage
from src.data.data_query import DataQuery
from src.common.config import Config
from loguru import logger


def test_data_processor():
    """测试数据处理器"""
    logger.info("开始测试数据处理器")
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
        'open': [10.0, 10.5, 10.2, 10.8, 11.0],
        'high': [10.5, 10.8, 10.9, 11.2, 11.5],
        'low': [9.8, 10.1, 10.0, 10.5, 10.7],
        'close': [10.2, 10.6, 10.7, 11.0, 11.2],
        'volume': [1000000, 1200000, 900000, 1500000, 1100000],
        'amount': [10200000, 12720000, 9630000, 16500000, 12320000],
        'ts_code': '000001.SZ'
    })
    
    # 添加一些异常值
    test_data.loc[1, 'high'] = 9.0  # high < low
    test_data.loc[2, 'low'] = 11.0  # low > close
    
    logger.info(f"原始测试数据:\n{test_data}")
    
    # 测试数据清洗
    cleaned_data = DataProcessor.clean_data(test_data)
    logger.info(f"清洗后数据:\n{cleaned_data}")
    
    # 测试OHLC一致性验证
    validated_data, correction_count = DataProcessor.validate_ohlc_consistency(cleaned_data)
    logger.info(f"验证后数据，修正了 {correction_count} 条记录:\n{validated_data}")
    
    # 测试完整处理流程
    processed_data = DataProcessor.process_data(test_data)
    logger.info(f"完整处理后数据:\n{processed_data}")
    
    logger.info("数据处理器测试完成")
    return True


def test_data_storage_and_query():
    """测试数据存储和查询"""
    logger.info("开始测试数据存储和查询")
    
    # 创建测试数据库
    test_db_path = "data/test_stock_data.db"
    
    # 初始化存储和查询
    storage = DataStorage(test_db_path)
    query = DataQuery(test_db_path)
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
        'open': [10.0, 10.5, 10.2, 10.8, 11.0],
        'high': [10.5, 10.8, 10.9, 11.2, 11.5],
        'low': [9.8, 10.1, 10.0, 10.5, 10.7],
        'close': [10.2, 10.6, 10.7, 11.0, 11.2],
        'volume': [1000000, 1200000, 900000, 1500000, 1100000],
        'amount': [10200000, 12720000, 9630000, 16500000, 12320000],
        'ts_code': '000001.SZ'
    })
    
    # 测试保存数据
    saved_count = storage.save_stock_daily(test_data)
    logger.info(f"保存了 {saved_count} 条记录")
    
    # 测试查询数据
    queried_data = query.get_stock_daily('000001.SZ')
    logger.info(f"查询到 {len(queried_data)} 条记录:\n{queried_data}")
    
    # 测试按日期范围查询
    range_data = query.get_stock_daily('000001.SZ', '20230102', '20230104')
    logger.info(f"按日期范围查询到 {len(range_data)} 条记录:\n{range_data}")
    
    # 测试获取最新日期
    latest_date = query.get_latest_date('000001.SZ')
    logger.info(f"最新日期: {latest_date}")
    
    # 测试获取最早日期
    earliest_date = query.get_earliest_date('000001.SZ')
    logger.info(f"最早日期: {earliest_date}")
    
    # 测试获取数据记录数
    count = query.get_data_count('000001.SZ')
    logger.info(f"数据记录数: {count}")
    
    logger.info("数据存储和查询测试完成")
    return True


if __name__ == "__main__":
    test_data_processor()
    test_data_storage_and_query()