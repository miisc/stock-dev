"""
数据模型定义
定义股票回测系统中使用的各种数据结构
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json


@dataclass
class StockData:
    """股票日线数据模型"""
    ts_code: str      # 股票代码 (如: 000001.SZ)
    trade_date: str   # 交易日期 (YYYYMMDD)
    open: float       # 开盘价
    high: float       # 最高价
    low: float        # 最低价
    close: float      # 收盘价
    volume: int       # 成交量
    amount: Optional[float] = None  # 成交额
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'trade_date': self.trade_date,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockData':
        """从字典创建实例"""
        return cls(
            ts_code=data['ts_code'],
            trade_date=data['trade_date'],
            open=float(data['open']),
            high=float(data['high']),
            low=float(data['low']),
            close=float(data['close']),
            volume=int(data['volume']),
            amount=float(data.get('amount', 0)) if data.get('amount') else None
        )
    
    def validate(self) -> bool:
        """验证数据有效性"""
        try:
            # 检查价格合理性
            if self.high < self.low:
                return False
            if not (self.low <= self.open <= self.high):
                return False
            if not (self.low <= self.close <= self.high):
                return False
            # 检查成交量非负
            if self.volume < 0:
                return False
            # 检查成交额非负
            if self.amount is not None and self.amount < 0:
                return False
            return True
        except (TypeError, ValueError):
            return False


@dataclass
class StockInfo:
    """股票基本信息模型"""
    ts_code: str      # 股票代码
    symbol: str       # 股票简称
    name: str         # 股票名称
    market: str       # 交易所 (SH/SZ)
    industry: Optional[str] = None     # 行业
    update_time: Optional[str] = None  # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'symbol': self.symbol,
            'name': self.name,
            'market': self.market,
            'industry': self.industry,
            'update_time': self.update_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockInfo':
        """从字典创建实例"""
        return cls(
            ts_code=data['ts_code'],
            symbol=data['symbol'],
            name=data['name'],
            market=data['market'],
            industry=data.get('industry'),
            update_time=data.get('update_time')
        )


@dataclass
class TradeRecord:
    """交易记录模型"""
    id: Optional[int] = None  # 记录ID
    ts_code: str = ""         # 股票代码
    direction: str = ""        # 交易方向 (BUY/SELL)
    price: float = 0.0        # 交易价格
    quantity: int = 0         # 交易数量
    amount: float = 0.0       # 交易金额
    trade_time: str = ""       # 交易时间
    strategy_id: str = ""      # 策略ID
    commission: float = 0.0    # 手续费
    notes: str = ""           # 备注
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'ts_code': self.ts_code,
            'direction': self.direction,
            'price': self.price,
            'quantity': self.quantity,
            'amount': self.amount,
            'trade_time': self.trade_time,
            'strategy_id': self.strategy_id,
            'commission': self.commission,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeRecord':
        """从字典创建实例"""
        return cls(
            id=data.get('id'),
            ts_code=data['ts_code'],
            direction=data['direction'],
            price=float(data['price']),
            quantity=int(data['quantity']),
            amount=float(data['amount']),
            trade_time=data['trade_time'],
            strategy_id=data['strategy_id'],
            commission=float(data.get('commission', 0)),
            notes=data.get('notes', '')
        )
    
    def validate(self) -> bool:
        """验证数据有效性"""
        try:
            # 检查交易方向
            if self.direction not in ['BUY', 'SELL']:
                return False
            # 检查价格和数量
            if self.price <= 0 or self.quantity <= 0:
                return False
            # 检查金额一致性
            if abs(self.amount - self.price * self.quantity) > 0.01:
                return False
            # 检查手续费非负
            if self.commission < 0:
                return False
            return True
        except (TypeError, ValueError):
            return False


@dataclass
class Signal:
    """策略信号模型"""
    symbol: str = ""          # 股票代码
    datetime: str = ""        # 信号时间
    direction: str = ""       # 信号方向 (BUY/SELL/HOLD)
    price: float = 0.0        # 参考价格
    quantity: int = 0         # 建议数量
    reason: str = ""          # 信号原因
    confidence: float = 1.0   # 信号置信度 (0-1)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'datetime': self.datetime,
            'direction': self.direction,
            'price': self.price,
            'quantity': self.quantity,
            'reason': self.reason,
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Signal':
        """从字典创建实例"""
        return cls(
            symbol=data['symbol'],
            datetime=data['datetime'],
            direction=data['direction'],
            price=float(data['price']),
            quantity=int(data['quantity']),
            reason=data['reason'],
            confidence=float(data.get('confidence', 1.0))
        )
    
    def validate(self) -> bool:
        """验证数据有效性"""
        try:
            # 检查信号方向
            if self.direction not in ['BUY', 'SELL', 'HOLD']:
                return False
            # 检查价格和数量
            if self.price <= 0 or self.quantity < 0:
                return False
            # 检查置信度范围
            if not (0 <= self.confidence <= 1):
                return False
            return True
        except (TypeError, ValueError):
            return False


@dataclass
class Position:
    """持仓信息模型"""
    ts_code: str = ""         # 股票代码
    quantity: int = 0         # 持仓数量
    avg_cost: float = 0.0     # 平均成本
    market_value: float = 0.0 # 市值
    last_update: str = ""     # 最后更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'ts_code': self.ts_code,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'market_value': self.market_value,
            'last_update': self.last_update
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Position':
        """从字典创建实例"""
        return cls(
            ts_code=data['ts_code'],
            quantity=int(data['quantity']),
            avg_cost=float(data['avg_cost']),
            market_value=float(data['market_value']),
            last_update=data['last_update']
        )
    
    def validate(self) -> bool:
        """验证数据有效性"""
        try:
            # 检查数量非负
            if self.quantity < 0:
                return False
            # 检查成本和市值非负
            if self.avg_cost < 0 or self.market_value < 0:
                return False
            return True
        except (TypeError, ValueError):
            return False


@dataclass
class Account:
    """账户信息模型"""
    id: int = 1              # 账户ID
    total_assets: float = 0.0    # 总资产
    available_cash: float = 0.0  # 可用资金
    position_value: float = 0.0  # 持仓市值
    total_profit: float = 0.0     # 总盈亏
    update_time: str = ""         # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'total_assets': self.total_assets,
            'available_cash': self.available_cash,
            'position_value': self.position_value,
            'total_profit': self.total_profit,
            'update_time': self.update_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Account':
        """从字典创建实例"""
        return cls(
            id=int(data.get('id', 1)),
            total_assets=float(data['total_assets']),
            available_cash=float(data['available_cash']),
            position_value=float(data['position_value']),
            total_profit=float(data['total_profit']),
            update_time=data['update_time']
        )
    
    def validate(self) -> bool:
        """验证数据有效性"""
        try:
            # 检查资产非负
            if any(x < 0 for x in [self.total_assets, self.available_cash, self.position_value]):
                return False
            # 检查资产一致性
            if abs(self.total_assets - (self.available_cash + self.position_value)) > 0.01:
                return False
            return True
        except (TypeError, ValueError):
            return False


@dataclass
class StrategyConfig:
    """策略配置模型"""
    id: str = ""              # 策略ID
    name: str = ""             # 策略名称
    description: str = ""      # 策略描述
    parameters: Dict[str, Any] = field(default_factory=dict)  # 策略参数
    is_active: bool = True     # 是否激活
    created_time: str = ""    # 创建时间
    updated_time: str = ""    # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'is_active': self.is_active,
            'created_time': self.created_time,
            'updated_time': self.updated_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyConfig':
        """从字典创建实例"""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            parameters=data.get('parameters', {}),
            is_active=bool(data.get('is_active', True)),
            created_time=data.get('created_time', ''),
            updated_time=data.get('updated_time', '')
        )
    
    def get_parameter(self, key: str, default: Any = None) -> Any:
        """获取参数值"""
        return self.parameters.get(key, default)
    
    def set_parameter(self, key: str, value: Any) -> None:
        """设置参数值"""
        self.parameters[key] = value


@dataclass
class BacktestResult:
    """回测结果模型"""
    strategy_name: str = ""           # 策略名称
    symbol: str = ""                 # 股票代码
    start_date: str = ""              # 开始日期
    end_date: str = ""                # 结束日期
    initial_capital: float = 0.0      # 初始资金
    final_capital: float = 0.0        # 最终资金
    total_return: float = 0.0         # 总收益率
    annual_return: float = 0.0        # 年化收益率
    max_drawdown: float = 0.0         # 最大回撤
    sharpe_ratio: float = 0.0         # 夏普比率
    win_rate: float = 0.0             # 胜率
    trade_records: List[TradeRecord] = field(default_factory=list)  # 交易记录
    portfolio_values: List[Dict[str, Any]] = field(default_factory=list)  # 组合价值
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'win_rate': self.win_rate,
            'trade_records': [record.to_dict() for record in self.trade_records],
            'portfolio_values': self.portfolio_values
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        """从字典创建实例"""
        trade_records = [TradeRecord.from_dict(record) for record in data.get('trade_records', [])]
        return cls(
            strategy_name=data['strategy_name'],
            symbol=data['symbol'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            initial_capital=float(data['initial_capital']),
            final_capital=float(data['final_capital']),
            total_return=float(data['total_return']),
            annual_return=float(data['annual_return']),
            max_drawdown=float(data['max_drawdown']),
            sharpe_ratio=float(data['sharpe_ratio']),
            win_rate=float(data['win_rate']),
            trade_records=trade_records,
            portfolio_values=data.get('portfolio_values', [])
        )


# 工具函数
def validate_data_list(data_list: List[Any]) -> bool:
    """验证数据列表中的所有数据"""
    for data in data_list:
        if hasattr(data, 'validate') and not data.validate():
            return False
    return True


def data_to_json(data: Any) -> str:
    """将数据对象转换为JSON字符串"""
    if hasattr(data, 'to_dict'):
        return json.dumps(data.to_dict(), ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, indent=2)


def json_to_data(json_str: str, model_class: type) -> Any:
    """将JSON字符串转换为数据对象"""
    data = json.loads(json_str)
    if hasattr(model_class, 'from_dict'):
        return model_class.from_dict(data)
    return data