"""
主窗口（三标签页版本）

Tab1 数据管理   — universe_panel.UniversePanel
Tab2 策略回测   — backtest_panel.BacktestPanel
Tab3 结果查看   — result_panel.ResultPanel

数据流：
  UniversePanel.data_updated  → BacktestPanel.refresh_from_db()
  BacktestPanel.backtest_finished → ResultPanel.set_results() + 切换到 Tab3
"""

import sys
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QStatusBar, QLabel,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from ..data.universe import manager as universe_manager
from .universe_panel  import UniversePanel
from .backtest_panel  import BacktestPanel
from .result_panel    import ResultPanel
from .strategy_panel  import StrategyPanel
from .realtime_panel  import RealtimePanel
from .strategy_panel import StrategyPanel
from .realtime_panel import RealtimePanel


class MainWindow(QMainWindow):
    """主窗口 — 三标签页批量回测系统"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("股票批量回测系统")
        self.setGeometry(100, 80, 1280, 860)

        self._init_ui()

        # 启动后在后台刷新 universe 缓存，不阻塞 UI
        threading.Thread(
            target=lambda: universe_manager.get_pool("all", force_refresh=False),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # UI 初始化
    # ------------------------------------------------------------------

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 10))
        root.addWidget(self.tab_widget)

        # ── Tab1：数据管理 ─────────────────────────────────────────────
        self.universe_panel = UniversePanel()
        self.tab_widget.addTab(self.universe_panel, "📥 数据管理")

        # ── Tab2：策略回测 ─────────────────────────────────────────────
        self.backtest_panel = BacktestPanel()
        self.tab_widget.addTab(self.backtest_panel, "📊 策略回测")

        # ── Tab3：结果查看 ─────────────────────────────────────────────
        self.result_panel = ResultPanel()
        self.tab_widget.addTab(self.result_panel, "📈 结果查看")

        # ── Tab4：策略配置 ─────────────────────────────────────────────
        self.strategy_panel = StrategyPanel()
        self.tab_widget.addTab(self.strategy_panel, "⚙️ 策略配置")

        # ── Tab5：实时行情 ─────────────────────────────────────────────
        self.realtime_panel = RealtimePanel()
        self.tab_widget.addTab(self.realtime_panel, "📡 实时行情")

        # ── 跨面板信号连接 ────────────────────────────────────────────
        # 数据更新 → 回测面板刷新股票列表
        self.universe_panel.data_updated.connect(
            self.backtest_panel.refresh_from_db
        )
        # 回测完成 → 切换到结果页并更新数据
        self.backtest_panel.backtest_finished.connect(self._on_backtest_finished)

        # ── 状态栏 ────────────────────────────────────────────────────
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(
            QLabel("基于前复权数据 | 含幸存者偏差 | 结果仅供参考")
        )
        self.statusBar().setStyleSheet("color: #555;")

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _on_backtest_finished(self, results: list):
        """批量回测完成：推送结果到结果面板并切换标签"""
        self.result_panel.set_results(results)
        self.tab_widget.setCurrentWidget(self.result_panel)
        self.status_label.setText(f"回测完成：{len(results)} 只股票")


def main():
    """应用入口"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()