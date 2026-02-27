"""
股票数据获取示例
演示如何使用股票回测系统的数据获取功能
"""

import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.data.data_fetcher import DataFetcher
from src.data.data_query import DataQuery
from loguru import logger


def main():
    """主函数"""
    logger.info("股票数据获取示例")
    
    # 初始化数据获取器和查询器
    fetcher = DataFetcher()
    query = DataQuery("data/stock_data.db")
    
    # 1. 获取股票列表
    logger.info("1. 获取股票列表")
    try:
        success = fetcher.fetch_and_store_stock_list()
        if success:
            logger.info("成功获取股票列表")
            # 获取股票列表用于显示
            stock_list = query.get_stock_list()
            if not stock_list.empty:
                print("股票列表前5只:")
                print(stock_list.head())
            else:
                logger.warning("获取股票列表为空")
        else:
            logger.warning("获取股票列表失败")
            return
    except Exception as e:
        logger.error(f"获取股票列表失败: {str(e)}")
        return
    
    # 2. 获取特定股票的数据
    logger.info("\n2. 获取股票数据")
    symbols = ["000001", "600519"]  # 平安银行和贵州茅台
    
    for symbol in symbols:
        try:
            logger.info(f"获取股票 {symbol} 的数据")
            count = fetcher.fetch_and_store_data(symbol, days=30)
            if count > 0:
                logger.info(f"成功获取并存储 {count} 条记录")
            else:
                logger.warning(f"未获取到股票 {symbol} 的新数据")
        except Exception as e:
            logger.error(f"获取股票 {symbol} 数据失败: {str(e)}")
    
    # 3. 查询股票数据
    logger.info("\n3. 查询股票数据")
    for symbol in symbols:
        try:
            df = query.get_stock_daily(symbol, days=7)
            if not df.empty:
                logger.info(f"股票 {symbol} 最近7天的数据:")
                print(df)
            else:
                logger.warning(f"未查询到股票 {symbol} 的数据")
        except Exception as e:
            logger.error(f"查询股票 {symbol} 数据失败: {str(e)}")
    
    # 4. 获取数据摘要
    logger.info("\n4. 获取数据摘要")
    try:
        summary = query.get_stock_summary()
        if not summary.empty:
            logger.info("数据摘要:")
            print(summary)
        else:
            logger.warning("未获取到数据摘要")
    except Exception as e:
        logger.error(f"获取数据摘要失败: {str(e)}")
    
    logger.info("\n示例完成!")


if __name__ == "__main__":
    main()