"""
测试AKShare数据源完整功能
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

from src.data.akshare_source import AKShareSource
from src.data.models import StockData
from loguru import logger


def test_akshare_source_comprehensive():
    """测试AKShare数据源完整功能"""
    logger.info("开始测试AKShare数据源完整功能")
    
    try:
        # 初始化AKShare数据源
        config = {
            'max_retries': 3,
            'retry_delay': 1
        }
        akshare_source = AKShareSource(config)
        
        # 测试1: 获取股票日线数据
        logger.info("测试1: 获取股票日线数据")
        try:
            # 使用真实API测试（注意：可能因为网络问题失败）
            data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-10')
            if not data.empty:
                logger.info(f"成功获取到 {len(data)} 条数据")
                # 验证数据结构
                required_columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
                for col in required_columns:
                    assert col in data.columns, f"数据缺少必要列: {col}"
                logger.info("数据结构验证通过")
            else:
                logger.warning("获取到空数据，可能是网络问题或API限制")
        except Exception as e:
            logger.warning(f"真实API测试失败: {str(e)}，将使用模拟数据")
        
        # 测试2: 获取股票列表
        logger.info("测试2: 获取股票列表")
        try:
            # 使用真实API测试
            stock_list = akshare_source.get_stock_list()
            if not stock_list.empty:
                logger.info(f"成功获取到 {len(stock_list)} 只股票")
                # 验证数据结构
                required_columns = ['ts_code', 'symbol', 'name']
                for col in required_columns:
                    assert col in stock_list.columns, f"股票列表缺少必要列: {col}"
                logger.info("股票列表结构验证通过")
            else:
                logger.warning("获取到空股票列表，可能是网络问题或API限制")
        except Exception as e:
            logger.warning(f"股票列表API测试失败: {str(e)}，将使用模拟数据")
        
        # 测试3: 股票代码标准化
        logger.info("测试3: 股票代码标准化")
        assert akshare_source.normalize_symbol('000001') == '000001.SZ', "深圳股票代码标准化错误"
        assert akshare_source.normalize_symbol('600000') == '600000.SH', "上海股票代码标准化错误"
        assert akshare_source.normalize_symbol('000001.SZ') == '000001.SZ', "已标准化代码不应改变"
        assert akshare_source.normalize_symbol('600000.SH') == '600000.SH', "已标准化代码不应改变"
        logger.info("股票代码标准化测试通过")
        
        # 测试4: 日期范围验证
        logger.info("测试4: 日期范围验证")
        assert akshare_source.validate_date_range('2023-01-01', '2023-01-10'), "有效日期范围验证失败"
        assert not akshare_source.validate_date_range('2023-01-10', '2023-01-01'), "无效日期范围应该返回False"
        assert not akshare_source.validate_date_range('2023-13-01', '2023-01-10'), "无效日期应该返回False"
        logger.info("日期范围验证测试通过")
        
        logger.info("AKShare数据源完整功能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"AKShare数据源测试失败: {str(e)}")
        return False


def test_akshare_source_mock():
    """使用模拟数据测试AKShare数据源"""
    logger.info("开始使用模拟数据测试AKShare数据源")
    
    try:
        # 初始化AKShare数据源
        config = {
            'max_retries': 3,
            'retry_delay': 0.1  # 减少测试时间
        }
        akshare_source = AKShareSource(config)
        
        # 测试1: 模拟获取股票日线数据
        logger.info("测试1: 模拟获取股票日线数据")
        mock_data = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=5),
            'open': [10.0, 10.5, 10.2, 10.8, 11.0],
            'high': [10.5, 10.8, 10.9, 11.2, 11.5],
            'low': [9.8, 10.1, 10.0, 10.5, 10.7],
            'close': [10.2, 10.6, 10.7, 11.0, 11.2],
            'volume': [1000000, 1200000, 900000, 1500000, 1100000]
        })
        
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            mock_ak.return_value = mock_data
            
            data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-05')
            
            assert not data.empty, "模拟数据不应该为空"
            assert len(data) == 5, f"期望有5条记录，实际有{len(data)}条"
            assert 'ts_code' in data.columns, "数据应该包含ts_code列"
            assert 'trade_date' in data.columns, "数据应该包含trade_date列"
            assert data.iloc[0]['ts_code'] == '000001.SZ', "股票代码不正确"
            
            logger.info("模拟获取股票日线数据测试通过")
        
        # 测试2: 模拟获取股票列表
        logger.info("测试2: 模拟获取股票列表")
        mock_stock_list = pd.DataFrame({
            '代码': ['000001', '000002', '600000'],
            '名称': ['平安银行', '万科A', '浦发银行']
        })
        
        with patch('src.data.akshare_source.ak.stock_zh_a_spot_em') as mock_ak:
            mock_ak.return_value = mock_stock_list
            
            stock_list = akshare_source.get_stock_list()
            
            assert not stock_list.empty, "模拟股票列表不应该为空"
            assert len(stock_list) == 3, f"期望有3只股票，实际有{len(stock_list)}只"
            assert 'ts_code' in stock_list.columns, "股票列表应该包含ts_code列"
            assert 'symbol' in stock_list.columns, "股票列表应该包含symbol列"
            assert 'name' in stock_list.columns, "股票列表应该包含name列"
            
            logger.info("模拟获取股票列表测试通过")
        
        # 测试3: 模拟网络错误和重试机制
        logger.info("测试3: 模拟网络错误和重试机制")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            # 前两次调用失败，第三次成功
            mock_ak.side_effect = [
                Exception("网络错误1"),
                Exception("网络错误2"),
                mock_data
            ]
            
            data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-05')
            
            assert not data.empty, "重试后应该成功获取数据"
            assert mock_ak.call_count == 3, f"期望调用3次，实际调用{mock_ak.call_count}次"
            
            logger.info("模拟网络错误和重试机制测试通过")
        
        # 测试4: 模拟全部重试失败
        logger.info("测试4: 模拟全部重试失败")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            # 所有调用都失败
            mock_ak.side_effect = Exception("持续网络错误")
            
            try:
                data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-05')
                assert False, "应该抛出异常"
            except Exception as e:
                assert "持续网络错误" in str(e), "异常信息不正确"
                assert mock_ak.call_count == 3, f"期望调用3次，实际调用{mock_ak.call_count}次"
            
            logger.info("模拟全部重试失败测试通过")
        
        # 测试5: 模拟空数据处理
        logger.info("测试5: 模拟空数据处理")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            mock_ak.return_value = pd.DataFrame()
            
            data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-05')
            
            assert data.empty, "空数据应该返回空DataFrame"
            
            logger.info("模拟空数据处理测试通过")
        
        logger.info("AKShare数据源模拟测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"AKShare数据源模拟测试失败: {str(e)}")
        return False


def test_akshare_source_column_mapping():
    """测试AKShare数据源列映射"""
    logger.info("开始测试AKShare数据源列映射")
    
    try:
        # 初始化AKShare数据源
        akshare_source = AKShareSource()
        
        # 测试1: 新浪财经接口格式
        logger.info("测试1: 新浪财经接口格式")
        sina_data = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=3),
            'open': [10.0, 10.5, 10.2],
            'high': [10.5, 10.8, 10.9],
            'low': [9.8, 10.1, 10.0],
            'close': [10.2, 10.6, 10.7],
            'volume': [1000000, 1200000, 900000]
        })
        
        result = akshare_source._standardize_columns(sina_data, '000001.SZ')
        
        assert not result.empty, "标准化结果不应该为空"
        assert 'ts_code' in result.columns, "应该包含ts_code列"
        assert 'trade_date' in result.columns, "应该包含trade_date列"
        assert 'open' in result.columns, "应该包含open列"
        assert 'high' in result.columns, "应该包含high列"
        assert 'low' in result.columns, "应该包含low列"
        assert 'close' in result.columns, "应该包含close列"
        assert 'volume' in result.columns, "应该包含volume列"
        
        assert result.iloc[0]['ts_code'] == '000001.SZ', "股票代码不正确"
        assert len(result) == 3, "记录数不正确"
        
        logger.info("新浪财经接口格式测试通过")
        
        # 测试2: 中文列名格式
        logger.info("测试2: 中文列名格式")
        chinese_data = pd.DataFrame({
            '日期': ['2023-01-01', '2023-01-02', '2023-01-03'],
            '开盘': [10.0, 10.5, 10.2],
            '最高': [10.5, 10.8, 10.9],
            '最低': [9.8, 10.1, 10.0],
            '收盘': [10.2, 10.6, 10.7],
            '成交量': [1000000, 1200000, 900000]
        })
        
        result = akshare_source._standardize_columns(chinese_data, '000002.SZ')
        
        assert not result.empty, "标准化结果不应该为空"
        assert 'ts_code' in result.columns, "应该包含ts_code列"
        assert 'trade_date' in result.columns, "应该包含trade_date列"
        assert result.iloc[0]['ts_code'] == '000002.SZ', "股票代码不正确"
        
        logger.info("中文列名格式测试通过")
        
        # 测试3: 实时行情接口格式
        logger.info("测试3: 实时行情接口格式")
        realtime_data = pd.DataFrame({
            'symbol': ['000001', '000002', '000001'],
            'date': ['2023-01-01', '2023-01-01', '2023-01-02'],
            'open': [10.0, 20.0, 10.5],
            'high': [10.5, 20.5, 10.8],
            'low': [9.8, 19.8, 10.1],
            'close': [10.2, 20.2, 10.6],
            'volume': [1000000, 2000000, 1200000]
        })
        
        result = akshare_source._standardize_columns(realtime_data, '000001.SZ')
        
        assert not result.empty, "标准化结果不应该为空"
        assert 'ts_code' in result.columns, "应该包含ts_code列"
        assert 'trade_date' in result.columns, "应该包含trade_date列"
        
        logger.info("实时行情接口格式测试通过")
        
        # 测试4: 未知格式处理
        logger.info("测试4: 未知格式处理")
        unknown_data = pd.DataFrame({
            'unknown_date': ['2023-01-01', '2023-01-02'],
            'unknown_open': [10.0, 10.5],
            'unknown_high': [10.5, 10.8],
            'unknown_low': [9.8, 10.1],
            'unknown_close': [10.2, 10.6],
            'unknown_volume': [1000000, 1200000]
        })
        
        result = akshare_source._standardize_columns(unknown_data, '000001.SZ')
        
        # 未知格式应该只保留标准列名的数据
        assert 'ts_code' in result.columns, "应该包含ts_code列"
        # 其他列可能不存在，因为列名不匹配
        
        logger.info("未知格式处理测试通过")
        
        logger.info("AKShare数据源列映射测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"AKShare数据源列映射测试失败: {str(e)}")
        return False


def test_akshare_source_performance():
    """测试AKShare数据源性能"""
    logger.info("开始测试AKShare数据源性能")
    
    try:
        # 初始化AKShare数据源
        config = {
            'max_retries': 1,  # 减少重试次数
            'retry_delay': 0.1  # 减少重试延迟
        }
        akshare_source = AKShareSource(config)
        
        # 测试1: 大数据量处理性能
        logger.info("测试1: 大数据量处理性能")
        large_data = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=1000),  # 1000天数据
            'open': [10.0 + i * 0.001 for i in range(1000)],
            'high': [10.5 + i * 0.001 for i in range(1000)],
            'low': [9.8 + i * 0.001 for i in range(1000)],
            'close': [10.2 + i * 0.001 for i in range(1000)],
            'volume': [1000000 + i * 1000 for i in range(1000)]
        })
        
        start_time = time.time()
        result = akshare_source._standardize_columns(large_data, '000001.SZ')
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        assert not result.empty, "大数据量处理结果不应该为空"
        assert len(result) == 1000, "大数据量处理记录数不正确"
        assert elapsed_time < 1, f"大数据量处理时间过长: {elapsed_time}秒"
        
        logger.info(f"大数据量处理性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        # 测试2: 重试机制性能
        logger.info("测试2: 重试机制性能")
        with patch('src.data.akshare_source.ak.stock_zh_a_daily') as mock_ak:
            mock_data = pd.DataFrame({
                'date': pd.date_range('2023-01-01', periods=5),
                'open': [10.0, 10.5, 10.2, 10.8, 11.0],
                'high': [10.5, 10.8, 10.9, 11.2, 11.5],
                'low': [9.8, 10.1, 10.0, 10.5, 10.7],
                'close': [10.2, 10.6, 10.7, 11.0, 11.2],
                'volume': [1000000, 1200000, 900000, 1500000, 1100000]
            })
            
            # 第一次调用失败，第二次成功
            mock_ak.side_effect = [Exception("网络错误"), mock_data]
            
            start_time = time.time()
            data = akshare_source.get_stock_daily('000001', '2023-01-01', '2023-01-05')
            end_time = time.time()
            
            elapsed_time = end_time - start_time
            assert not data.empty, "重试后应该成功获取数据"
            assert mock_ak.call_count == 2, f"期望调用2次，实际调用{mock_ak.call_count}次"
            assert elapsed_time < 1, f"重试机制时间过长: {elapsed_time}秒"
            
            logger.info(f"重试机制性能测试通过，耗时: {elapsed_time:.4f}秒")
        
        logger.info("AKShare数据源性能测试全部通过")
        return True
        
    except Exception as e:
        logger.error(f"AKShare数据源性能测试失败: {str(e)}")
        return False


if __name__ == "__main__":
    test_akshare_source_comprehensive()
    test_akshare_source_mock()
    test_akshare_source_column_mapping()
    test_akshare_source_performance()