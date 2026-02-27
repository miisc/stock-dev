"""
数据基础设施性能测试脚本
验证阶段1数据基础设施的性能要求
"""

import sys
import os
import pandas as pd
import tempfile
import shutil
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.data_fetcher import DataFetcher
from src.data.data_storage import DataStorage
from src.data.data_query import DataQuery
from src.common.config import Config
from loguru import logger


def test_data_fetch_performance():
    """测试数据获取性能"""
    logger.info("开始测试数据获取性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_perf_fetch.db")
    
    try:
        # 创建测试配置
        config = Config()
        config.set('database.path', test_db_path)
        
        # 初始化数据获取器
        fetcher = DataFetcher(config)
        
        # 测试1: 单次数据获取时间≤30秒
        logger.info("测试1: 单次数据获取时间≤30秒")
        test_symbol = "000001"  # 平安银行
        start_time = time.time()
        
        success = fetcher.fetch_and_store_data(test_symbol, days=30)  # 获取30天数据
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert success, f"获取股票 {test_symbol} 数据失败"
        assert elapsed_time <= 30, f"数据获取时间超过30秒限制: {elapsed_time:.2f}秒"
        
        logger.info(f"✓ 单次数据获取性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        # 测试2: 批量数据获取性能
        logger.info("测试2: 批量数据获取性能")
        test_symbols = ["000001", "000002"]  # 平安银行、万科A
        start_time = time.time()
        
        results = fetcher.batch_fetch_data(test_symbols, days=10)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        success_count = sum(results.values())
        assert success_count > 0, "批量获取全部失败"
        assert elapsed_time <= 60, f"批量获取时间超过60秒限制: {elapsed_time:.2f}秒"
        
        logger.info(f"✓ 批量数据获取性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"数据获取性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_query_performance():
    """测试数据查询性能"""
    logger.info("开始测试数据查询性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_perf_query.db")
    
    try:
        # 初始化存储器和查询器
        storage = DataStorage(test_db_path)
        query = DataQuery(test_db_path)
        
        # 准备大量测试数据
        logger.info("准备大量测试数据...")
        symbols = ['000001.SZ', '000002.SZ', '000858.SZ', '600000.SH', '600036.SH']
        dates = [f'2022{str(month).zfill(2)}{str(day).zfill(2)}' 
                for month in range(1, 13) for day in range(1, 29)]
        
        # 准备股票列表数据
        stock_list = pd.DataFrame({
            'ts_code': symbols,
            'symbol': [s.split('.')[0] for s in symbols],
            'name': [f'股票{i+1}' for i in range(len(symbols))]
        })
        storage.save_stock_list(stock_list)
        
        large_data = []
        for symbol in symbols:
            for i, date in enumerate(dates):
                large_data.append({
                    'ts_code': symbol,
                    'trade_date': date,
                    'open': 10.0 + i * 0.01,
                    'high': 10.5 + i * 0.01,
                    'low': 9.5 + i * 0.01,
                    'close': 10.2 + i * 0.01,
                    'volume': 1000000 + i * 1000,
                    'amount': 10200000 + i * 1000
                })
        
        large_df = pd.DataFrame(large_data)
        storage.save_stock_daily(large_df)
        
        # 测试1: 单次查询时间≤1秒
        logger.info("测试1: 单次查询时间≤1秒")
        start_time = time.time()
        
        stock_data = query.get_stock_daily('000001.SZ')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(stock_data) > 0, "查询数据为空"
        assert elapsed_time <= 1, f"单次查询时间超过1秒限制: {elapsed_time:.4f}秒"
        
        logger.info(f"✓ 单次查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试2: 日期范围查询性能
        logger.info("测试2: 日期范围查询性能")
        start_time = time.time()
        
        range_data = query.get_stock_daily('000001.SZ', '20220101', '20221231')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(range_data) > 0, "日期范围查询数据为空"
        assert elapsed_time <= 1, f"日期范围查询时间超过1秒限制: {elapsed_time:.4f}秒"
        
        logger.info(f"✓ 日期范围查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试3: 复杂查询性能
        logger.info("测试3: 复杂查询性能")
        start_time = time.time()
        
        summary = query.get_stock_summary()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(summary) > 0, "复杂查询数据为空"
        assert elapsed_time <= 1, f"复杂查询时间超过1秒限制: {elapsed_time:.4f}秒"
        
        logger.info(f"✓ 复杂查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"数据查询性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_storage_performance():
    """测试数据存储性能"""
    logger.info("开始测试数据存储性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_perf_storage.db")
    
    try:
        # 初始化存储器
        storage = DataStorage(test_db_path)
        
        # 准备大量测试数据
        logger.info("准备大量测试数据...")
        batch_size = 1000
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * batch_size,
            'trade_date': [f'2023{str(i).zfill(4)}' for i in range(1, batch_size + 1)],
            'open': [10.0 + i * 0.001 for i in range(batch_size)],
            'high': [10.5 + i * 0.001 for i in range(batch_size)],
            'low': [9.5 + i * 0.001 for i in range(batch_size)],
            'close': [10.2 + i * 0.001 for i in range(batch_size)],
            'volume': [1000000 + i * 1000 for i in range(batch_size)],
            'amount': [10200000 + i * 1000 for i in range(batch_size)]
        })
        
        # 测试1: 批量数据存储性能
        logger.info("测试1: 批量数据存储性能")
        start_time = time.time()
        
        saved_count = storage.save_stock_daily(test_data)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert saved_count == batch_size, f"期望保存{batch_size}条记录，实际保存{saved_count}条"
        assert elapsed_time <= 5, f"批量数据存储时间超过5秒限制: {elapsed_time:.2f}秒"
        
        logger.info(f"✓ 批量数据存储性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        # 测试2: 事务处理性能
        logger.info("测试2: 事务处理性能")
        start_time = time.time()
        
        # 模拟事务操作
        try:
            with storage.db_manager.get_connection() as conn:
                conn.execute("BEGIN TRANSACTION")
                
                # 批量插入
                for i in range(100):
                    conn.execute(
                        "INSERT OR REPLACE INTO stock_daily (ts_code, trade_date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (f'000002.SZ', f'2023{str(i).zfill(4)}', 20.0 + i * 0.001, 20.5 + i * 0.001, 19.5 + i * 0.001, 20.2 + i * 0.001, 2000000 + i * 1000)
                    )
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert elapsed_time <= 2, f"事务处理时间超过2秒限制: {elapsed_time:.2f}秒"
        
        logger.info(f"✓ 事务处理性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"数据存储性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_end_to_end_performance():
    """测试端到端性能"""
    logger.info("开始测试端到端性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_perf_e2e.db")
    
    try:
        # 创建测试配置
        config = Config()
        config.set('database.path', test_db_path)
        
        # 初始化组件
        fetcher = DataFetcher(config)
        
        # 测试1: 完整数据流程性能
        logger.info("测试1: 完整数据流程性能")
        start_time = time.time()
        
        # 获取股票列表
        success = fetcher.fetch_and_store_stock_list()
        assert success, "获取股票列表失败"
        
        # 获取单只股票数据
        success = fetcher.fetch_and_store_data("000001", days=30)
        assert success, "获取股票数据失败"
        
        # 查询数据
        stock_data = fetcher.get_stock_data("000001")
        assert len(stock_data) > 0, "查询数据为空"
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert elapsed_time <= 60, f"完整数据流程时间超过60秒限制: {elapsed_time:.2f}秒"
        
        logger.info(f"✓ 完整数据流程性能测试通过，耗时: {elapsed_time:.2f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"端到端性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def main():
    """主函数"""
    logger.info("开始数据基础设施性能测试")
    
    test_results = []
    
    # 执行各项性能测试
    test_results.append(("数据获取性能", test_data_fetch_performance()))
    test_results.append(("数据查询性能", test_data_query_performance()))
    test_results.append(("数据存储性能", test_data_storage_performance()))
    test_results.append(("端到端性能", test_end_to_end_performance()))
    
    # 输出测试结果
    logger.info("\n" + "="*50)
    logger.info("性能测试结果汇总")
    logger.info("="*50)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    logger.info("="*50)
    
    if all_passed:
        logger.info("🎉 所有性能测试通过！阶段1数据基础设施性能要求达标。")
    else:
        logger.error("❌ 部分性能测试失败，需要优化性能。")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)