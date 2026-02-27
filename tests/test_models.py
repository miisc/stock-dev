"""
测试数据模型
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.models import (
    StockData, StockInfo, TradeRecord, Signal, Position, Account, 
    StrategyConfig, BacktestResult, validate_data_list, data_to_json, json_to_data
)
from loguru import logger


def test_stock_data_model():
    """测试股票数据模型"""
    logger.info("测试股票数据模型")
    
    # 创建测试数据
    stock_data = StockData(
        ts_code='000001.SZ',
        trade_date='20230101',
        open=10.0,
        high=10.5,
        low=9.8,
        close=10.2,
        volume=1000000,
        amount=10200000
    )
    
    # 测试数据验证
    assert stock_data.validate(), "有效的股票数据应该通过验证"
    
    # 测试无效数据
    invalid_data = StockData(
        ts_code='000001.SZ',
        trade_date='20230101',
        open=10.0,
        high=9.5,  # high < low
        low=9.8,
        close=10.2,
        volume=1000000
    )
    assert not invalid_data.validate(), "无效的股票数据应该不通过验证"
    
    # 测试转换
    data_dict = stock_data.to_dict()
    assert data_dict['ts_code'] == '000001.SZ', "转换为字典后代码不匹配"
    
    restored_data = StockData.from_dict(data_dict)
    assert restored_data.ts_code == stock_data.ts_code, "从字典恢复后代码不匹配"
    
    logger.info("股票数据模型测试通过")


def test_trade_record_model():
    """测试交易记录模型"""
    logger.info("测试交易记录模型")
    
    # 创建测试数据
    trade_record = TradeRecord(
        id=1,
        ts_code='000001.SZ',
        direction='BUY',
        price=10.2,
        quantity=1000,
        amount=10200,
        trade_time='20230101 09:30:00',
        strategy_id='test_strategy',
        commission=30.6,
        notes='测试买入'
    )
    
    # 测试数据验证
    assert trade_record.validate(), "有效的交易记录应该通过验证"
    
    # 测试无效数据
    invalid_record = TradeRecord(
        ts_code='000001.SZ',
        direction='INVALID',  # 无效方向
        price=10.2,
        quantity=1000,
        amount=10200,
        trade_time='20230101 09:30:00',
        strategy_id='test_strategy'
    )
    assert not invalid_record.validate(), "无效的交易记录应该不通过验证"
    
    # 测试转换
    data_dict = trade_record.to_dict()
    assert data_dict['direction'] == 'BUY', "转换为字典后方向不匹配"
    
    restored_record = TradeRecord.from_dict(data_dict)
    assert restored_record.direction == trade_record.direction, "从字典恢复后方向不匹配"
    
    logger.info("交易记录模型测试通过")


def test_signal_model():
    """测试策略信号模型"""
    logger.info("测试策略信号模型")
    
    # 创建测试数据
    signal = Signal(
        symbol='000001.SZ',
        datetime='20230101 09:30:00',
        direction='BUY',
        price=10.2,
        quantity=1000,
        reason='金叉买入',
        confidence=0.8
    )
    
    # 测试数据验证
    assert signal.validate(), "有效的策略信号应该通过验证"
    
    # 测试无效数据
    invalid_signal = Signal(
        symbol='000001.SZ',
        datetime='20230101 09:30:00',
        direction='INVALID',  # 无效方向
        price=10.2,
        quantity=1000,
        reason='测试信号',
        confidence=1.5  # 超出范围
    )
    assert not invalid_signal.validate(), "无效的策略信号应该不通过验证"
    
    # 测试转换
    data_dict = signal.to_dict()
    assert data_dict['direction'] == 'BUY', "转换为字典后方向不匹配"
    
    restored_signal = Signal.from_dict(data_dict)
    assert restored_signal.direction == signal.direction, "从字典恢复后方向不匹配"
    
    logger.info("策略信号模型测试通过")


def test_position_model():
    """测试持仓信息模型"""
    logger.info("测试持仓信息模型")
    
    # 创建测试数据
    position = Position(
        ts_code='000001.SZ',
        quantity=1000,
        avg_cost=10.2,
        market_value=10200,
        last_update='20230101 15:00:00'
    )
    
    # 测试数据验证
    assert position.validate(), "有效的持仓信息应该通过验证"
    
    # 测试无效数据
    invalid_position = Position(
        ts_code='000001.SZ',
        quantity=-1000,  # 负数量
        avg_cost=10.2,
        market_value=10200,
        last_update='20230101 15:00:00'
    )
    assert not invalid_position.validate(), "无效的持仓信息应该不通过验证"
    
    # 测试转换
    data_dict = position.to_dict()
    assert data_dict['quantity'] == 1000, "转换为字典后数量不匹配"
    
    restored_position = Position.from_dict(data_dict)
    assert restored_position.quantity == position.quantity, "从字典恢复后数量不匹配"
    
    logger.info("持仓信息模型测试通过")


def test_account_model():
    """测试账户信息模型"""
    logger.info("测试账户信息模型")
    
    # 创建测试数据
    account = Account(
        id=1,
        total_assets=100000,
        available_cash=50000,
        position_value=50000,
        total_profit=5000,
        update_time='20230101 15:00:00'
    )
    
    # 测试数据验证
    assert account.validate(), "有效的账户信息应该通过验证"
    
    # 测试无效数据
    invalid_account = Account(
        id=1,
        total_assets=100000,
        available_cash=60000,  # 可用资金大于总资产
        position_value=50000,
        total_profit=5000,
        update_time='20230101 15:00:00'
    )
    assert not invalid_account.validate(), "无效的账户信息应该不通过验证"
    
    # 测试转换
    data_dict = account.to_dict()
    assert data_dict['total_assets'] == 100000, "转换为字典后总资产不匹配"
    
    restored_account = Account.from_dict(data_dict)
    assert restored_account.total_assets == account.total_assets, "从字典恢复后总资产不匹配"
    
    logger.info("账户信息模型测试通过")


def test_strategy_config_model():
    """测试策略配置模型"""
    logger.info("测试策略配置模型")
    
    # 创建测试数据
    strategy_config = StrategyConfig(
        id='test_strategy',
        name='测试策略',
        description='这是一个测试策略',
        parameters={'short_window': 5, 'long_window': 20},
        is_active=True,
        created_time='20230101 00:00:00',
        updated_time='20230101 00:00:00'
    )
    
    # 测试参数操作
    assert strategy_config.get_parameter('short_window') == 5, "获取参数失败"
    assert strategy_config.get_parameter('nonexistent', 'default') == 'default', "获取不存在的参数失败"
    
    strategy_config.set_parameter('new_param', 'new_value')
    assert strategy_config.get_parameter('new_param') == 'new_value', "设置参数失败"
    
    # 测试转换
    data_dict = strategy_config.to_dict()
    assert data_dict['name'] == '测试策略', "转换为字典后名称不匹配"
    
    restored_config = StrategyConfig.from_dict(data_dict)
    assert restored_config.name == strategy_config.name, "从字典恢复后名称不匹配"
    
    logger.info("策略配置模型测试通过")


def test_backtest_result_model():
    """测试回测结果模型"""
    logger.info("测试回测结果模型")
    
    # 创建测试交易记录
    trade_records = [
        TradeRecord(
            ts_code='000001.SZ',
            direction='BUY',
            price=10.0,
            quantity=1000,
            amount=10000,
            trade_time='20230101 09:30:00',
            strategy_id='test_strategy'
        ),
        TradeRecord(
            ts_code='000001.SZ',
            direction='SELL',
            price=10.5,
            quantity=1000,
            amount=10500,
            trade_time='20230102 09:30:00',
            strategy_id='test_strategy'
        )
    ]
    
    # 创建测试组合价值
    portfolio_values = [
        {'datetime': '20230101', 'portfolio_value': 100000},
        {'datetime': '20230102', 'portfolio_value': 105000}
    ]
    
    # 创建测试回测结果
    backtest_result = BacktestResult(
        strategy_name='test_strategy',
        symbol='000001.SZ',
        start_date='20230101',
        end_date='20230102',
        initial_capital=100000,
        final_capital=105000,
        total_return=0.05,
        annual_return=0.05,
        max_drawdown=0.01,
        sharpe_ratio=1.5,
        win_rate=1.0,
        trade_records=trade_records,
        portfolio_values=portfolio_values
    )
    
    # 测试转换
    data_dict = backtest_result.to_dict()
    assert data_dict['strategy_name'] == 'test_strategy', "转换为字典后策略名称不匹配"
    assert len(data_dict['trade_records']) == 2, "转换为字典后交易记录数量不匹配"
    
    restored_result = BacktestResult.from_dict(data_dict)
    assert restored_result.strategy_name == backtest_result.strategy_name, "从字典恢复后策略名称不匹配"
    assert len(restored_result.trade_records) == 2, "从字典恢复后交易记录数量不匹配"
    
    logger.info("回测结果模型测试通过")


def test_utility_functions():
    """测试工具函数"""
    logger.info("测试工具函数")
    
    # 测试数据列表验证
    valid_data = [
        StockData('000001.SZ', '20230101', 10.0, 10.5, 9.8, 10.2, 1000000),
        StockData('000001.SZ', '20230102', 10.2, 10.7, 10.0, 10.5, 1100000)
    ]
    assert validate_data_list(valid_data), "有效数据列表应该通过验证"
    
    invalid_data = [
        StockData('000001.SZ', '20230101', 10.0, 10.5, 9.8, 10.2, 1000000),
        StockData('000001.SZ', '20230102', 10.2, 9.7, 10.0, 10.5, 1100000)  # high < low
    ]
    assert not validate_data_list(invalid_data), "无效数据列表应该不通过验证"
    
    # 测试JSON转换
    stock_data = StockData('000001.SZ', '20230101', 10.0, 10.5, 9.8, 10.2, 1000000)
    json_str = data_to_json(stock_data)
    assert '000001.SZ' in json_str, "JSON转换失败"
    
    restored_data = json_to_data(json_str, StockData)
    assert restored_data.ts_code == stock_data.ts_code, "JSON恢复失败"
    
    logger.info("工具函数测试通过")


def test_model_edge_cases():
    """测试模型边界情况"""
    logger.info("测试模型边界情况")
    
    # 测试空参数
    strategy_config = StrategyConfig(
        id='test',
        name='test',
        description='test',
        parameters={}
    )
    assert strategy_config.get_parameter('nonexistent') is None, "获取不存在的参数应该返回None"
    
    # 测试空交易记录
    empty_trade = TradeRecord()
    assert not empty_trade.validate(), "空交易记录应该不通过验证"
    
    # 测试空策略信号
    empty_signal = Signal()
    assert not empty_signal.validate(), "空策略信号应该不通过验证"
    
    # 测试最小值
    min_position = Position(
        ts_code='000001.SZ',
        quantity=0,
        avg_cost=0,
        market_value=0,
        last_update='20230101'
    )
    assert min_position.validate(), "最小持仓值应该通过验证"
    
    logger.info("模型边界情况测试通过")


def main():
    """主函数"""
    logger.info("开始测试数据模型")
    
    try:
        test_stock_data_model()
        test_trade_record_model()
        test_signal_model()
        test_position_model()
        test_account_model()
        test_strategy_config_model()
        test_backtest_result_model()
        test_utility_functions()
        test_model_edge_cases()
        
        logger.info("🎉 所有数据模型测试通过！")
        return True
        
    except Exception as e:
        logger.error(f"数据模型测试失败: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)