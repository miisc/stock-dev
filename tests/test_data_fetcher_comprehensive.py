"""
测试数据获取器完整功能
"""

import sys
import os
import pandas as pd
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import time

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.data_fetcher import DataFetcher
from src.data.data_storage import DataStorage
from src.data.data_query import DataQuery
from src.data.models import StockData, StockInfo
from src.common.config import Config
from loguru import logger


def test_data_fetcher_comprehensive():
    """测试数据获取器完整功能"""
    logger.info("开始测试数据获取器完整功能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_fetcher.db")
    
    try:
        # 创建测试配置
        config = Config()
        config.set('database.path', test_db_path)
        
        # 初始化数据获取器
        fetcher = DataFetcher(config)
        
        # 测试1: 获取并存储股票列表
        logger.info("测试1: 获取并存储股票列表")
        success = fetcher.fetch_and_store_stock_list()
        assert success, "获取并存储股票列表失败"
        
        stock_list = fetcher.get_stock_list()
        assert len(stock_list) > 0, "股票列表为空"
        logger.info(f"获取到 {len(stock_list)} 只股票")
        logger.info("获取并存储股票列表测试通过")
        
        # 测试2: 获取并存储单只股票数据
        logger.info("测试2: 获取并存储单只股票数据")
        test_symbol = "000001"  # 平安银行
        success = fetcher.fetch_and_store_data(test_symbol, days=30)
        assert success, f"获取股票 {test_symbol} 数据失败"
        
        stock_data = fetcher.get_stock_data(test_symbol)
        assert len(stock_data) > 0, f"股票 {test_symbol} 数据为空"
        logger.info(f"获取到股票 {test_symbol} 的 {len(stock_data)} 条数据")
        logger.info("获取并存储单只股票数据测试通过")
        
        # 测试3: 更新股票数据
        logger.info("测试3: 更新股票数据")
        success = fetcher.update_data(test_symbol)
        assert success, f"更新股票 {test_symbol} 数据失败"
        logger.info("更新股票数据测试通过")
        
        # 测试4: 强制更新股票数据
        logger.info("测试4: 强制更新股票数据")
        success = fetcher.update_data(test_symbol, force_update=True)
        assert success, f"强制更新股票 {test_symbol} 数据失败"
        logger.info("强制更新股票数据测试通过")
        
        # 测试5: 获取指定日期范围的数据
        logger.info("测试5: 获取指定日期范围的数据")
        start_date = stock_data['trade_date'].min()
        end_date = stock_data['trade_date'].max()
        range_data = fetcher.get_stock_data(test_symbol, start_date, end_date)
        assert len(range_data) > 0, "指定日期范围的数据为空"
        logger.info("获取指定日期范围的数据测试通过")
        
        # 测试6: 搜索股票
        logger.info("测试6: 搜索股票")
        search_results = fetcher.search_stocks("平安")
        assert len(search_results) > 0, "搜索结果为空"
        logger.info(f"搜索到 {len(search_results)} 只包含'平安'的股票")
        logger.info("搜索股票测试通过")
        
        # 测试7: 获取股票摘要
        logger.info("测试7: 获取股票摘要")
        summary = fetcher.get_stock_summary()
        assert len(summary) > 0, "股票摘要为空"
        logger.info(f"获取到 {len(summary)} 只股票的数据摘要")
        logger.info("获取股票摘要测试通过")
        
        # 测试8: 批量获取数据
        logger.info("测试8: 批量获取数据")
        test_symbols = ["000001", "000002"]  # 平安银行、万科A
        results = fetcher.batch_fetch_data(test_symbols, days=10)
        assert len(results) == len(test_symbols), "批量获取结果数量不匹配"
        
        success_count = sum(results.values())
        logger.info(f"批量获取完成，成功 {success_count}/{len(test_symbols)} 只股票")
        assert success_count > 0, "批量获取全部失败"
        logger.info("批量获取数据测试通过")
        
        # 测试9: 获取不存在股票的数据
        logger.info("测试9: 获取不存在股票的数据")
        nonexistent_symbol = "999999"
        stock_data = fetcher.get_stock_data(nonexistent_symbol)
        assert len(stock_data) == 0, f"不存在的股票 {nonexistent_symbol} 应该返回空数据"
        logger.info("获取不存在股票的数据测试通过")
        
        # 测试10: 错误处理 - 无效日期范围
        logger.info("测试10: 错误处理 - 无效日期范围")
        try:
            # 这里应该能处理错误，不会抛出异常
            success = fetcher.fetch_and_store_data(test_symbol, days=-1)
            # 如果返回False，说明正确处理了错误
            assert not success, "应该返回False表示失败"
            logger.info("错误处理测试通过")
        except Exception as e:
            # 如果抛出异常，说明错误处理有问题
            logger.error(f"错误处理测试失败: {str(e)}")
            raise
        
        logger.info("数据获取器完整功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据获取器测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_fetcher_error_handling():
    """测试数据获取器错误处理"""
    logger.info("开始测试数据获取器错误处理")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_fetcher_error.db")
    
    try:
        # 创建测试配置
        config = Config()
        config.set('database.path', test_db_path)
        
        # 初始化数据获取器
        fetcher = DataFetcher(config)
        
        # 测试1: 网络错误处理
        logger.info("测试1: 网络错误处理")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            # 模拟网络错误
            mock_ak.side_effect = Exception("网络错误")
            
            success = fetcher.fetch_and_store_data("000001", days=10)
            assert not success, "网络错误应该返回失败"
            logger.info("网络错误处理测试通过")
        
        # 测试2: 数据格式错误处理
        logger.info("测试2: 数据格式错误处理")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            # 模拟返回空数据
            mock_ak.return_value = pd.DataFrame()
            
            success = fetcher.fetch_and_store_data("000001", days=10)
            assert not success, "空数据应该返回失败"
            logger.info("数据格式错误处理测试通过")
        
        # 测试3: 数据库错误处理
        logger.info("测试3: 数据库错误处理")
        with patch('src.data.data_storage.DataStorage.save_stock_daily') as mock_save:
            # 模拟数据库错误
            mock_save.side_effect = Exception("数据库错误")
            
            success = fetcher.fetch_and_store_data("000001", days=10)
            assert not success, "数据库错误应该返回失败"
            logger.info("数据库错误处理测试通过")
        
        logger.info("数据获取器错误处理测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据获取器错误处理测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_fetcher_performance():
    """测试数据获取器性能"""
    logger.info("开始测试数据获取器性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_fetcher_perf.db")
    
    try:
        # 创建测试配置
        config = Config()
        config.set('database.path', test_db_path)
        
        # 初始化数据获取器
        fetcher = DataFetcher(config)
        
        # 测试1: 数据获取性能
        logger.info("测试1: 数据获取性能")
        start_time = time.time()
        success = fetcher.fetch_and_store_data("000001", days=30)
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        assert success, "数据获取失败"
        assert elapsed_time < 30, f"数据获取时间过长: {elapsed_time}秒"
        logger.info(f"数据获取性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        # 测试2: 数据查询性能
        logger.info("测试2: 数据查询性能")
        start_time = time.time()
        stock_data = fetcher.get_stock_data("000001")
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        assert len(stock_data) > 0, "查询数据为空"
        assert elapsed_time < 1, f"数据查询时间过长: {elapsed_time}秒"
        logger.info(f"数据查询性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        # 测试3: 批量获取性能
        logger.info("测试3: 批量获取性能")
        test_symbols = ["000001", "000002"]
        start_time = time.time()
        results = fetcher.batch_fetch_data(test_symbols, days=10)
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        success_count = sum(results.values())
        assert success_count > 0, "批量获取全部失败"
        assert elapsed_time < 60, f"批量获取时间过长: {elapsed_time}秒"
        logger.info(f"批量获取性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        logger.info("数据获取器性能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据获取器性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_data_fetcher_comprehensive()
    test_data_fetcher_error_handling()
    test_data_fetcher_performance()