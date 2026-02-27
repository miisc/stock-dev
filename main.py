"""
股票交易系统启动脚本
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.common.config import Config
from src.common.logger import setup_logger


def main():
    """主函数"""
    print("股票交易系统启动中...")
    
    # 设置日志
    logger = setup_logger()
    logger.info("系统启动")
    
    # 加载配置
    config = Config()
    logger.info(f"配置加载完成: {config.config_path}")
    
    # 这里可以添加系统初始化代码
    logger.info("系统初始化完成")
    
    print("系统启动完成！")
    print("使用 'python -m src.backtesting' 运行回测系统")
    print("使用 'python -m src.trading' 运行交易系统")


if __name__ == "__main__":
    main()