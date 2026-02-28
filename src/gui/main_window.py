"""
主窗口

PyQt主界面，提供策略配置、数据管理、回测执行和结果展示功能
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QProgressBar, QMessageBox, QFileDialog,
    QSplitter, QGroupBox, QFormLayout, QHeaderView,
    QCheckBox, QDateEdit, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap

from ..trading import strategy_config_manager
from ..data.data_query import DataQuery
from ..data.data_fetcher import DataFetcher
from ..backtesting import BacktestEngine, BacktestConfig
from ..data.universe import manager as universe_manager
import threading
from .chart_widget import BacktestChartWidget


class BacktestThread(QThread):
    """回测线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int, str)  # current, total, message
    backtest_completed = pyqtSignal(object)  # 回测结果
    backtest_failed = pyqtSignal(str)  # 错误信息
    
    def __init__(self, config: BacktestConfig, strategy, symbols: List[str]):
        super().__init__()
        self.config = config
        self.strategy = strategy
        self.symbols = symbols
        self.engine = None
    
    def run(self):
        """运行回测"""
        try:
            # 创建回测引擎
            self.engine = BacktestEngine(self.config)
            
            # 设置进度回调
            def progress_callback(current, total):
                self.progress_updated.emit(current, total, f"处理中... {current}/{total}")
            
            self.config.progress_callback = progress_callback
            
            # 运行回测
            result = self.engine.run_backtest(self.strategy, self.symbols)
            
            # 发送完成信号
            self.backtest_completed.emit(result)
            
        except Exception as e:
            # 发送错误信号
            self.backtest_failed.emit(str(e))
    
    def stop(self):
        """停止回测"""
        if self.engine:
            # TODO: 实现回测停止逻辑
            pass


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("股票回测系统")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化组件
        self.data_query = DataQuery(db_path="data/stock_data.db")
        self.data_fetcher = DataFetcher()
        
        # 当前状态
        self.current_strategy = None
        self.current_symbol = None
        self.current_data = None
        self.backtest_result = None
        self.backtest_thread = None
        
        # 初始化UI
        self.init_ui()
        
        # 加载策略
        self.load_strategies()

        # 启动后自动从本地DB加载数据（延迟200ms等待UI完全渲染）
        QTimer.singleShot(200, self.auto_load_local_data)
        # 启动后后台检查并在需要时刷新股票池缓存（不阻塞UI）
        threading.Thread(target=lambda: universe_manager.get_pool('all', force_refresh=False), daemon=True).start()
    
    def init_ui(self):
        """初始化用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setSizes([400, 800])
    
    def create_left_panel(self):
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 策略配置页
        strategy_tab = self.create_strategy_tab()
        tab_widget.addTab(strategy_tab, "策略配置")
        
        # 数据管理页
        data_tab = self.create_data_tab()
        tab_widget.addTab(data_tab, "数据管理")
        
        # 回测配置页
        backtest_tab = self.create_backtest_tab()
        tab_widget.addTab(backtest_tab, "回测配置")
        
        return panel
    
    def create_right_panel(self):
        """创建右侧结果面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 数据预览页
        preview_tab = self.create_preview_tab()
        tab_widget.addTab(preview_tab, "数据预览")
        
        # 回测结果页
        results_tab = self.create_results_tab()
        tab_widget.addTab(results_tab, "回测结果")

        # 可视化图表页
        self.chart_widget = BacktestChartWidget()
        tab_widget.addTab(self.chart_widget, "📈 图表")
        self.right_tab_widget = tab_widget  # 保存引用以便跳转
        
        # 日志页
        log_tab = self.create_log_tab()
        tab_widget.addTab(log_tab, "日志")
        
        return panel
    
    def create_strategy_tab(self):
        """创建策略配置页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 策略选择
        strategy_group = QGroupBox("策略选择")
        strategy_layout = QFormLayout(strategy_group)
        
        self.strategy_combo = QComboBox()
        strategy_layout.addRow("策略:", self.strategy_combo)
        
        # 策略参数
        params_group = QGroupBox("策略参数")
        self.params_layout = QFormLayout(params_group)
        
        layout.addWidget(strategy_group)
        layout.addWidget(params_group)
        layout.addStretch()
        
        # 连接信号
        self.strategy_combo.currentIndexChanged.connect(self.on_strategy_changed)
        
        return widget
    
    def create_data_tab(self):
        """创建数据管理页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 股票选择
        symbol_group = QGroupBox("股票选择")
        symbol_layout = QFormLayout(symbol_group)
        
        self.symbol_edit = QLineEdit("000001.SZ")
        symbol_layout.addRow("股票代码:", self.symbol_edit)
        
        # 日期选择
        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        symbol_layout.addRow("开始日期:", self.start_date_edit)
        
        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit.setDate(QDate.currentDate())
        symbol_layout.addRow("结束日期:", self.end_date_edit)

        # 本地数据状态提示
        self.data_status_label = QLabel("本地数据: 未检查")
        self.data_status_label.setStyleSheet("color: gray; font-size: 11px;")
        symbol_layout.addRow("", self.data_status_label)

        # 从网络更新按钮（本地有数据时无需点击）
        self.fetch_button = QPushButton("从网络更新数据")
        self.fetch_button.clicked.connect(self.fetch_data)
        symbol_layout.addRow("", self.fetch_button)

        # 股票代码或日期变化时自动刷新本地数据
        self.symbol_edit.editingFinished.connect(self.auto_load_local_data)
        self.start_date_edit.dateChanged.connect(self.auto_load_local_data)
        self.end_date_edit.dateChanged.connect(self.auto_load_local_data)
        
        layout.addWidget(symbol_group)
        layout.addStretch()
        
        return widget
    
    def create_backtest_tab(self):
        """创建回测配置页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 回测参数
        config_group = QGroupBox("回测参数")
        config_layout = QFormLayout(config_group)
        
        self.initial_cash_spin = QDoubleSpinBox()
        self.initial_cash_spin.setRange(1000, 10000000)
        self.initial_cash_spin.setValue(100000)
        self.initial_cash_spin.setSuffix(" 元")
        config_layout.addRow("初始资金:", self.initial_cash_spin)
        
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setRange(0, 0.01)
        self.commission_spin.setValue(0.0003)
        self.commission_spin.setDecimals(4)
        self.commission_spin.setSingleStep(0.0001)
        config_layout.addRow("手续费率:", self.commission_spin)
        
        self.slippage_spin = QDoubleSpinBox()
        self.slippage_spin.setRange(0, 0.01)
        self.slippage_spin.setValue(0.001)
        self.slippage_spin.setDecimals(4)
        self.slippage_spin.setSingleStep(0.0001)
        config_layout.addRow("滑点率:", self.slippage_spin)
        
        # 运行按钮
        self.run_button = QPushButton("运行回测")
        self.run_button.clicked.connect(self.run_backtest)
        self.run_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        config_layout.addRow("", self.run_button)
        
        # 进度条
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        layout.addWidget(config_group)
        layout.addStretch()
        
        return widget
    
    def create_preview_tab(self):
        """创建数据预览页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.data_table)
        
        return widget
    
    def create_results_tab(self):
        """创建回测结果页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 结果表格
        self.results_table = QTableWidget()
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.results_table)
        
        return widget
    
    def create_log_tab(self):
        """创建日志页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)
        
        return widget
    
    def load_strategies(self):
        """加载可用策略"""
        try:
            strategies = strategy_config_manager.get_all_strategies()
            
            self.strategy_combo.clear()
            for name, config in strategies.items():
                self.strategy_combo.addItem(config['description'])
                self.strategy_combo.setItemData(self.strategy_combo.count() - 1, name)
            
            # 默认选择第一个策略
            if strategies:
                self.on_strategy_changed(self.strategy_combo.currentIndex())
                
        except Exception as e:
            self.log_message(f"加载策略失败: {e}")
    
    def on_strategy_changed(self, index):
        """策略改变事件"""
        if index < 0:
            return
        
        try:
            strategy_id = self.strategy_combo.itemData(index)
            if not strategy_id:
                strategy_id = list(strategy_config_manager.get_all_strategies().keys())[index]
            
            # 清除现有参数控件
            while self.params_layout.count():
                item = self.params_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 获取策略参数
            config = strategy_config_manager.get_strategy_config(strategy_id)
            if not config:
                self.log_message(f"未找到策略配置: {strategy_id}")
                return
            params = config.parameters
            
            # 创建参数控件
            self.param_widgets = {}
            for param_name, param_config in params.items():
                if param_config.type == int:
                    widget = QSpinBox()
                    widget.setRange(param_config.min_value or 0, param_config.max_value or 1000)
                    widget.setValue(param_config.default_value)
                elif param_config.type == float:
                    widget = QDoubleSpinBox()
                    widget.setRange(param_config.min_value or 0, param_config.max_value or 1000)
                    widget.setValue(param_config.default_value)
                    widget.setDecimals(4)
                else:  # string
                    widget = QLineEdit(str(param_config.default_value))
                
                self.param_widgets[param_name] = widget
                self.params_layout.addRow(f"{param_config.name}:", widget)
            
            # 保存当前策略
            self.current_strategy = strategy_config_manager.create_strategy(strategy_id)
            
        except Exception as e:
            self.log_message(f"加载策略参数失败: {e}")

    def auto_load_local_data(self):
        """启动时及代码/日期变更时，自动从本地DB静默加载数据（不访问网络）"""
        symbol = self.symbol_edit.text().strip()
        if not symbol:
            return

        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()

        try:
            df = self.data_query.get_stock_daily(symbol, start_date, end_date)
            if not df.empty:
                self.current_symbol = symbol
                self.current_data = df
                self.update_data_preview(df)
                self.data_status_label.setText(f"本地数据: {len(df)} 条记录 ✓")
                self.data_status_label.setStyleSheet("color: green; font-size: 11px;")
                self.log_message(f"已从本地加载 {symbol} 数据: {len(df)} 条记录")
            else:
                self.current_data = None
                self.data_status_label.setText('本地数据: 无，请点击"从网络更新数据"')
                self.data_status_label.setStyleSheet("color: orange; font-size: 11px;")
        except Exception:
            pass  # 静默失败，不打扰用户

    def fetch_data(self):
        """从网络获取并更新数据，同时保存到本地DB"""
        symbol = self.symbol_edit.text().strip()
        if not symbol:
            QMessageBox.warning(self, "警告", "请输入股票代码")
            return
        
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        
        self.log_message(f"从网络获取数据: {symbol}, {start_date} 到 {end_date}")
        self.fetch_button.setEnabled(False)
        self.fetch_button.setText("获取中...")
        
        try:
            days = (end_date - start_date).days
            success = self.data_fetcher.fetch_and_store_data(symbol, days)
            
            if success:
                self.log_message("网络数据获取成功，已保存到本地数据库")
            else:
                self.log_message("网络数据获取失败，尝试使用本地已有数据")

            # 无论网络成功与否，都从DB读取
            df = self.data_query.get_stock_daily(symbol, start_date, end_date)
            if not df.empty:
                self.current_symbol = symbol
                self.current_data = df
                self.update_data_preview(df)
                self.data_status_label.setText(f"本地数据: {len(df)} 条记录 ✓")
                self.data_status_label.setStyleSheet("color: green; font-size: 11px;")
                self.log_message(f"数据加载完成: {len(df)} 条记录")
            else:
                self.data_status_label.setText("本地数据: 无可用数据")
                self.data_status_label.setStyleSheet("color: red; font-size: 11px;")
                self.log_message("未能获取任何数据")
            
        except Exception as e:
            self.log_message(f"获取数据失败: {e}")
        finally:
            self.fetch_button.setEnabled(True)
            self.fetch_button.setText("从网络更新数据")
    
    def update_data_preview(self, df):
        """更新数据预览"""
        if df.empty:
            return
        
        # 设置表格
        self.data_table.setRowCount(min(100, len(df)))  # 最多显示100行
        self.data_table.setColumnCount(len(df.columns))
        self.data_table.setHorizontalHeaderLabels(df.columns.tolist())
        
        # 填充数据
        for i in range(min(100, len(df))):
            for j, col in enumerate(df.columns):
                value = df.iloc[i, j]
                item = QTableWidgetItem(str(value))
                self.data_table.setItem(i, j, item)
    
    def run_backtest(self):
        """运行回测"""
        if not self.current_strategy:
            QMessageBox.warning(self, "警告", "请先选择策略")
            return
        
        if self.current_data is None or self.current_data.empty:
            # 先尝试本地DB
            self.auto_load_local_data()

        if self.current_data is None or self.current_data.empty:
            # 本地也没有，自动从网络抓取
            self.log_message("本地无数据，自动从网络获取...")
            symbol = self.symbol_edit.text().strip()
            start_date = self.start_date_edit.date().toPyDate()
            end_date = self.end_date_edit.date().toPyDate()
            days = (end_date - start_date).days
            try:
                success = self.data_fetcher.fetch_and_store_data(symbol, days)
                if success:
                    self.auto_load_local_data()
            except Exception as e:
                self.log_message(f"自动获取数据失败: {e}")

        if self.current_data is None or self.current_data.empty:
            QMessageBox.warning(self, "警告", "无法获取数据，请检查股票代码或网络连接")
            return
        
        if self.backtest_thread and self.backtest_thread.isRunning():
            QMessageBox.warning(self, "警告", "回测正在运行中")
            return
        
        try:
            # 获取策略参数
            if hasattr(self, 'param_widgets'):
                params = {}
                for name, widget in self.param_widgets.items():
                    if hasattr(widget, 'value'):
                        params[name] = widget.value()
                    else:
                        params[name] = widget.text()
                
                # 更新策略参数
                self.current_strategy.set_parameters(params)
            
            # 创建回测配置
            config = BacktestConfig(
                start_date=self.current_data.index[0],
                end_date=self.current_data.index[-1],
                initial_cash=self.initial_cash_spin.value(),
                commission_rate=self.commission_spin.value(),
                slippage_rate=self.slippage_spin.value()
            )
            
            # 创建回测线程
            self.backtest_thread = BacktestThread(config, self.current_strategy, [self.current_symbol])
            
            # 连接信号
            self.backtest_thread.progress_updated.connect(self.update_progress)
            self.backtest_thread.backtest_completed.connect(self.on_backtest_completed)
            self.backtest_thread.backtest_failed.connect(self.on_backtest_failed)
            
            # 禁用运行按钮
            self.run_button.setEnabled(False)
            self.run_button.setText("运行中...")

            # 清空上次图表
            self.chart_widget.clear_charts()
            
            # 启动线程
            self.backtest_thread.start()
            
            self.log_message("开始运行回测...")
            
        except Exception as e:
            self.log_message(f"启动回测失败: {e}")
    
    def update_progress(self, current, total, message):
        """更新进度"""
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
        self.log_message(message)
    
    def on_backtest_completed(self, result):
        """回测完成"""
        # 保存结果
        self.backtest_result = result
        
        # 更新UI
        self.run_button.setEnabled(True)
        self.run_button.setText("运行回测")
        self.progress_bar.setValue(100)
        
        # 显示结果
        self.display_results(result)

        # 可视化图表
        self.chart_widget.update_charts(result, self.current_data)
        # 自动跳到图表页
        self.right_tab_widget.setCurrentWidget(self.chart_widget)
        
        self.log_message("回测完成!")
    
    def on_backtest_failed(self, error):
        """回测失败"""
        # 更新UI
        self.run_button.setEnabled(True)
        self.run_button.setText("运行回测")
        self.progress_bar.setValue(0)
        
        # 显示错误
        self.log_message(f"回测失败: {error}")
        QMessageBox.critical(self, "错误", f"回测失败: {error}")
    
    def display_results(self, result):
        """显示回测结果"""
        # 清除现有结果
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["指标", "值"])
        
        # 结果数据
        results_data = [
            ("策略名称", result.strategy_name),
            ("股票代码", ", ".join(result.symbols)),
            ("回测期间", f"{result.start_date.strftime('%Y-%m-%d')} 到 {result.end_date.strftime('%Y-%m-%d')}"),
            ("", ""),  # 分隔行
            ("总收益率", f"{result.total_return:.2f}%"),
            ("年化收益率", f"{result.annual_return:.2f}%"),
            ("基准收益率", f"{result.metrics.benchmark_return:.2f}%"),
            ("超额收益率", f"{result.metrics.excess_return:.2f}%"),
            ("", ""),  # 分隔行
            ("最大回撤", f"{result.metrics.max_drawdown:.2f}%"),
            ("年化波动率", f"{result.metrics.volatility:.2f}%"),
            ("夏普比率", f"{result.metrics.sharpe_ratio:.2f}"),
            ("卡玛比率", f"{result.metrics.calmar_ratio:.2f}"),
            ("", ""),  # 分隔行
            ("总交易次数", str(result.metrics.total_trades)),
            ("胜率", f"{result.metrics.win_rate:.2f}%"),
            ("盈亏比", f"{result.metrics.profit_loss_ratio:.2f}"),
            ("平均每笔收益率", f"{result.metrics.avg_trade_return:.2f}%"),
        ]
        
        # 填充结果
        self.results_table.setRowCount(len(results_data))
        for i, (key, value) in enumerate(results_data):
            key_item = QTableWidgetItem(key)
            value_item = QTableWidgetItem(str(value))
            
            # 设置分隔行样式
            if key == "":
                key_item.setBackground(Qt.lightGray)
                value_item.setBackground(Qt.lightGray)
            
            self.results_table.setItem(i, 0, key_item)
            self.results_table.setItem(i, 1, value_item)
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止回测线程
        if self.backtest_thread and self.backtest_thread.isRunning():
            self.backtest_thread.stop()
            self.backtest_thread.wait()
        
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用图标和样式
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()