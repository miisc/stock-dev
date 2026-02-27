#!/usr/bin/env python
"""
测试自动数据获取功能
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.data_query import DataQuery
from src.data.data_fetcher import DataFetcher
from datetime import datetime, timedelta


def test_auto_data_fetch():
    """测试自动数据获取功能"""
    print("测试自动数据获取功能")
    print("=" * 50)
    
    # 初始化组件
    data_query = DataQuery(db_path="data/stock_data.db")
    data_fetcher = DataFetcher()
    
    # 测试参数
    symbol = "000001.SZ"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 最近30天
    
    print(f"测试股票: {symbol}")
    print(f"日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
    
    # 1. 先尝试从本地获取数据
    print("\n1. 尝试从本地数据库获取数据...")
    df = data_query.get_stock_daily(symbol, start_date, end_date)
    
    if not df.empty:
        print(f"✓ 本地找到 {len(df)} 条数据")
        print(f"  日期范围: {df.index[0]} 到 {df.index[-1]}")
    else:
        print("✗ 本地没有找到数据")
        
        # 2. 从数据源获取数据
        print("\n2. 从数据源获取数据...")
        days = (end_date - start_date).days
        success = data_fetcher.fetch_and_store_data(symbol, days)
        
        if success:
            print("✓ 数据获取成功")
            
            # 3. 再次从本地获取数据
            print("\n3. 再次从本地数据库获取数据...")
            df = data_query.get_stock_daily(symbol, start_date, end_date)
            
            if not df.empty:
                print(f"✓ 成功获取 {len(df)} 条数据")
                print(f"  日期范围: {df.index[0]} 到 {df.index[-1]}")
                print(f"  价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
            else:
                print("✗ 仍然无法获取数据")
        else:
            print("✗ 数据获取失败")
    
    print("\n测试完成！")


if __name__ == "__main__":
    test_auto_data_fetch()