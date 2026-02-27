#!/usr/bin/env python
"""
回测引擎测试脚本

测试回测引擎的基本功能
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting import BacktestEngine, BacktestConfig
from src.trading import strategy_config_manager
from src.data.data_query import DataQuery


def test_backtest_engine():
    """测试回测引擎"""
    print("回测引擎测试")
    print("=" * 50)
    
    try:
        # 1. 创建回测配置
        config = BacktestConfig(
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31),
            initial_cash=100000.0,
            commission_rate=0.0003,
            slippage_rate=0.001
        )
        
        print("1. 回测配置:")
        print(f"   时间范围: {config.start_date.strftime('%Y-%m-%d')} 到 {config.end_date.strftime('%Y-%m-%d')}")
        print(f"   初始资金: {config.initial_cash:.2f}")
        print(f"   手续费率: {config.commission_rate*100:.3f}%")
        print(f"   滑点率: {config.slippage_rate*100:.2f}%")
        
        # 2. 创建策略
        strategy = strategy_config_manager.create_strategy("dual_ma")
        print(f"\n2. 创建策略: {strategy.name}")
        
        # 3. 创建回测引擎
        engine = BacktestEngine(config)
        print("\n3. 回测引擎创建成功")
        
        # 4. 检查数据
        data_query = DataQuery(db_path="data/stock_data.db")
        symbols = ["000001.SZ"]
        
        print(f"\n4. 检查数据: {symbols}")
        for symbol in symbols:
            df = data_query.get_stock_daily(symbol, config.start_date, config.end_date)
            if not df.empty:
                print(f"   {symbol}: {len(df)} 条数据，范围 {df.index[0]} 到 {df.index[-1]}")
            else:
                print(f"   {symbol}: 无数据")
        
        # 5. 运行回测（如果有数据）
        df = data_query.get_stock_daily(symbols[0], config.start_date, config.end_date)
        if not df.empty:
            print(f"\n5. 开始运行回测...")
            result = engine.run_backtest(strategy, symbols)
            
            # 6. 显示结果
            print("\n6. 回测结果:")
            result.print_summary()
        else:
            print("\n5. 无可用数据，跳过回测")
        
        print("\n回测引擎测试完成！")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_backtest_engine()