#!/usr/bin/env python
"""
策略基类测试脚本
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.trading import BarData, Signal, Direction, Strategy, Position, Account
from src.data.data_query import DataQuery
from src.common.config import Config


class TestStrategy(Strategy):
    """测试策略"""
    
    def on_init(self):
        """策略初始化"""
        self.logger.info("测试策略初始化")
        self.set_parameter("short_window", 5)
        self.set_parameter("long_window", 20)
    
    def on_bar(self, bar: BarData):
        """K线数据推送"""
        # 简单的测试逻辑：如果价格上涨，买入；如果价格下跌，卖出
        bars = self.get_bars(bar.symbol, 2)
        if len(bars) < 2:
            return
        
        prev_bar = bars[0]
        curr_bar = bars[1]
        
        # 计算价格变化
        price_change = curr_bar.close - prev_bar.close
        price_change_pct = price_change / prev_bar.close
        
        # 获取当前持仓
        position = self.get_position(bar.symbol)
        
        # 简单的交易逻辑
        if price_change_pct > 0.02 and not position.is_long:  # 上涨超过2%且没有多头持仓
            self.buy(bar.symbol, bar.close, 100, f"价格上涨{price_change_pct:.2%}")
        elif price_change_pct < -0.02 and position.is_long:  # 下跌超过2%且有多头持仓
            self.sell(bar.symbol, bar.close, position.volume, f"价格下跌{price_change_pct:.2%}")


def test_bar_data():
    """测试BarData数据结构"""
    print("测试BarData数据结构")
    
    # 创建测试数据
    bar = BarData(
        symbol="600036",
        datetime=datetime.now(),
        open=10.0,
        high=10.5,
        low=9.8,
        close=10.2,
        volume=1000000
    )
    
    # 测试属性
    assert bar.is_up == True, "应该是上涨"
    assert bar.is_down == False, "不应该是下跌"
    assert abs(bar.price_change - 0.2) < 0.0001, f"价格变动应该是0.2，实际是{bar.price_change}"
    assert abs(bar.price_change_pct - 0.02) < 0.0001, f"价格变动百分比应该是2%，实际是{bar.price_change_pct}"
    
    # 测试转换
    bar_dict = bar.to_dict()
    restored_bar = BarData.from_dict(bar_dict)
    assert restored_bar.symbol == bar.symbol, "恢复后代码应该相同"
    
    print("✓ BarData测试通过")


def test_signal():
    """测试Signal数据结构"""
    print("测试Signal数据结构")
    
    # 创建测试信号
    signal = Signal(
        symbol="600036",
        datetime=datetime.now(),
        direction=Direction.BUY,
        price=10.2,
        volume=1000,
        confidence=0.8,
        reason="测试买入"
    )
    
    # 测试属性
    assert signal.is_buy == True, "应该是买入信号"
    assert signal.is_sell == False, "不应该是卖出信号"
    assert signal.confidence == 0.8, "置信度应该是0.8"
    
    # 测试转换
    signal_dict = signal.to_dict()
    restored_signal = Signal.from_dict(signal_dict)
    assert restored_signal.direction == signal.direction, "恢复后方向应该相同"
    
    print("✓ Signal测试通过")


def test_position():
    """测试Position数据结构"""
    print("测试Position数据结构")
    
    # 创建测试持仓
    position = Position(
        symbol="600036",
        volume=1000,
        avg_price=10.0
    )
    
    # 测试属性
    assert position.is_long == True, "应该是多头持仓"
    assert position.is_short == False, "不应该是空头持仓"
    assert position.is_empty == False, "不应该是空仓"
    
    # 测试更新市值
    position.update_market_value(10.5)
    assert position.market_value == 10500, "市值应该是10500"
    
    print("✓ Position测试通过")


def test_account():
    """测试Account数据结构"""
    print("测试Account数据结构")
    
    # 创建测试账户
    account = Account(initial_capital=100000)
    
    # 测试属性
    assert account.cash == 100000, "初始资金应该是100000"
    assert account.total_assets == 100000, "总资产应该是100000"
    assert account.total_profit == 0, "总盈亏应该是0"
    
    # 测试更新持仓
    # 模拟买入操作：减少现金，增加持仓
    account.cash -= 10000  # 买入成本
    account.update_position("600036", 1000, 10.0)
    position = account.get_position("600036")
    position.update_market_value(10.5)
    
    assert account.position_value == 10500, "持仓市值应该是10500"
    assert account.total_assets == 90000 + 10500, f"总资产应该是100500，实际是{account.total_assets}"
    assert account.total_profit == 500, f"总盈亏应该是500，实际是{account.total_profit}"
    
    print("✓ Account测试通过")


def test_strategy():
    """测试策略基类"""
    print("测试策略基类")
    
    # 创建测试策略
    strategy = TestStrategy("test_strategy", "测试策略")
    
    # 测试初始化
    strategy.initialize()
    assert strategy.inited == True, "策略应该已初始化"
    assert strategy.get_parameter("short_window") == 5, "参数应该正确设置"
    
    # 测试生成信号
    signal = strategy.buy("600036", 10.0, 1000, "测试买入")
    assert signal.strategy_id == "test_strategy", "信号应该关联策略ID"
    assert len(strategy.signals) == 1, "应该有一个信号"
    
    # 测试执行信号
    result = strategy.execute_signal(signal, 10.0, 1000)
    assert result.executed == True, "信号应该已执行"
    assert len(strategy.signal_results) == 1, "应该有一个执行结果"
    assert strategy.account.cash == 90000, "现金应该减少"
    
    # 测试绩效摘要
    summary = strategy.get_performance_summary()
    assert summary['strategy_id'] == "test_strategy", "摘要应该包含策略ID"
    assert summary['signal_count'] == 1, "摘要应该包含信号数量"
    
    print("✓ Strategy测试通过")


def test_real_data():
    """测试真实数据"""
    print("测试真实数据")
    
    try:
        # 初始化数据查询器
        config = Config()
        query = DataQuery(config.get('database.path', 'data/stock_data.db'))
        
        # 获取招商银行最近10天数据
        df = query.get_stock_daily("600036")
        if df.empty:
            print("⚠️ 无法获取真实数据，跳过真实数据测试")
            return
        
        # 只取最近10条数据
        df = df.tail(10)
        
        # 创建策略
        strategy = TestStrategy("real_test", "真实数据测试")
        strategy.initialize()
        
        # 模拟数据推送
        for _, row in df.iterrows():
            bar = BarData.from_dataframe_row(row, "600036")
            strategy.update_bar(bar)
        
        # 检查结果
        summary = strategy.get_performance_summary()
        print(f"策略绩效摘要: {summary}")
        
        print("✓ 真实数据测试通过")
        
    except Exception as e:
        print(f"⚠️ 真实数据测试失败: {str(e)}")


def main():
    """主函数"""
    print("开始测试策略基类设计")
    
    try:
        test_bar_data()
        test_signal()
        test_position()
        test_account()
        test_strategy()
        test_real_data()
        
        print("\n🎉 所有策略基类测试通过！")
        return True
        
    except Exception as e:
        print(f"\n❌ 策略基类测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)