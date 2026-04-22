"""
批量结果汇总视图面板

接收 List[BacktestResult]，通过 ResultAggregator 构建汇总表，
提供可排序的 QTableWidget、整体胜率统计、CSV 导出，以及
点击单行展示该股票的详细图表。

页脚注明：基于前复权数据，含幸存者偏差，交易成本按实际配置计算。
"""
from __future__ import annotations

from typing import List, Optional
from pathlib import Path

import pandas as pd

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame, QGroupBox, QSplitter, QDialog,
    QDialogButtonBox,
)

from ..backtesting.result import BacktestResult
from ..analysis.aggregator import ResultAggregator
from ..data.data_query import DataQuery
from ..common.config import Config
from .chart_widget import BacktestChartWidget

# 显示列配置：(列头名称, DataFrame 列名, 是否为百分比列)
_COLUMNS = [
    ("代码",     "code",             False),
    ("策略",     "strategy",         False),
    ("总收益%",  "total_return",     True),
    ("年化%",    "annual_return",    True),
    ("最大回撤%","max_drawdown",     True),
    ("夏普",     "sharpe_ratio",     False),
    ("波动率%",  "volatility",       True),
    ("交易次数", "total_trades",     False),
    ("胜率%",    "win_rate",         True),
    ("盈亏比",   "profit_loss_ratio",False),
]


class _SortableItem(QTableWidgetItem):
    """支持数值排序的 TableWidgetItem"""
    def __init__(self, text: str, sort_key=None):
        super().__init__(text)
        self._sort_key = sort_key if sort_key is not None else text

    def __lt__(self, other):
        try:
            return float(self._sort_key) < float(other._sort_key)
        except (ValueError, TypeError):
            return str(self._sort_key) < str(other._sort_key)


class ResultPanel(QWidget):
    """批量回测汇总视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results: List[BacktestResult] = []
        self._agg: Optional[ResultAggregator] = None
        self._df: Optional[pd.DataFrame] = None
        self._init_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # ── 统计摘要行 ─────────────────────────────────────────────────
        summary_row = QHBoxLayout()

        self.total_label  = QLabel("股票数: 0")
        self.win_label    = QLabel("整体胜率: —")
        self.avg_sharpe   = QLabel("平均夏普: —")
        self.avg_return   = QLabel("平均年化: —")

        for lbl in (self.total_label, self.win_label, self.avg_sharpe, self.avg_return):
            lbl.setStyleSheet("font-weight:bold; padding: 0 12px;")

        summary_row.addWidget(self.total_label)
        summary_row.addWidget(self._vline())
        summary_row.addWidget(self.win_label)
        summary_row.addWidget(self._vline())
        summary_row.addWidget(self.avg_sharpe)
        summary_row.addWidget(self._vline())
        summary_row.addWidget(self.avg_return)
        summary_row.addStretch()

        root.addLayout(summary_row)

        # ── 工具栏 ─────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.export_btn = QPushButton("导出 CSV")
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(
            "QPushButton { background:#388E3C; color:white; padding:5px 12px; }"
            "QPushButton:hover { background:#2E7D32; }"
            "QPushButton:disabled { background:#aaa; }"
        )
        self.export_btn.clicked.connect(self._export_csv)

        self.chart_btn = QPushButton("查看图表")
        self.chart_btn.setEnabled(False)
        self.chart_btn.setStyleSheet(
            "QPushButton { background:#1565C0; color:white; padding:5px 12px; }"
            "QPushButton:hover { background:#0D47A1; }"
            "QPushButton:disabled { background:#aaa; }"
        )
        self.chart_btn.clicked.connect(self._show_selected_chart)

        self.hint_label = QLabel("点击列头排序 | 双击行查看详细图表")
        self.hint_label.setStyleSheet("color: gray; font-size: 11px;")

        toolbar.addWidget(self.export_btn)
        toolbar.addWidget(self.chart_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.hint_label)
        root.addLayout(toolbar)

        # ── 汇总表格 ───────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._show_selected_chart)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        root.addWidget(self.table)

        # ── 免责声明页脚 ───────────────────────────────────────────────
        footer = QLabel(
            "⚠ 以上数据基于前复权历史价格，含幸存者偏差（仅使用当前仍上市股票），"
            "交易成本按实际配置计算。回测结果不代表未来收益，仅供参考。"
        )
        footer.setStyleSheet(
            "color: #B71C1C; font-size: 11px; padding: 4px 0;"
        )
        footer.setWordWrap(True)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def set_results(self, results: List[BacktestResult]):
        """接收新的批量回测结果并刷新表格"""
        self._results = results
        if not results:
            self._clear_table()
            return

        self._agg = ResultAggregator(results)
        self._df  = self._agg.build_summary()
        self._populate_table(self._df)
        self._update_summary()

        self.export_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _populate_table(self, df: pd.DataFrame):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))

        for row_idx, row in df.iterrows():
            for col_idx, (header, col_name, is_pct) in enumerate(_COLUMNS):
                val = row.get(col_name, "")
                if isinstance(val, float):
                    text = f"{val:.2f}"
                else:
                    text = str(val)
                item = _SortableItem(text, val)
                item.setTextAlignment(Qt.AlignCenter)

                # 收益率上色：正绿负红
                if col_name in ("total_return", "annual_return") and isinstance(val, float):
                    if val > 0:
                        item.setForeground(QColor("#388E3C"))
                    elif val < 0:
                        item.setForeground(QColor("#C62828"))

                # 最大回撤：红色提示
                if col_name == "max_drawdown" and isinstance(val, float) and val > 20:
                    item.setForeground(QColor("#C62828"))

                self.table.setItem(row_idx, col_idx, item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _update_summary(self):
        if self._agg is None:
            return
        df = self._df
        n   = len(df)
        wr  = self._agg.overall_win_rate()
        avg_sharpe = df["sharpe_ratio"].mean() if "sharpe_ratio" in df else 0
        avg_ann    = df["annual_return"].mean() if "annual_return" in df else 0

        self.total_label.setText(f"股票数: {n}")
        self.win_label.setText(f"整体胜率: {wr:.1f}%")
        self.avg_sharpe.setText(f"平均夏普: {avg_sharpe:.2f}")
        self.avg_return.setText(f"平均年化: {avg_ann:.2f}%")

        color = "#2E7D32" if wr >= 50 else "#C62828"
        self.win_label.setStyleSheet(f"font-weight:bold; padding: 0 12px; color: {color};")

    def _clear_table(self):
        self.table.setRowCount(0)
        self.export_btn.setEnabled(False)
        self.chart_btn.setEnabled(False)

    def _on_selection_changed(self):
        self.chart_btn.setEnabled(bool(self.table.selectedItems()))

    def _export_csv(self):
        if self._df is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出汇总结果", "backtest_summary.csv", "CSV 文件 (*.csv)"
        )
        if not path:
            return
        try:
            self._agg.to_csv(path)
            QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _show_selected_chart(self):
        """弹出选中行股票的详细图表对话框"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row_idx = rows[0].row()
        if row_idx >= len(self._results):
            return
        result = self._results[row_idx]

        dlg = _ChartDialog(result, parent=self)
        dlg.exec_()

    @staticmethod
    def _vline() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFrameShadow(QFrame.Sunken)
        return f


# ─────────────────────────────────────────────────────────────────────────────
# 详细图表弹窗
# ─────────────────────────────────────────────────────────────────────────────

class _ChartDialog(QDialog):
    """展示单只股票回测详细图表的对话框"""

    def __init__(self, result: BacktestResult, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Window | Qt.WindowMinMaxButtonsHint)
        symbol = result.symbols[0] if result.symbols else "?"
        self.setWindowTitle(f"详细图表 — {symbol}")
        self.resize(1000, 650)

        layout = QVBoxLayout(self)

        # 指标摘要
        m = result.metrics
        summary = (
            f"总收益: {result.total_return:.2f}%  |  "
            f"年化: {result.annual_return:.2f}%  |  "
            f"最大回撤: {m.max_drawdown:.2f}%  |  "
            f"夏普: {m.sharpe_ratio:.2f}  |  "
            f"交易次数: {m.total_trades}  |  "
            f"胜率: {m.win_rate:.1f}%"
        )
        lbl = QLabel(summary)
        lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(lbl)

        # 从数据库获取 OHLC 数据
        price_df = self._load_price_data(result, symbol)

        # 图表
        chart = BacktestChartWidget()
        chart.update_charts(result, price_df)
        layout.addWidget(chart)

        # 关闭按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_price_data(self, result: BacktestResult, symbol: str) -> Optional[pd.DataFrame]:
        """从数据库加载股票 OHLC 数据"""
        try:
            # 获取数据库路径
            config = Config()
            db_path = config.get("database.path", "data/stock_data.db")
            
            # 直接转换为绝对路径，相对于项目根目录
            if not Path(db_path).is_absolute():
                db_path = str(Path.cwd() / db_path)
            
            query = DataQuery(db_path)
            
            # 获取回测期间的数据
            price_df = query.get_stock_daily(
                symbol,
                start_date=result.start_date,
                end_date=result.end_date
            )
            
            return price_df if not price_df.empty else None
        except Exception as e:
            from loguru import logger
            logger.warning(f"加载 OHLC 数据失败 ({symbol}): {str(e)}")
            return None
