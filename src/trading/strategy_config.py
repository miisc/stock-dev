"""
策略配置管理器

提供统一的策略配置管理功能，包括：
- 配置文件加载和保存
- 参数验证和默认值处理
- 策略工厂模式
- 配置热重载
"""

import os
import json
import yaml
from typing import Dict, Any, List, Optional, Type, Union
from pathlib import Path
from dataclasses import dataclass, field
from loguru import logger

from .strategy import Strategy
from .strategies import DualMovingAverageStrategy, RSIStrategy


@dataclass
class StrategyParameter:
    """策略参数定义"""
    name: str                                    # 参数名称
    type: Type                                   # 参数类型
    default_value: Any                            # 默认值
    description: str = ""                         # 参数描述
    min_value: Optional[Union[int, float]] = None  # 最小值
    max_value: Optional[Union[int, float]] = None  # 最大值
    choices: Optional[List[Any]] = None            # 可选值列表
    required: bool = True                         # 是否必需
    
    def validate(self, value: Any) -> bool:
        """
        验证参数值
        
        Args:
            value: 要验证的值
            
        Returns:
            是否有效
        """
        # 类型检查
        if not isinstance(value, self.type):
            try:
                value = self.type(value)
            except (ValueError, TypeError):
                logger.error(f"参数 {self.name} 类型错误，期望 {self.type.__name__}，实际 {type(value).__name__}")
                return False
        
        # 范围检查
        if self.min_value is not None and value < self.min_value:
            logger.error(f"参数 {self.name} 值 {value} 小于最小值 {self.min_value}")
            return False
        
        if self.max_value is not None and value > self.max_value:
            logger.error(f"参数 {self.name} 值 {value} 大于最大值 {self.max_value}")
            return False
        
        # 选择项检查
        if self.choices is not None and value not in self.choices:
            logger.error(f"参数 {self.name} 值 {value} 不在可选值列表中: {self.choices}")
            return False
        
        return True


@dataclass
class StrategyConfig:
    """策略配置定义"""
    strategy_id: str                              # 策略ID
    strategy_class: Type[Strategy]                  # 策略类
    name: str                                     # 策略名称
    description: str = ""                          # 策略描述
    parameters: Dict[str, StrategyParameter] = field(default_factory=dict)  # 参数定义
    default_parameters: Dict[str, Any] = field(default_factory=dict)  # 默认参数值
    
    def __post_init__(self):
        """初始化后处理"""
        # 如果没有提供默认参数，从参数定义中提取
        if not self.default_parameters:
            self.default_parameters = {
                name: param.default_value 
                for name, param in self.parameters.items()
            }
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        验证参数
        
        Args:
            parameters: 要验证的参数
            
        Returns:
            是否有效
        """
        # 检查必需参数
        for name, param in self.parameters.items():
            if param.required and name not in parameters:
                logger.error(f"缺少必需参数: {name}")
                return False
        
        # 验证每个参数
        for name, value in parameters.items():
            if name in self.parameters:
                if not self.parameters[name].validate(value):
                    return False
            else:
                logger.warning(f"未知参数: {name}")
        
        return True
    
    def get_parameter_info(self, name: str) -> Optional[StrategyParameter]:
        """
        获取参数信息
        
        Args:
            name: 参数名
            
        Returns:
            参数信息
        """
        return self.parameters.get(name)
    
    def create_strategy(self, parameters: Optional[Dict[str, Any]] = None) -> Strategy:
        """
        创建策略实例
        
        Args:
            parameters: 策略参数
            
        Returns:
            策略实例
        """
        # 使用默认参数
        final_params = self.default_parameters.copy()
        
        # 覆盖用户参数
        if parameters:
            final_params.update(parameters)
        
        # 验证参数
        if not self.validate_parameters(final_params):
            raise ValueError(f"策略 {self.strategy_id} 参数验证失败")
        
        # 创建策略实例
        return self.strategy_class(
            strategy_id=self.strategy_id,
            name=self.name,
            params=final_params
        )


class StrategyConfigManager:
    """策略配置管理器"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.strategies: Dict[str, StrategyConfig] = {}
        self.config_file: Optional[str] = None
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认策略"""
        # 注册双均线策略
        self.register_strategy(StrategyConfig(
            strategy_id="dual_ma",
            strategy_class=DualMovingAverageStrategy,
            name="双均线策略",
            description="基于短期和长期移动平均线交叉的趋势跟踪策略",
            parameters={
                "short_window": StrategyParameter(
                    name="short_window",
                    type=int,
                    default_value=5,
                    description="短期均线窗口",
                    min_value=1,
                    max_value=100
                ),
                "long_window": StrategyParameter(
                    name="long_window",
                    type=int,
                    default_value=20,
                    description="长期均线窗口",
                    min_value=1,
                    max_value=200
                ),
                "position_size": StrategyParameter(
                    name="position_size",
                    type=int,
                    default_value=100,
                    description="每次交易数量",
                    min_value=1,
                    max_value=10000
                ),
                "min_hold_bars": StrategyParameter(
                    name="min_hold_bars",
                    type=int,
                    default_value=3,
                    description="最少持仓K线数",
                    min_value=0,
                    max_value=100
                ),
                "signal_threshold": StrategyParameter(
                    name="signal_threshold",
                    type=float,
                    default_value=0.01,
                    description="信号确认阈值",
                    min_value=0.001,
                    max_value=0.1
                ),
                "stop_loss_pct": StrategyParameter(
                    name="stop_loss_pct",
                    type=float,
                    default_value=0.05,
                    description="止损百分比",
                    min_value=0.01,
                    max_value=0.5
                ),
                "take_profit_pct": StrategyParameter(
                    name="take_profit_pct",
                    type=float,
                    default_value=0.10,
                    description="止盈百分比",
                    min_value=0.01,
                    max_value=1.0
                )
            }
        ))

        # 注册 RSI 策略
        self.register_strategy(StrategyConfig(
            strategy_id="rsi",
            strategy_class=RSIStrategy,
            name="RSI 策略",
            description="基于相对强弱指数（RSI）的超买超卖均值回归策略",
            parameters={
                "rsi_period": StrategyParameter(
                    name="rsi_period",
                    type=int,
                    default_value=14,
                    description="RSI 计算周期",
                    min_value=2,
                    max_value=100
                ),
                "oversold": StrategyParameter(
                    name="oversold",
                    type=int,
                    default_value=30,
                    description="超卖阈值（RSI 低于此值视为超卖）",
                    min_value=1,
                    max_value=49
                ),
                "overbought": StrategyParameter(
                    name="overbought",
                    type=int,
                    default_value=70,
                    description="超买阈值（RSI 高于此值视为超买）",
                    min_value=51,
                    max_value=99
                ),
                "position_size": StrategyParameter(
                    name="position_size",
                    type=int,
                    default_value=100,
                    description="每次交易数量",
                    min_value=1,
                    max_value=10000
                ),
                "min_hold_bars": StrategyParameter(
                    name="min_hold_bars",
                    type=int,
                    default_value=3,
                    description="最少持仓 K 线数",
                    min_value=0,
                    max_value=100
                ),
                "stop_loss_pct": StrategyParameter(
                    name="stop_loss_pct",
                    type=float,
                    default_value=0.05,
                    description="止损百分比",
                    min_value=0.01,
                    max_value=0.5
                ),
                "take_profit_pct": StrategyParameter(
                    name="take_profit_pct",
                    type=float,
                    default_value=0.15,
                    description="止盈百分比",
                    min_value=0.01,
                    max_value=1.0
                ),
                "rsi_smooth": StrategyParameter(
                    name="rsi_smooth",
                    type=bool,
                    default_value=True,
                    description="使用 Wilder 平滑法（True）或简单均值（False）"
                )
            }
        ))

    def register_strategy(self, config: StrategyConfig):
        """
        注册策略配置
        
        Args:
            config: 策略配置
        """
        self.strategies[config.strategy_id] = config
        logger.info(f"注册策略配置: {config.strategy_id} - {config.name}")
    
    def get_strategy_config(self, strategy_id: str) -> Optional[StrategyConfig]:
        """
        获取策略配置
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略配置
        """
        return self.strategies.get(strategy_id)
    
    def list_strategies(self) -> List[str]:
        """
        列出所有注册的策略
        
        Returns:
            策略ID列表
        """
        return list(self.strategies.keys())
    
    def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有策略配置信息
        
        Returns:
            策略ID到配置信息的字典
        """
        result = {}
        for strategy_id, config in self.strategies.items():
            result[strategy_id] = {
                'name': config.name,
                'description': config.description,
                'parameters': {
                    param_name: {
                        'type': param.type.__name__,
                        'default_value': param.default_value,
                        'description': param.description,
                        'min_value': param.min_value,
                        'max_value': param.max_value
                    }
                    for param_name, param in config.parameters.items()
                }
            }
        return result
    
    def create_strategy(self, strategy_id: str, parameters: Optional[Dict[str, Any]] = None) -> Strategy:
        """
        创建策略实例
        
        Args:
            strategy_id: 策略ID
            parameters: 策略参数
            
        Returns:
            策略实例
        """
        config = self.get_strategy_config(strategy_id)
        if not config:
            raise ValueError(f"未找到策略配置: {strategy_id}")
        
        return config.create_strategy(parameters)
    
    def load_from_file(self, file_path: str) -> bool:
        """
        从文件加载配置
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            是否加载成功
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"配置文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    data = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    data = json.load(f)
                else:
                    logger.error(f"不支持的配置文件格式: {file_path.suffix}")
                    return False
            
            # 解析策略配置
            if 'strategies' in data:
                for strategy_id, strategy_data in data['strategies'].items():
                    self._parse_strategy_config(strategy_id, strategy_data)
            
            self.config_file = str(file_path)
            logger.info(f"成功加载配置文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            return False
    
    def _parse_strategy_config(self, strategy_id: str, strategy_data: Dict[str, Any]):
        """
        解析策略配置
        
        Args:
            strategy_id: 策略ID
            strategy_data: 策略数据
        """
        # 获取已注册的策略配置作为模板
        base_config = self.get_strategy_config(strategy_id)
        if not base_config:
            logger.warning(f"未注册的策略: {strategy_id}")
            return
        
        # 更新默认参数
        if 'parameters' in strategy_data:
            base_config.default_parameters.update(strategy_data['parameters'])
        
        # 更新策略信息
        if 'name' in strategy_data:
            base_config.name = strategy_data['name']
        
        if 'description' in strategy_data:
            base_config.description = strategy_data['description']
    
    def save_to_file(self, file_path: str) -> bool:
        """
        保存配置到文件
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            是否保存成功
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 构建配置数据
            config_data = {
                'strategies': {}
            }
            
            for strategy_id, config in self.strategies.items():
                config_data['strategies'][strategy_id] = {
                    'name': config.name,
                    'description': config.description,
                    'parameters': config.default_parameters
                }
            
            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                if file_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                elif file_path.suffix.lower() == '.json':
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                else:
                    logger.error(f"不支持的配置文件格式: {file_path.suffix}")
                    return False
            
            logger.info(f"成功保存配置文件: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {str(e)}")
            return False
    
    def reload_config(self) -> bool:
        """
        重新加载配置文件
        
        Returns:
            是否重载成功
        """
        if not self.config_file:
            logger.warning("没有配置文件可重载")
            return False
        
        return self.load_from_file(self.config_file)
    
    def get_strategy_parameters_info(self, strategy_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        获取策略参数信息
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            参数信息字典
        """
        config = self.get_strategy_config(strategy_id)
        if not config:
            return None
        
        result = {}
        for name, param in config.parameters.items():
            result[name] = {
                'type': param.type.__name__,
                'default_value': param.default_value,
                'description': param.description,
                'min_value': param.min_value,
                'max_value': param.max_value,
                'choices': param.choices,
                'required': param.required
            }
        
        return result


# 全局配置管理器实例
strategy_config_manager = StrategyConfigManager()