"""
测试数据查询器完整功能
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

from src.data.data_query import DataQuery
from src.data.data_storage import DataStorage
from src.data.models import StockData, StockInfo
from loguru import logger


def test_data_query_comprehensive():
    """测试数据查询器完整功能"""
    logger.info("开始测试数据查询器完整功能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_query.db")
    
    try:
        # 初始化存储器和查询器
        storage = DataStorage(test_db_path)
        query = DataQuery(test_db_path)
        
        # 准备测试数据
        test_stock_data = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 10,
            'trade_date': [f'202301{str(i).zfill(2)}' for i in range(1, 11)],
            'open': [10.0 + i * 0.1 for i in range(10)],
            'high': [10.5 + i * 0.1 for i in range(10)],
            'low': [9.5 + i * 0.1 for i in range(10)],
            'close': [10.2 + i * 0.1 for i in range(10)],
            'volume': [1000000 + i * 100000 for i in range(10)],
            'amount': [10200000 + i * 1000000 for i in range(10)]
        })
        
        test_stock_list = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
            'symbol': ['000001', '000002', '600000'],
            'name': ['平安银行', '万科A', '浦发银行']
        })
        
        # 保存测试数据
        storage.save_stock_daily(test_stock_data)
        storage.save_stock_list(test_stock_list)
        
        # 测试1: 获取股票日线数据
        logger.info("测试1: 获取股票日线数据")
        stock_data = query.get_stock_daily('000001.SZ')
        assert len(stock_data) == 10, f"期望有10条记录，实际有{len(stock_data)}条"
        assert stock_data.iloc[0]['ts_code'] == '000001.SZ', "股票代码不匹配"
        logger.info("获取股票日线数据测试通过")
        
        # 测试2: 按日期范围查询
        logger.info("测试2: 按日期范围查询")
        range_data = query.get_stock_daily('000001.SZ', '20230103', '20230107')
        assert len(range_data) == 5, f"期望有5条记录，实际有{len(range_data)}条"
        assert range_data.iloc[0]['trade_date'] == '20230103', "开始日期不匹配"
        assert range_data.iloc[-1]['trade_date'] == '20230107', "结束日期不匹配"
        logger.info("按日期范围查询测试通过")
        
        # 测试3: 查询不存在的股票
        logger.info("测试3: 查询不存在的股票")
        empty_data = query.get_stock_daily('999999.SZ')
        assert len(empty_data) == 0, "不存在的股票应该返回空数据"
        logger.info("查询不存在的股票测试通过")
        
        # 测试4: 获取股票列表
        logger.info("测试4: 获取股票列表")
        stock_list = query.get_stock_list()
        assert len(stock_list) == 3, f"期望有3只股票，实际有{len(stock_list)}只"
        assert '000001.SZ' in stock_list['ts_code'].values, "股票列表中缺少000001.SZ"
        logger.info("获取股票列表测试通过")
        
        # 测试5: 获取股票基本信息
        logger.info("测试5: 获取股票基本信息")
        stock_info = query.get_stock_info('000001.SZ')
        assert stock_info, "股票信息为空"
        assert stock_info['name'] == '平安银行', "股票名称不匹配"
        logger.info("获取股票基本信息测试通过")
        
        # 测试6: 获取不存在股票的信息
        logger.info("测试6: 获取不存在股票的信息")
        empty_info = query.get_stock_info('999999.SZ')
        assert not empty_info, "不存在的股票信息应该为空"
        logger.info("获取不存在股票的信息测试通过")
        
        # 测试7: 获取最新日期
        logger.info("测试7: 获取最新日期")
        latest_date = query.get_latest_date('000001.SZ')
        assert latest_date == '20230110', f"期望最新日期为20230110，实际为{latest_date}"
        logger.info("获取最新日期测试通过")
        
        # 测试8: 获取最早日期
        logger.info("测试8: 获取最早日期")
        earliest_date = query.get_earliest_date('000001.SZ')
        assert earliest_date == '20230101', f"期望最早日期为20230101，实际为{earliest_date}"
        logger.info("获取最早日期测试通过")
        
        # 测试9: 获取数据记录数
        logger.info("测试9: 获取数据记录数")
        count = query.get_data_count('000001.SZ')
        assert count == 10, f"期望有10条记录，实际有{count}条"
        
        total_count = query.get_data_count()
        assert total_count == 10, f"期望总共有10条记录，实际有{total_count}条"
        logger.info("获取数据记录数测试通过")
        
        # 测试10: 获取股票数据摘要
        logger.info("测试10: 获取股票数据摘要")
        summary = query.get_stock_summary()
        assert len(summary) == 1, f"期望有1只股票的摘要，实际有{len(summary)}只"
        assert summary.iloc[0]['ts_code'] == '000001.SZ', "摘要股票代码不匹配"
        assert summary.iloc[0]['record_count'] == 10, "摘要记录数不匹配"
        logger.info("获取股票数据摘要测试通过")
        
        # 测试11: 搜索股票
        logger.info("测试11: 搜索股票")
        search_results = query.search_stocks('平安')
        assert len(search_results) == 1, f"期望搜索到1只股票，实际搜索到{len(search_results)}只"
        assert search_results.iloc[0]['ts_code'] == '000001.SZ', "搜索结果股票代码不匹配"
        
        # 测试按代码搜索
        search_results = query.search_stocks('000002')
        assert len(search_results) == 1, f"期望搜索到1只股票，实际搜索到{len(search_results)}只"
        assert search_results.iloc[0]['ts_code'] == '000002.SZ', "搜索结果股票代码不匹配"
        
        # 测试按名称搜索
        search_results = query.search_stocks('银行')
        assert len(search_results) == 2, f"期望搜索到2只股票，实际搜索到{len(search_results)}只"
        logger.info("搜索股票测试通过")
        
        # 测试12: 搜索不存在的股票
        logger.info("测试12: 搜索不存在的股票")
        empty_results = query.search_stocks('不存在的股票')
        assert len(empty_results) == 0, "搜索不存在的股票应该返回空结果"
        logger.info("搜索不存在的股票测试通过")
        
        logger.info("数据查询器完整功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据查询器测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_query_edge_cases():
    """测试数据查询器边界情况"""
    logger.info("开始测试数据查询器边界情况")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_query_edge.db")
    
    try:
        # 初始化存储器和查询器
        storage = DataStorage(test_db_path)
        query = DataQuery(test_db_path)
        
        # 测试1: 查询空数据库
        logger.info("测试1: 查询空数据库")
        empty_data = query.get_stock_daily('000001.SZ')
        assert len(empty_data) == 0, "空数据库查询应该返回空结果"
        
        empty_list = query.get_stock_list()
        assert len(empty_list) == 0, "空数据库股票列表应该为空"
        
        empty_summary = query.get_stock_summary()
        assert len(empty_summary) == 0, "空数据库摘要应该为空"
        logger.info("查询空数据库测试通过")
        
        # 测试2: 查询单条记录
        logger.info("测试2: 查询单条记录")
        single_data = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230101'],
            'open': [10.0],
            'high': [10.5],
            'low': [9.5],
            'close': [10.2],
            'volume': [1000000],
            'amount': [10200000]
        })
        
        storage.save_stock_daily(single_data)
        
        result = query.get_stock_daily('000001.SZ')
        assert len(result) == 1, "单条记录查询应该返回1条记录"
        assert result.iloc[0]['trade_date'] == '20230101', "单条记录日期不匹配"
        logger.info("查询单条记录测试通过")
        
        # 测试3: 查询无效日期范围
        logger.info("测试3: 查询无效日期范围")
        # 开始日期晚于结束日期
        empty_result = query.get_stock_daily('000001.SZ', '20230105', '20230101')
        assert len(empty_result) == 0, "无效日期范围应该返回空结果"
        
        # 不存在的日期范围
        empty_result = query.get_stock_daily('000001.SZ', '20230201', '20230205')
        assert len(empty_result) == 0, "不存在的日期范围应该返回空结果"
        logger.info("查询无效日期范围测试通过")
        
        # 测试4: 查询边界日期
        logger.info("测试4: 查询边界日期")
        # 查询精确日期
        exact_result = query.get_stock_daily('000001.SZ', '20230101', '20230101')
        assert len(exact_result) == 1, "精确日期查询应该返回1条记录"
        
        # 查询包含边界日期的范围
        range_result = query.get_stock_daily('000001.SZ', '20230101', '20230101')
        assert len(range_result) == 1, "边界日期范围查询应该返回1条记录"
        logger.info("查询边界日期测试通过")
        
        # 测试5: 搜索空字符串和特殊字符
        logger.info("测试5: 搜索空字符串和特殊字符")
        empty_search = query.search_stocks('')
        assert len(empty_search) == 0, "搜索空字符串应该返回空结果"
        
        special_search = query.search_stocks('!@#$%')
        assert len(special_search) == 0, "搜索特殊字符应该返回空结果"
        logger.info("搜索空字符串和特殊字符测试通过")
        
        logger.info("数据查询器边界情况测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据查询器边界情况测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def test_data_query_performance():
    """测试数据查询器性能"""
    logger.info("开始测试数据查询器性能")
    
    # 创建临时测试数据库
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "test_query_perf.db")
    
    try:
        # 初始化存储器和查询器
        storage = DataStorage(test_db_path)
        query = DataQuery(test_db_path)
        
        # 准备大量测试数据
        logger.info("准备大量测试数据...")
        symbols = ['000001.SZ', '000002.SZ', '000858.SZ', '600000.SH', '600036.SH']
        dates = [f'2022{str(month).zfill(2)}{str(day).zfill(2)}' 
                for month in range(1, 13) for day in range(1, 29)]
        
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
        
        # 测试1: 大数据量查询性能
        logger.info("测试1: 大数据量查询性能")
        import time
        start_time = time.time()
        
        result = query.get_stock_daily('000001.SZ')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(result) > 0, "查询结果为空"
        assert elapsed_time < 1, f"大数据量查询时间过长: {elapsed_time}秒"
        logger.info(f"大数据量查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试2: 日期范围查询性能
        logger.info("测试2: 日期范围查询性能")
        start_time = time.time()
        
        range_result = query.get_stock_daily('000001.SZ', '20220101', '20221231')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(range_result) > 0, "日期范围查询结果为空"
        assert elapsed_time < 1, f"日期范围查询时间过长: {elapsed_time}秒"
        logger.info(f"日期范围查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试3: 摘要查询性能
        logger.info("测试3: 摘要查询性能")
        start_time = time.time()
        
        summary = query.get_stock_summary()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(summary) > 0, "摘要查询结果为空"
        assert elapsed_time < 1, f"摘要查询时间过长: {elapsed_time}秒"
        logger.info(f"摘要查询性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试4: 搜索性能
        logger.info("测试4: 搜索性能")
        start_time = time.time()
        
        search_results = query.search_stocks('银行')
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        assert len(search_results) > 0, "搜索结果为空"
        assert elapsed_time < 1, f"搜索时间过长: {elapsed_time}秒"
        logger.info(f"搜索性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        logger.info("数据查询器性能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"数据查询器性能测试失败: {str(e)}")
        return False
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_data_query_comprehensive()
    test_data_query_edge_cases()
    test_data_query_performance()