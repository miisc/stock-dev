#!/usr/bin/env python
"""
策略配置系统测试脚本
"""

import sys
from pathlib import Path
import tempfile
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading.strategy_config import (
    StrategyConfig, StrategyParameter, StrategyConfigManager, strategy_config_manager
)
from src.trading import DualMovingAverageStrategy


def test_strategy_parameter():
    """测试策略参数"""
    print("测试策略参数")
    
    # 创建参数
    param = StrategyParameter(
        name="test_param",
        type=int,
        default_value=10,
        description="测试参数",
        min_value=1,
        max_value=100
    )
    
    # 测试有效值
    assert param.validate(10), "有效值应该通过验证"
    assert param.validate(50), "范围内的值应该通过验证"
    
    # 测试无效值
    assert not param.validate(0), "小于最小值的值应该不通过验证"
    assert not param.validate(101), "大于最大值的值应该不通过验证"
    assert not param.validate("invalid"), "错误类型的值应该不通过验证"
    
    print("✓ 策略参数测试通过")


def test_strategy_config():
    """测试策略配置"""
    print("测试策略配置")
    
    # 创建策略配置
    config = StrategyConfig(
        strategy_id="test_strategy",
        strategy_class=DualMovingAverageStrategy,
        name="测试策略",
        description="这是一个测试策略",
        parameters={
            "param1": StrategyParameter(
                name="param1",
                type=int,
                default_value=10,
                min_value=1,
                max_value=100
            ),
            "param2": StrategyParameter(
                name="param2",
                type=str,
                default_value="default",
                choices=["option1", "option2", "default"]
            )
        }
    )
    
    # 测试参数验证
    valid_params = {"param1": 20, "param2": "option1"}
    assert config.validate_parameters(valid_params), "有效参数应该通过验证"
    
    # 测试无效参数
    invalid_params = {"param1": 0, "param2": "invalid"}
    assert not config.validate_parameters(invalid_params), "无效参数应该不通过验证"
    
    # 测试策略创建
    strategy = config.create_strategy(valid_params)
    assert strategy.strategy_id == "test_strategy", "策略ID应该正确"
    assert strategy.get_parameter("param1") == 20, "参数1应该正确设置"
    assert strategy.get_parameter("param2") == "option1", "参数2应该正确设置"
    
    print("✓ 策略配置测试通过")


def test_strategy_config_manager():
    """测试策略配置管理器"""
    print("测试策略配置管理器")
    
    # 创建配置管理器
    manager = StrategyConfigManager()
    
    # 测试默认策略注册
    assert "dual_ma" in manager.list_strategies(), "默认应该注册双均线策略"
    
    # 测试获取策略配置
    config = manager.get_strategy_config("dual_ma")
    assert config is not None, "应该能获取双均线策略配置"
    assert config.strategy_id == "dual_ma", "策略ID应该正确"
    
    # 测试创建策略
    strategy = manager.create_strategy("dual_ma")
    assert strategy.strategy_id == "dual_ma", "创建的策略ID应该正确"
    assert strategy.name == "双均线策略", "策略名称应该正确"
    
    # 测试参数信息
    param_info = manager.get_strategy_parameters_info("dual_ma")
    assert param_info is not None, "应该能获取参数信息"
    assert "short_window" in param_info, "应该包含short_window参数"
    
    print("✓ 策略配置管理器测试通过")


def test_config_file_operations():
    """测试配置文件操作"""
    print("测试配置文件操作")
    
    # 创建临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        temp_config_path = f.name
        
        # 写入测试配置
        f.write("""
strategies:
  dual_ma:
    name: "双均线策略"
    description: "这是一个测试策略"
    parameters:
      short_window: 10
      long_window: 30
      position_size: 200
""")
    
    try:
        # 创建配置管理器并加载文件
        manager = StrategyConfigManager()
        success = manager.load_from_file(temp_config_path)
        assert success, "应该成功加载配置文件"
        
        # 检查配置是否加载
        config = manager.get_strategy_config("dual_ma")
        # 注意：只有已定义的参数才能被覆盖
        assert config.default_parameters["short_window"] == 10, "参数应该被覆盖"
        assert config.default_parameters["long_window"] == 30, "参数应该被覆盖"
        assert config.default_parameters["position_size"] == 200, "参数应该被覆盖"
        
        print("✓ 配置文件加载测试通过")
        
        # 测试保存配置
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_save_path = f.name
        
        try:
            success = manager.save_to_file(temp_save_path)
            assert success, "应该成功保存配置文件"
            
            # 检查文件是否存在
            assert os.path.exists(temp_save_path), "配置文件应该存在"
            
            print("✓ 配置文件保存测试通过")
            
        finally:
            if os.path.exists(temp_save_path):
                os.unlink(temp_save_path)
    
    finally:
        if os.path.exists(temp_config_path):
            os.unlink(temp_config_path)


def test_real_config_file():
    """测试真实配置文件"""
    print("测试真实配置文件")
    
    # 加载真实配置文件
    config_file = project_root / "config" / "strategies.yaml"
    if not config_file.exists():
        print("⚠️ 真实配置文件不存在，跳过测试")
        return
    
    manager = StrategyConfigManager()
    success = manager.load_from_file(str(config_file))
    assert success, "应该成功加载真实配置文件"
    
    # 测试创建不同配置的策略
    # 注意：只有注册的策略才能创建
    # 这里我们测试双均线策略的参数是否被正确更新
    strategy = manager.create_strategy("dual_ma")
    assert strategy.get_parameter("short_window") == 5, "默认参数应该保持不变"
    assert strategy.get_parameter("long_window") == 20, "默认参数应该保持不变"
    assert strategy.get_parameter("position_size") == 100, "默认参数应该保持不变"
    
    print("✓ 真实配置文件测试通过")


def test_strategy_factory():
    """测试策略工厂"""
    print("测试策略工厂")
    
    # 使用全局配置管理器
    strategy = strategy_config_manager.create_strategy("dual_ma", {
        "short_window": 8,
        "long_window": 25,
        "position_size": 150
    })
    
    assert strategy.strategy_id == "dual_ma", "策略ID应该正确"
    assert strategy.get_parameter("short_window") == 8, "短期窗口应该正确"
    assert strategy.get_parameter("long_window") == 25, "长期窗口应该正确"
    assert strategy.get_parameter("position_size") == 150, "持仓大小应该正确"
    
    print("✓ 策略工厂测试通过")


def test_parameter_validation():
    """测试参数验证"""
    print("测试参数验证")
    
    manager = StrategyConfigManager()
    
    # 测试有效参数
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
        strategy = manager.create_strategy("dual_ma", valid_params)
        assert strategy is not None, "有效参数应该能创建策略"
    except ValueError:
        assert False, "有效参数不应该抛出异常"
    
    # 测试无效参数
    invalid_params = {
        "short_window": 20,  # 大于long_window
        "long_window": 10,   # 小于short_window
        "position_size": -1,  # 负数
        "signal_threshold": 0.5  # 超出范围
    }
    
    try:
        strategy = manager.create_strategy("dual_ma", invalid_params)
        assert False, "无效参数应该抛出异常"
    except ValueError:
        pass  # 预期的异常
    
    print("✓ 参数验证测试通过")


def main():
    """主函数"""
    print("开始测试策略配置系统")
    
    try:
        test_strategy_parameter()
        test_strategy_config()
        test_strategy_config_manager()
        test_config_file_operations()
        test_real_config_file()
        test_strategy_factory()
        test_parameter_validation()
        
        print("\n🎉 所有策略配置系统测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 策略配置系统测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)