#!/usr/bin/env python
"""
策略配置系统交互式命令行界面

提供用户友好的交互式界面，用于：
- 查看可用策略
- 配置策略参数
- 运行策略回测
- 查看回测结果
"""

import sys
from pathlib import Path
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.trading import strategy_config_manager
from src.trading.bar_data import BarData
from src.data.data_query import DataQuery
from src.data.data_fetcher import DataFetcher
from src.backtesting import BacktestEngine, BacktestConfig
from datetime import datetime, timedelta
import pandas as pd


class StrategyConfigCLI:
    """策略配置命令行界面"""
    
    def __init__(self):
        """初始化CLI"""
        self.data_query = DataQuery(db_path="data/stock_data.db")
        self.data_fetcher = DataFetcher()
        self.current_strategy = None
        self.current_symbol = None
        self.current_data = None
        self.backtest_result = None
        
        # 加载配置文件
        config_file = project_root / "config" / "strategies.yaml"
        if config_file.exists():
            strategy_config_manager.load_from_file(str(config_file))
    
    def show_banner(self):
        """显示欢迎横幅"""
        print("=" * 60)
        print("           策略配置系统交互式界面")
        print("=" * 60)
        print("功能：")
        print("  1. 查看可用策略")
        print("  2. 配置策略参数")
        print("  3. 选择股票和数据")
        print("  4. 运行策略回测")
        print("  5. 查看回测结果")
        print("  0. 退出")
        print("=" * 60)
    
    def show_available_strategies(self):
        """显示可用策略"""
        print("\n--- 可用策略 ---")
        strategies = strategy_config_manager.list_strategies()
        
        for i, strategy_id in enumerate(strategies, 1):
            config = strategy_config_manager.get_strategy_config(strategy_id)
            print(f"{i}. {strategy_id} - {config.name}")
            print(f"   描述: {config.description}")
        
        print()
    
    def configure_strategy(self):
        """配置策略"""
        print("\n--- 配置策略 ---")
        
        # 选择策略
        strategies = strategy_config_manager.list_strategies()
        if not strategies:
            print("没有可用策略")
            return
        
        print("可用策略:")
        for i, strategy_id in enumerate(strategies, 1):
            config = strategy_config_manager.get_strategy_config(strategy_id)
            print(f"{i}. {strategy_id} - {config.name}")
        
        try:
            choice = int(input("请选择策略 (输入数字): ")) - 1
            if choice < 0 or choice >= len(strategies):
                print("无效选择")
                return
            
            strategy_id = strategies[choice]
            config = strategy_config_manager.get_strategy_config(strategy_id)
            
            print(f"\n当前策略: {config.name}")
            print("当前参数:")
            
            # 显示当前参数
            param_info = strategy_config_manager.get_strategy_parameters_info(strategy_id)
            for name, info in param_info.items():
                current_value = config.default_parameters.get(name, info['default_value'])
                print(f"  {name}: {current_value} ({info['description']})")
            
            # 询问是否修改参数
            modify = input("\n是否修改参数? (y/n): ").lower()
            if modify == 'y':
                new_params = {}
                
                for name, info in param_info.items():
                    current_value = config.default_parameters.get(name, info['default_value'])
                    prompt = f"  {name} (当前: {current_value}, {info['description']})"
                    
                    if info['choices']:
                        print(f"    可选值: {info['choices']}")
                    
                    new_value = input(f"{prompt}: ").strip()
                    
                    if new_value:
                        # 类型转换
                        try:
                            if info['type'] == 'int':
                                new_value = int(new_value)
                            elif info['type'] == 'float':
                                new_value = float(new_value)
                            elif info['type'] == 'bool':
                                new_value = new_value.lower() in ['true', 'yes', '1']
                            
                            new_params[name] = new_value
                        except ValueError:
                            print(f"  无效值，保持原值: {current_value}")
                
                # 创建策略
                try:
                    self.current_strategy = strategy_config_manager.create_strategy(strategy_id, new_params)
                    print(f"\n✓ 策略配置成功: {self.current_strategy.name}")
                    print("新参数:")
                    for name, value in new_params.items():
                        print(f"  {name}: {value}")
                except ValueError as e:
                    print(f"\n✗ 策略配置失败: {e}")
                    return
            else:
                # 使用默认参数
                self.current_strategy = strategy_config_manager.create_strategy(strategy_id)
                print(f"\n✓ 使用默认参数创建策略: {self.current_strategy.name}")
            
            self.current_strategy.initialize()
            
        except ValueError:
            print("无效输入")
        
        print()
    
    def select_stock_and_data(self):
        """选择股票和数据"""
        print("\n--- 选择股票和数据 ---")
        
        # 输入股票代码
        symbol = input("请输入股票代码 (例如: 000001.SZ): ").strip()
        if not symbol:
            print("股票代码不能为空")
            return
        
        # 输入日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 默认90天
        
        start_str = input(f"开始日期 (默认: {start_date.strftime('%Y-%m-%d')}): ").strip()
        end_str = input(f"结束日期 (默认: {end_date.strftime('%Y-%m-%d')}): ").strip()
        
        try:
            if start_str:
                start_date = datetime.strptime(start_str, '%Y-%m-%d')
            if end_str:
                end_date = datetime.strptime(end_str, '%Y-%m-%d')
            
            # 获取数据
            print(f"\n正在获取 {symbol} 从 {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')} 的数据...")
            
            # 先尝试从本地数据库获取
            df = self.data_query.get_stock_daily(symbol, start_date, end_date)
            
            # 检查数据完整性
            if df.empty:
                print("本地数据库中没有找到数据，正在从数据源获取...")
                # 计算需要获取的天数
                days = (end_date - start_date).days
                success = self.data_fetcher.fetch_and_store_data(symbol, days)
                
                if success:
                    print("数据获取成功，正在从本地数据库读取...")
                    df = self.data_query.get_stock_daily(symbol, start_date, end_date)
                else:
                    print("从数据源获取数据失败")
                    return
            else:
                # 检查是否有缺失的数据
                expected_days = (end_date - start_date).days + 1
                actual_days = len(df)
                
                if actual_days < expected_days * 0.8:  # 如果实际数据少于期望的80%
                    print(f"本地数据不完整（{actual_days}/{expected_days}天），正在补充获取...")
                    
                    # 计算需要获取的天数
                    days = (end_date - start_date).days
                    success = self.data_fetcher.fetch_and_store_data(symbol, days)
                    
                    if success:
                        print("数据补充成功，正在重新读取...")
                        df = self.data_query.get_stock_daily(symbol, start_date, end_date)
                    else:
                        print("数据补充失败，使用现有数据")
            
            if df.empty:
                print("未获取到数据，请检查股票代码和日期范围")
                return
            
            self.current_symbol = symbol
            self.current_data = df
            
            print(f"✓ 成功获取 {len(df)} 条数据")
            print(f"  日期范围: {df.index[0]} 到 {df.index[-1]}")
            print(f"  价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
            
        except Exception as e:
            print(f"获取数据失败: {e}")
        
        print()
    
    def run_backtest(self):
        """运行回测"""
        print("\n--- 运行策略回测 ---")
        
        if not self.current_strategy:
            print("请先配置策略")
            return
        
        if self.current_data is None or self.current_data.empty:
            print("请先选择股票和数据")
            return
        
        # 获取回测配置
        try:
            print("\n回测配置:")
            
            # 获取初始资金
            initial_cash = input("请输入初始资金（默认100000）: ").strip()
            initial_cash = float(initial_cash) if initial_cash else 100000.0
            
            # 获取手续费率
            commission_rate = input("请输入手续费率（默认0.0003）: ").strip()
            commission_rate = float(commission_rate) if commission_rate else 0.0003
            
            # 获取滑点率
            slippage_rate = input("请输入滑点率（默认0.001）: ").strip()
            slippage_rate = float(slippage_rate) if slippage_rate else 0.001
            
            # 创建回测配置
            config = BacktestConfig(
                start_date=self.current_data.index[0],
                end_date=self.current_data.index[-1],
                initial_cash=initial_cash,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate
            )
            
            print(f"\n开始运行回测...")
            print(f"  策略: {self.current_strategy.name}")
            print(f"  股票: {self.current_symbol}")
            print(f"  时间范围: {config.start_date.strftime('%Y-%m-%d')} 到 {config.end_date.strftime('%Y-%m-%d')}")
            print(f"  初始资金: {initial_cash:.2f}")
            
            # 创建回测引擎
            engine = BacktestEngine(config)
            
            # 运行回测
            result = engine.run_backtest(self.current_strategy, [self.current_symbol])
            
            # 保存结果
            self.backtest_result = result
            
            # 显示结果
            result.print_summary()
            
        except Exception as e:
            print(f"回测失败: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    def show_backtest_results(self):
        """显示回测结果"""
        print("\n--- 回测结果 ---")
        
        if not hasattr(self, 'backtest_result') or self.backtest_result is None:
            print("请先运行回测")
            return
        
        result = self.backtest_result
        
        # 显示详细结果
        print(f"策略名称: {result.strategy_name}")
        print(f"股票代码: {', '.join(result.symbols)}")
        print(f"回测期间: {result.start_date.strftime('%Y-%m-%d')} 到 {result.end_date.strftime('%Y-%m-%d')}")
        
        print(f"\n收益指标:")
        print(f"  总收益率: {result.total_return:.2f}%")
        print(f"  年化收益率: {result.annual_return:.2f}%")
        print(f"  基准收益率: {result.metrics.benchmark_return:.2f}%")
        print(f"  超额收益率: {result.metrics.excess_return:.2f}%")
        
        print(f"\n风险指标:")
        print(f"  最大回撤: {result.metrics.max_drawdown:.2f}%")
        print(f"  年化波动率: {result.metrics.volatility:.2f}%")
        print(f"  夏普比率: {result.metrics.sharpe_ratio:.2f}")
        print(f"  卡玛比率: {result.metrics.calmar_ratio:.2f}")
        
        print(f"\n交易指标:")
        print(f"  总交易次数: {result.metrics.total_trades}")
        print(f"  胜率: {result.metrics.win_rate:.2f}%")
        print(f"  盈亏比: {result.metrics.profit_loss_ratio:.2f}")
        print(f"  平均每笔收益率: {result.metrics.avg_trade_return:.2f}%")
        
        # 显示交易记录
        if result.trades:
            print(f"\n交易记录（最近10笔）:")
            for i, trade in enumerate(result.trades[-10:]):
                direction = trade.get('direction', '')
                price = trade.get('price', 0)
                volume = trade.get('volume', 0)
                pnl = trade.get('pnl', 0)
                print(f"  {i+1}. {trade.get('datetime', '')} {direction} {volume}股 @ {price:.2f} 盈亏: {pnl:.2f}")
        
        # 显示信号统计
        if result.signals:
            buy_signals = [s for s in result.signals if s.direction.value == 'BUY']
            sell_signals = [s for s in result.signals if s.direction.value == 'SELL']
            
            print(f"\n信号统计:")
            print(f"  总信号数: {len(result.signals)}")
            print(f"  买入信号: {len(buy_signals)}")
            print(f"  卖出信号: {len(sell_signals)}")
        
        print()
    
    def run(self):
        """运行CLI"""
        while True:
            self.show_banner()
            
            try:
                choice = input("请选择功能 (输入数字): ").strip()
                
                if choice == '0':
                    print("感谢使用，再见！")
                    break
                elif choice == '1':
                    self.show_available_strategies()
                elif choice == '2':
                    self.configure_strategy()
                elif choice == '3':
                    self.select_stock_and_data()
                elif choice == '4':
                    self.run_backtest()
                elif choice == '5':
                    self.show_backtest_results()
                else:
                    print("无效选择，请重新输入")
                
                input("\n按回车键继续...")
                
            except KeyboardInterrupt:
                print("\n\n程序被用户中断")
                break
            except Exception as e:
                print(f"\n发生错误: {e}")
                input("\n按回车键继续...")


def main():
    """主函数"""
    cli = StrategyConfigCLI()
    cli.run()


if __name__ == "__main__":
    main()