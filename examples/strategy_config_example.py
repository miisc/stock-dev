#!/usr/bin/env python
"""
策略配置系统使用示例

本示例展示了如何使用策略配置系统创建和管理策略实例
"""

import sys
from pathlib import Path
import yaml

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading import strategy_config_manager, DualMovingAverageStrategy
from src.trading.bar_data import BarData
from datetime import datetime, timedelta


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 1. 使用默认参数创建策略
    strategy = strategy_config_manager.create_strategy("dual_ma")
    print(f"创建策略: {strategy.name} (ID: {strategy.strategy_id})")
    print(f"短期窗口: {strategy.get_parameter('short_window')}")
    print(f"长期窗口: {strategy.get_parameter('long_window')}")
    print()
    
    # 2. 使用自定义参数创建策略
    custom_params = {
        "short_window": 10,
        "long_window": 30,
        "position_size": 200
    }
    custom_strategy = strategy_config_manager.create_strategy("dual_ma", custom_params)
    print(f"自定义策略: {custom_strategy.name}")
    print(f"短期窗口: {custom_strategy.get_parameter('short_window')}")
    print(f"长期窗口: {custom_strategy.get_parameter('long_window')}")
    print(f"持仓大小: {custom_strategy.get_parameter('position_size')}")
    print()


def example_parameter_info():
    """参数信息示例"""
    print("=== 参数信息示例 ===")
    
    # 获取策略参数信息
    param_info = strategy_config_manager.get_strategy_parameters_info("dual_ma")
    
    print("双均线策略参数:")
    for name, info in param_info.items():
        print(f"  {name}:")
        print(f"    类型: {info['type']}")
        print(f"    默认值: {info['default_value']}")
        print(f"    描述: {info['description']}")
        if info['min_value'] is not None:
            print(f"    最小值: {info['min_value']}")
        if info['max_value'] is not None:
            print(f"    最大值: {info['max_value']}")
    print()


def example_config_file():
    """配置文件示例"""
    print("=== 配置文件示例 ===")
    
    # 加载配置文件
    config_file = project_root / "config" / "strategies.yaml"
    if config_file.exists():
        success = strategy_config_manager.load_from_file(str(config_file))
        if success:
            print("成功加载配置文件")
            
            # 创建配置文件中定义的策略
            strategy = strategy_config_manager.create_strategy("dual_ma")
            print(f"从配置文件创建策略: {strategy.name}")
            print(f"短期窗口: {strategy.get_parameter('short_window')}")
            print(f"长期窗口: {strategy.get_parameter('long_window')}")
            print(f"持仓大小: {strategy.get_parameter('position_size')}")
        else:
            print("加载配置文件失败")
    else:
        print("配置文件不存在")
    print()


def example_validation():
    """参数验证示例"""
    print("=== 参数验证示例 ===")
    
    # 有效参数
    valid_params = {
        "short_window": 5,
        "long_window": 20,
        "position_size": 100,
        "min_hold_bars": 3,
        "signal_threshold": 0.01,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10
    }
    
    try:
        strategy = strategy_config_manager.create_strategy("dual_ma", valid_params)
        print("有效参数创建策略成功")
    except ValueError as e:
        print(f"意外错误: {e}")
    
    # 无效参数
    invalid_params = {
        "short_window": 20,  # 大于long_window
        "long_window": 10,   # 小于short_window
        "position_size": -1,  # 负数
        "signal_threshold": 0.5  # 超出范围
    }
    
    try:
        strategy = strategy_config_manager.create_strategy("dual_ma", invalid_params)
        print("无效参数创建策略成功（不应该发生）")
    except ValueError as e:
        print(f"无效参数正确抛出异常: {e}")
    print()


def example_strategy_usage():
    """策略使用示例"""
    print("=== 策略使用示例 ===")
    
    # 创建策略
    strategy = strategy_config_manager.create_strategy("dual_ma")
    strategy.initialize()
    
    # 创建模拟数据
    symbol = "000001.SZ"
    base_price = 10.0
    bars = []
    
    # 生成20天的模拟数据（前10天下跌，后10天上涨）
    for i in range(20):
        if i < 10:
            # 前10天下跌
            price = base_price - i * 0.1
        else:
            # 后10天上涨
            price = base_price - 10 * 0.1 + (i - 9) * 0.2
        
        bar = BarData(
            symbol=symbol,
            datetime=datetime.now() + timedelta(days=i),
            open=price - 0.05,
            high=price + 0.1,
            low=price - 0.1,
            close=price,
            volume=10000
        )
        bars.append(bar)
    
    # 处理数据
    for bar in bars:
        strategy.update_bar(bar)
    
    # 检查生成的信号
    signals = strategy.signals
    print(f"生成了 {len(signals)} 个信号")
    
    for i, signal in enumerate(signals):
        print(f"  信号 {i+1}: {signal.direction.value} @ {signal.price:.2f} - {signal.reason}")
    
    # 检查持仓
    position = strategy.get_position(symbol)
    print(f"最终持仓: {position.volume} 股")
    print()


def example_custom_config():
    """自定义配置示例"""
    print("=== 自定义配置示例 ===")
    
    # 创建自定义配置
    custom_config = {
        "strategies": {
            "dual_ma": {
                "name": "自定义双均线策略",
                "description": "使用自定义参数的双均线策略",
                "parameters": {
                    "short_window": 8,
                    "long_window": 25,
                    "position_size": 150
                }
            }
        }
    }
    
    # 保存到临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(custom_config, f, default_flow_style=False, allow_unicode=True)
        temp_file = f.name
    
    try:
        # 加载自定义配置
        success = strategy_config_manager.load_from_file(temp_file)
        if success:
            print("成功加载自定义配置")
            
            # 创建策略
            strategy = strategy_config_manager.create_strategy("dual_ma")
            print(f"自定义策略: {strategy.name}")
            print(f"短期窗口: {strategy.get_parameter('short_window')}")
            print(f"长期窗口: {strategy.get_parameter('long_window')}")
            print(f"持仓大小: {strategy.get_parameter('position_size')}")
        else:
            print("加载自定义配置失败")
    finally:
        import os
        os.unlink(temp_file)
    
    print()


def main():
    """主函数"""
    print("策略配置系统使用示例")
    print("=" * 50)
    
    try:
        example_basic_usage()
        example_parameter_info()
        example_config_file()
        example_validation()
        example_strategy_usage()
        example_custom_config()
        
        print("所有示例运行完成！")
        
    except Exception as e:
        print(f"示例运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()