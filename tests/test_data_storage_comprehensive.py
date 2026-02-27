"""
测试数据存储器完整功能
"""

import sys
import os
import pandas as pd
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.data_storage import DataStorage
from src.data.models import StockData, TradeRecord, StockInfo
from src.common.database import DatabaseManager
from loguru import logger


def test_data_storage_comprehensive():
    """测试数据存储器完整功能"""
    logger.info("开始测试数据存储器完整功能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_stock_data.db")
    
    try:
        # 初始化存储器
        storage = DataStorage(test_db_path)
        
        # 测试1: 保存股票日线数据
        logger.info("测试1: 保存股票日线数据")
        test_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 5,
            'trade_date': ['20230101', '20230102', '20230103', '20230104', '20230105'],
            'open': [10.0, 10.5, 10.2, 10.8, 11.0],
            'high': [10.5, 10.8, 10.9, 11.2, 11.5],
            'low': [9.8, 10.1, 10.0, 10.5, 10.7],
            'close': [10.2, 10.6, 10.7, 11.0, 11.2],
            'volume': [1000000, 1200000, 900000, 1500000, 1100000],
            'amount': [10200000, 12720000, 9630000, 16500000, 12320000]
        })
        
        saved_count = storage.save_stock_daily(test_data)
        assert saved_count == 5, f"期望保存5条记录，实际保存{saved_count}条"
        logger.info("保存股票日线数据测试通过")
        
        # 测试2: 重复保存相同数据（应该替换）
        logger.info("测试2: 重复保存相同数据")
        saved_count = storage.save_stock_daily(test_data)
        assert saved_count == 0, f"期望新增0条记录，实际新增{saved_count}条"
        logger.info("重复保存相同数据测试通过")
        
        # 测试3: 保存部分重叠的数据
        logger.info("测试3: 保存部分重叠的数据")
        overlap_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'trade_date': ['20230104', '20230105', '20230106'],
            'open': [10.8, 11.0, 11.2],
            'high': [11.2, 11.5, 11.8],
            'low': [10.5, 10.7, 10.9],
            'close': [11.0, 11.2, 11.5],
            'volume': [1500000, 1100000, 1300000],
            'amount': [16500000, 12320000, 14950000]
        })
        
        saved_count = storage.save_stock_daily(overlap_data)
        assert saved_count == 1, f"期望新增1条记录，实际新增{saved_count}条"
        logger.info("保存部分重叠数据测试通过")
        
        # 测试4: 保存股票列表
        logger.info("测试4: 保存股票列表")
        stock_list = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'symbol': ['000001', '000002'],
            'name': ['平安银行', '万科A']
        })
        
        saved_count = storage.save_stock_list(stock_list)
        assert saved_count == 2, f"期望保存2条记录，实际保存{saved_count}条"
        logger.info("保存股票列表测试通过")
        
        # 测试5: 检查数据存在性
        logger.info("测试5: 检查数据存在性")
        exists = storage.check_data_exists('000001.SZ', '20230101', '20230105')
        assert exists, "期望数据存在，但检查结果为不存在"
        
        not_exists = storage.check_data_exists('000001.SZ', '20230107', '20230110')
        assert not not_exists, "期望数据不存在，但检查结果为存在"
        logger.info("检查数据存在性测试通过")
        
        # 测试6: 获取缺失日期
        logger.info("测试6: 获取缺失日期")
        missing_dates = storage.get_missing_dates('000001.SZ', '20230101', '20230110')
        expected_missing = ['20230107', '20230108', '20230109', '20230110']
        assert set(missing_dates) == set(expected_missing), f"期望缺失日期{expected_missing}，实际{missing_dates}"
        logger.info("获取缺失日期测试通过")
        
        # 测试7: 删除数据
        logger.info("测试7: 删除数据")
        deleted_count = storage.delete_data('000001.SZ', '20230106', '20230106')
        assert deleted_count == 1, f"期望删除1条记录，实际删除{deleted_count}条"
        
        deleted_count = storage.delete_data('000001.SZ')
        assert deleted_count == 5, f"期望删除5条记录，实际删除{deleted_count}条"
        logger.info("删除数据测试通过")
        
        # 测试8: 保存空数据
        logger.info("测试8: 保存空数据")
        empty_data = pd.DataFrame()
        saved_count = storage.save_stock_daily(empty_data)
        assert saved_count == 0, f"期望保存0条记录，实际保存{saved_count}条"
        logger.info("保存空数据测试通过")
        
        # 测试9: 保存缺少必要列的数据
        logger.info("测试9: 保存缺少必要列的数据")
        incomplete_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230101'],
            'open': [10.0]
            # 缺少其他必要列
        })
        
        saved_count = storage.save_stock_daily(incomplete_data)
        assert saved_count == 0, f"期望保存0条记录，实际保存{saved_count}条"
        logger.info("保存缺少必要列的数据测试通过")
        
        logger.info("数据存储器完整功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据存储器测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_database_manager_comprehensive():
    """测试数据库管理器完整功能"""
    logger.info("开始测试数据库管理器完整功能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_db_manager.db")
    
    try:
        # 初始化数据库管理器
        db_manager = DatabaseManager(test_db_path)
        
        # 测试1: 执行查询
        logger.info("测试1: 执行查询")
        results = db_manager.execute_query("SELECT name FROM sqlite_master WHERE type='table'")
        assert len(results) > 0, "期望查询到表，但结果为空"
        logger.info("执行查询测试通过")
        
        # 测试2: 执行更新
        logger.info("测试2: 执行更新")
        affected_rows = db_manager.execute_update(
            "INSERT OR IGNORE INTO account (id, total_assets, available_cash, position_value, update_time) VALUES (?, ?, ?, ?, ?)",
            (1, 100000, 100000, 0, '2023-01-01 00:00:00')
        )
        assert affected_rows == 1, f"期望影响1行，实际影响{affected_rows}行"
        logger.info("执行更新测试通过")
        
        # 测试3: 插入DataFrame
        logger.info("测试3: 插入DataFrame")
        test_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101'],
            'open': [10.0, 20.0],
            'high': [10.5, 20.5],
            'low': [9.5, 19.5],
            'close': [10.2, 20.2],
            'volume': [1000000, 2000000]
        })
        
        db_manager.insert_dataframe(test_df, 'stock_daily', 'append')
        results = db_manager.execute_query("SELECT COUNT(*) as count FROM stock_daily")
        count = results[0]['count'] if results else 0
        assert count == 2, f"期望有2条记录，实际有{count}条"
        logger.info("插入DataFrame测试通过")
        
        # 测试4: 获取股票数据
        logger.info("测试4: 获取股票数据")
        stock_data = db_manager.get_stock_data('000001.SZ')
        assert len(stock_data) == 1, f"期望有1条记录，实际有{len(stock_data)}条"
        assert stock_data.iloc[0]['ts_code'] == '000001.SZ', "股票代码不匹配"
        logger.info("获取股票数据测试通过")
        
        # 测试5: 连接上下文管理器
        logger.info("测试5: 连接上下文管理器")
        with db_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM stock_daily")
            result = cursor.fetchone()
            assert result['count'] == 2, f"期望有2条记录，实际有{result['count']}条"
        logger.info("连接上下文管理器测试通过")
        
        logger.info("数据库管理器完整功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据库管理器测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_data_storage_comprehensive()
    test_database_manager_comprehensive()