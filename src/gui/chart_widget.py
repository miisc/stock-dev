"""
回测结果可视化组件

提供基于 matplotlib 的嵌入式图表控件：
  - BacktestChartWidget  : 主容器，含「权益曲线」「信号K线」「收益分布」三个子图页
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import matplotlib
matplotlib.use("Qt5Agg")  # 必须在 pyplot 之前设置

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea,
    QLabel, QPushButton, QSizePolicy, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

if TYPE_CHECKING:
    from ..backtesting.result import BacktestResult

# ── 中文字体设置 ─────────────────────────────────────────────────────────────
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _apply_dark_style(fig: Figure, axes) -> None:
    """统一暗色背景风格"""
    bg = "#1e2130"
    ax_bg = "#262d3f"
    grid_color = "#3a4060"
    text_color = "#c8ccd8"

    fig.patch.set_facecolor(bg)
    ax_list = axes if hasattr(axes, "__iter__") else [axes]
    for ax in ax_list:
        ax.set_facecolor(ax_bg)
        ax.tick_params(colors=text_color, labelsize=8)
        ax.xaxis.label.set_color(text_color)
        ax.yaxis.label.set_color(text_color)
        ax.title.set_color(text_color)
        ax.spines[:].set_edgecolor(grid_color)
        ax.grid(True, color=grid_color, linewidth=0.5, linestyle="--", alpha=0.6)


# ─────────────────────────────────────────────────────────────────────────────
# 单个 Figure 控件基类
# ─────────────────────────────────────────────────────────────────────────────

class _BaseFigureWidget(QWidget):
    """包含 FigureCanvas + NavigationToolbar 的基础控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

    def _redraw(self):
        self.canvas.draw()

    def clear(self):
        self.figure.clear()
        self.canvas.draw()


# ─────────────────────────────────────────────────────────────────────────────
# 图1：权益曲线 + 回撤 + 持仓详情表
# ─────────────────────────────────────────────────────────────────────────────

class EquityCurveWidget(QWidget):
    """权益曲线（上）+ 回撤（中）+ 持仓详情表（下）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 图表部分
        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")
        
        chart_layout = QVBoxLayout()
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(toolbar)
        chart_layout.addWidget(self.canvas)
        
        layout.addLayout(chart_layout, stretch=2)
        
        # 持仓表格部分
        table_label = QLabel("持仓详情")
        table_label.setStyleSheet("color: #c8ccd8; font-weight: bold; padding: 4px;")
        layout.addWidget(table_label)
        
        self.position_table = QTableWidget(0, 6)
        self.position_table.setHorizontalHeaderLabels(["日期", "代码", "数量", "成本价", "当前价", "浮动盈亏"])
        self.position_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.position_table.setMaximumHeight(150)
        self.position_table.setStyleSheet(
            "QTableWidget { background: #262d3f; color: #c8ccd8; gridline-color: #3a4060; }"
            "QHeaderView::section { background: #1e2130; color: #c8ccd8; padding: 4px; border: 1px solid #3a4060; }"
        )
        layout.addWidget(self.position_table, stretch=1)

    def plot(self, result: "BacktestResult") -> None:
        self.figure.clear()

        equity = result.equity_curve
        if equity.empty:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "暂无权益曲线数据", ha="center", va="center",
                    fontsize=14, color="#888")
            _apply_dark_style(self.figure, [ax])
            self.canvas.draw()
            return

        # 确保索引是日期类型
        if not isinstance(equity.index, pd.DatetimeIndex):
            equity.index = pd.to_datetime(equity.index)

        gs = self.figure.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
        ax_eq = self.figure.add_subplot(gs[0])
        ax_dd = self.figure.add_subplot(gs[1], sharex=ax_eq)

        # —— 权益曲线 ——
        cum_return = equity.get("cumulative_return", None)
        if cum_return is not None:
            ax_eq.plot(equity.index, cum_return, color="#4fc3f7", linewidth=1.5,
                       label="累计收益率 (%)")
            ax_eq.axhline(0, color="#888", linewidth=0.8, linestyle="--")
            ax_eq.fill_between(equity.index, cum_return, 0,
                                where=(cum_return >= 0), alpha=0.15, color="#4fc3f7")
            ax_eq.fill_between(equity.index, cum_return, 0,
                                where=(cum_return < 0), alpha=0.15, color="#ef5350")
            ax_eq.set_ylabel("累计收益率 (%)")
        else:
            # fallback: 绘制净值
            total_value = equity.get("total_value", equity.iloc[:, 0])
            ax_eq.plot(equity.index, total_value, color="#4fc3f7", linewidth=1.5,
                       label="组合价值")
            ax_eq.set_ylabel("组合价值 (元)")

        ax_eq.set_title(f"权益曲线 — {result.strategy_name}")
        ax_eq.legend(loc="upper left", fontsize=8, framealpha=0.3)

        # —— 统计标注 ——
        m = result.metrics
        stats_txt = (
            f"总收益: {result.total_return:.2f}%  |  "
            f"年化: {result.annual_return:.2f}%  |  "
            f"夏普: {m.sharpe_ratio:.2f}  |  "
            f"最大回撤: {m.max_drawdown:.2f}%"
        )
        ax_eq.text(0.01, 0.02, stats_txt, transform=ax_eq.transAxes,
                   fontsize=8, color="#aaa", verticalalignment="bottom")

        # —— 回撤 ——
        total_value_col = equity.get("total_value",
                                     equity.iloc[:, 0] if not equity.empty else None)
        if total_value_col is not None:
            roll_max = total_value_col.cummax()
            drawdown = (total_value_col - roll_max) / roll_max * 100
            ax_dd.fill_between(equity.index, drawdown, 0, color="#ef5350", alpha=0.6)
            ax_dd.set_ylabel("回撤 (%)")
        ax_dd.set_xlabel("日期")

        # X 轴日期格式
        ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax_dd.xaxis.set_major_locator(mdates.AutoDateLocator())
        self.figure.autofmt_xdate(rotation=30)

        _apply_dark_style(self.figure, [ax_eq, ax_dd])
        self.canvas.draw()
        
        # 填充持仓表格
        self._populate_position_table(result)

    def _populate_position_table(self, result: "BacktestResult") -> None:
        """填充持仓详情表格"""
        self.position_table.setRowCount(0)
        
        if not result.daily_portfolio:
            return
        
        # 收集所有有持仓的日期和持仓信息
        rows = []
        for daily_record in result.daily_portfolio:
            positions = daily_record.get('positions', [])
            if not positions:
                continue
            
            date = daily_record.get('date')
            if date is None:
                continue
            
            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date).split(' ')[0]
            
            for pos in positions:
                symbol = pos.get('symbol', '')
                volume = pos.get('volume', 0)
                avg_price = pos.get('avg_price', 0)
                market_value = pos.get('market_value', 0)
                
                if volume == 0:
                    continue
                
                # 计算当前价 = market_value / volume
                current_price = market_value / abs(volume) if volume != 0 else 0
                
                # 浮动盈亏 = (当前价 - 成本价) × 数量
                floating_pnl = (current_price - avg_price) * volume
                
                rows.append({
                    'date': date_str,
                    'symbol': symbol,
                    'volume': volume,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'floating_pnl': floating_pnl,
                })
        
        # 显示表格
        self.position_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            # 日期
            item_date = QTableWidgetItem(row_data['date'])
            item_date.setTextAlignment(Qt.AlignCenter)
            self.position_table.setItem(row_idx, 0, item_date)
            
            # 代码
            item_symbol = QTableWidgetItem(row_data['symbol'])
            item_symbol.setTextAlignment(Qt.AlignCenter)
            self.position_table.setItem(row_idx, 1, item_symbol)
            
            # 数量
            item_volume = QTableWidgetItem(str(int(row_data['volume'])))
            item_volume.setTextAlignment(Qt.AlignCenter)
            self.position_table.setItem(row_idx, 2, item_volume)
            
            # 成本价
            item_cost = QTableWidgetItem(f"{row_data['avg_price']:.2f}")
            item_cost.setTextAlignment(Qt.AlignCenter)
            self.position_table.setItem(row_idx, 3, item_cost)
            
            # 当前价
            item_current = QTableWidgetItem(f"{row_data['current_price']:.2f}")
            item_current.setTextAlignment(Qt.AlignCenter)
            self.position_table.setItem(row_idx, 4, item_current)
            
            # 浮动盈亏
            pnl = row_data['floating_pnl']
            pnl_text = f"{pnl:.2f}"
            item_pnl = QTableWidgetItem(pnl_text)
            item_pnl.setTextAlignment(Qt.AlignCenter)
            if pnl > 0:
                item_pnl.setForeground(QColor("#66bb6a"))  # 绿色
            elif pnl < 0:
                item_pnl.setForeground(QColor("#ef5350"))  # 红色
            self.position_table.setItem(row_idx, 5, item_pnl)

    def clear(self):
        self.figure.clear()
        self.canvas.draw()
        self.position_table.setRowCount(0)


# ─────────────────────────────────────────────────────────────────────────────
# 图2：价格 + 交易信号
# ─────────────────────────────────────────────────────────────────────────────

class PriceSignalWidget(_BaseFigureWidget):
    """收盘价折线 + 买卖信号标记"""

    def plot(self, result: "BacktestResult", price_df: Optional[pd.DataFrame] = None) -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # ── 价格数据 ──
        if price_df is not None and not price_df.empty:
            close_col = None
            for candidate in ["close", "收盘", "close_price"]:
                if candidate in price_df.columns:
                    close_col = candidate
                    break
            if close_col is None and not price_df.empty:
                close_col = price_df.select_dtypes(include=[np.number]).columns[0]

            if close_col:
                idx = pd.to_datetime(price_df.index) if not isinstance(
                    price_df.index, pd.DatetimeIndex) else price_df.index
                ax.plot(idx, price_df[close_col], color="#90caf9",
                        linewidth=1.2, label="收盘价", zorder=2)
                ax.set_ylabel("价格 (元)")

        # ── 交易信号 ──
        signals = result.signals or []
        buy_times, buy_prices = [], []
        sell_times, sell_prices = [], []

        for sig in signals:
            if not hasattr(sig, "timestamp") or not hasattr(sig, "price"):
                continue
            t = pd.to_datetime(sig.timestamp)
            p = sig.price
            direction = getattr(sig, "direction", None)
            if direction is None:
                continue
            # 支持枚举和字符串两种形式
            d_str = direction.value if hasattr(direction, "value") else str(direction)
            if "long" in d_str.lower() or "buy" in d_str.lower():
                buy_times.append(t)
                buy_prices.append(p)
            elif "short" in d_str.lower() or "sell" in d_str.lower():
                sell_times.append(t)
                sell_prices.append(p)

        if buy_times:
            ax.scatter(buy_times, buy_prices, marker="^", color="#66bb6a",
                       s=80, zorder=5, label=f"买入 ({len(buy_times)})")
        if sell_times:
            ax.scatter(sell_times, sell_prices, marker="v", color="#ef5350",
                       s=80, zorder=5, label=f"卖出 ({len(sell_times)})")

        if not buy_times and not sell_times and (price_df is None or price_df.empty):
            ax.text(0.5, 0.5, "暂无价格/信号数据", ha="center", va="center",
                    fontsize=14, color="#888")

        ax.set_title(f"交易信号 — {', '.join(result.symbols)}")
        # 只在有带 label 的 artist 时才显示图例，避免 UserWarning
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        self.figure.autofmt_xdate(rotation=30)

        _apply_dark_style(self.figure, [ax])
        self._redraw()


# ─────────────────────────────────────────────────────────────────────────────
# 图3：交易详情（逐笔盈亏图 + 明细表）
# ─────────────────────────────────────────────────────────────────────────────

class TradeDetailWidget(QWidget):
    """交易详情：左侧逐笔盈亏图，右侧交易明细表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_rows = []
        self._filtered_rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header_row = QHBoxLayout()
        self.title_label = QLabel("交易详情")
        self.title_label.setStyleSheet("color: #c8ccd8; font-weight: bold; padding: 4px;")

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #9aa3b2; padding: 4px;")

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "仅盈利", "仅亏损"])
        self.filter_combo.setStyleSheet(
            "QComboBox { background: #262d3f; color: #c8ccd8; border: 1px solid #3a4060; padding: 2px 8px; }"
            "QComboBox QAbstractItemView { background: #262d3f; color: #c8ccd8; }"
        )
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)

        header_row.addWidget(self.title_label)
        header_row.addStretch()
        header_row.addWidget(self.stats_label)
        header_row.addWidget(self.filter_combo)
        layout.addLayout(header_row)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background: #3a4060; }")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")
        left_layout.addWidget(toolbar)
        left_layout.addWidget(self.canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["交易日期", "买卖方向", "数量", "价格", "盈亏(元)", "收益率(%)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setStyleSheet(
            "QTableWidget { background: #262d3f; color: #c8ccd8; gridline-color: #3a4060; }"
            "QHeaderView::section { background: #1e2130; color: #c8ccd8; padding: 4px; border: 1px solid #3a4060; }"
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        right_layout.addWidget(self.table)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([560, 640])
        layout.addWidget(splitter)

        self.canvas.mpl_connect("button_press_event", self._on_chart_click)

    def plot(self, result: "BacktestResult") -> None:
        """填充交易详情图表和表格"""
        trades = result.trades or []
        rows = []

        for trade in trades:
            dt = trade.get("datetime") or trade.get("timestamp")
            dt_ts = pd.to_datetime(dt, errors="coerce")
            date_str = dt_ts.strftime("%Y-%m-%d") if pd.notna(dt_ts) else ""

            direction = trade.get("direction", "")
            direction_str = "B" if "BUY" in str(direction).upper() else "S"

            volume = trade.get("volume", trade.get("quantity", 0)) or 0
            price = float(trade.get("price", 0) or 0)
            pnl = float(trade.get("pnl", 0) or 0)
            ret = float(trade.get("return_pct", 0) or 0)

            rows.append({
                "dt": dt_ts,
                "date": date_str,
                "direction": direction_str,
                "volume": int(volume),
                "price": price,
                "pnl": pnl,
                "ret": ret,
            })

        rows.sort(key=lambda x: x["dt"] if pd.notna(x["dt"]) else pd.Timestamp.min)
        self._all_rows = rows
        self._apply_filter()

    def clear(self):
        self._all_rows = []
        self._filtered_rows = []
        self.title_label.setText("交易详情")
        self.stats_label.setText("")
        self.table.setRowCount(0)
        self.figure.clear()
        self.canvas.draw()

    def _apply_filter(self):
        mode = self.filter_combo.currentText()
        if mode == "仅盈利":
            rows = [r for r in self._all_rows if r["pnl"] > 0]
        elif mode == "仅亏损":
            rows = [r for r in self._all_rows if r["pnl"] < 0]
        else:
            rows = list(self._all_rows)

        self._filtered_rows = rows
        self._populate_table(rows)
        self._render_pnl_chart(rows)
        self._update_summary(rows)

    def _populate_table(self, rows):
        # 计算已实现盈亏汇总（仅卖出笔）
        sell_rows = [r for r in rows if r["direction"] == "S"]
        total_realized_pnl = sum(r["pnl"] for r in sell_rows)
        win_count = sum(1 for r in sell_rows if r["pnl"] > 0)
        loss_count = sum(1 for r in sell_rows if r["pnl"] < 0)

        # 交易行 + 1行汇总
        self.table.setRowCount(len(rows) + 1)
        for row_idx, row in enumerate(rows):
            item_date = QTableWidgetItem(row["date"])
            item_date.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, item_date)

            item_dir = QTableWidgetItem(row["direction"])
            item_dir.setTextAlignment(Qt.AlignCenter)
            item_dir.setForeground(QColor("#66bb6a") if row["direction"] == "B" else QColor("#ef5350"))
            self.table.setItem(row_idx, 1, item_dir)

            item_qty = QTableWidgetItem(str(row["volume"]))
            item_qty.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, item_qty)

            item_price = QTableWidgetItem(f"{row['price']:.2f}")
            item_price.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, item_price)

            # 已实现盈亏和收益率仅在卖出笔显示，买入笔显示“-”
            if row["direction"] == "S":
                item_pnl = QTableWidgetItem(f"{row['pnl']:.2f}")
                item_pnl.setTextAlignment(Qt.AlignCenter)
                if row["pnl"] > 0:
                    item_pnl.setForeground(QColor("#66bb6a"))
                elif row["pnl"] < 0:
                    item_pnl.setForeground(QColor("#ef5350"))
                self.table.setItem(row_idx, 4, item_pnl)

                item_ret = QTableWidgetItem(f"{row['ret']:.2f}")
                item_ret.setTextAlignment(Qt.AlignCenter)
                if row["ret"] > 0:
                    item_ret.setForeground(QColor("#66bb6a"))
                elif row["ret"] < 0:
                    item_ret.setForeground(QColor("#ef5350"))
                self.table.setItem(row_idx, 5, item_ret)
            else:
                for col in (4, 5):
                    item_dash = QTableWidgetItem("-")
                    item_dash.setTextAlignment(Qt.AlignCenter)
                    item_dash.setForeground(QColor("#9aa3b2"))
                    self.table.setItem(row_idx, col, item_dash)

        # 汇总行
        summary_row = len(rows)
        pnl_color = "#66bb6a" if total_realized_pnl >= 0 else "#ef5350"
        summary_labels = [
            ("合计", 0),
            (f"卖出 {len(sell_rows)} 笔", 1),
            (f"盈 {win_count} / 亏 {loss_count}", 2),
            ("已实现盈亏", 3),
            (f"{total_realized_pnl:.2f}", 4),
            ("", 5),
        ]
        for text, col in summary_labels:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(Qt.ItemIsEnabled)  # 不可选中
            if col == 4:
                item.setForeground(QColor(pnl_color))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setForeground(QColor("#9aa3b2"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.table.setItem(summary_row, col, item)

    def _render_pnl_chart(self, rows, selected_idx=None):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        if not rows:
            ax.text(0.5, 0.5, "暂无交易记录", ha="center", va="center", fontsize=14, color="#888")
            _apply_dark_style(self.figure, [ax])
            self.canvas.draw()
            self.title_label.setText("交易详情")
            return

        pnl = np.array([r["pnl"] for r in rows], dtype=float)
        x = np.arange(len(rows))
        colors = np.where(pnl >= 0, "#66bb6a", "#ef5350")

        ax.bar(x, pnl, color=colors, alpha=0.85)
        ax.axhline(0, color="#9aa3b2", linewidth=0.9, linestyle="--")

        if selected_idx is not None and 0 <= selected_idx < len(rows):
            ax.scatter([selected_idx], [pnl[selected_idx]], s=140, facecolors="none",
                       edgecolors="#ffd54f", linewidths=2, zorder=5)

        step = max(1, len(rows) // 10)
        tick_locs = x[::step]
        tick_lbls = [rows[i]["date"][5:] if rows[i]["date"] else str(i + 1) for i in tick_locs]
        ax.set_xticks(tick_locs)
        ax.set_xticklabels(tick_lbls, rotation=20, fontsize=8)
        ax.set_xlabel("交易日期")
        ax.set_ylabel("盈亏 (元)")
        ax.set_title("逐笔交易盈亏")

        _apply_dark_style(self.figure, [ax])
        self.canvas.draw()

    def _update_summary(self, rows):
        total = len(rows)
        win = sum(1 for r in rows if r["pnl"] > 0)
        lose = sum(1 for r in rows if r["pnl"] < 0)
        total_pnl = sum(r["pnl"] for r in rows)
        win_rate = (win / total * 100) if total else 0.0

        self.title_label.setText(f"交易详情 (共 {total} 笔)")
        self.stats_label.setText(
            f"盈利: {win}  亏损: {lose}  胜率: {win_rate:.1f}%  总盈亏: {total_pnl:.2f}"
        )

    def _on_table_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._render_pnl_chart(self._filtered_rows)
            return
        self._render_pnl_chart(self._filtered_rows, selected_idx=rows[0].row())

    def _on_chart_click(self, event):
        if event.inaxes is None or not self._filtered_rows or event.xdata is None:
            return
        idx = int(round(event.xdata))
        if 0 <= idx < len(self._filtered_rows):
            self.table.selectRow(idx)


# ─────────────────────────────────────────────────────────────────────────────
# 图4：K线图（OHLC 蜡烛图）
# ─────────────────────────────────────────────────────────────────────────────

class CandlestickWidget(_BaseFigureWidget):
    """OHLC 蜡烛图 + 成交量 + 买卖信号"""

    def plot(self, result: "BacktestResult", price_df: Optional[pd.DataFrame] = None) -> None:
        self.figure.clear()

        if price_df is None or price_df.empty:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "暂无 OHLC 数据（需传入含 open/high/low/close 列的 DataFrame）",
                    ha="center", va="center", fontsize=12, color="#888")
            _apply_dark_style(self.figure, [ax])
            self._redraw()
            return

        # 列名规范化
        col_map = {}
        for col in price_df.columns:
            cl = col.lower()
            if cl in ("open", "开盘", "open_price"):
                col_map["open"] = col
            elif cl in ("high", "最高", "high_price"):
                col_map["high"] = col
            elif cl in ("low", "最低", "low_price"):
                col_map["low"] = col
            elif cl in ("close", "收盘", "close_price"):
                col_map["close"] = col
            elif cl in ("volume", "成交量", "vol"):
                col_map["volume"] = col

        has_ohlc = all(k in col_map for k in ("open", "high", "low", "close"))
        has_vol  = "volume" in col_map

        gs_ratios = [4, 1] if has_vol else [1]
        n_rows = 2 if has_vol else 1
        gs = self.figure.add_gridspec(n_rows, 1, height_ratios=gs_ratios, hspace=0.05)
        ax_k = self.figure.add_subplot(gs[0])
        ax_v = self.figure.add_subplot(gs[1], sharex=ax_k) if has_vol else None

        # 确保索引是 DatetimeIndex
        idx = price_df.index
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.to_datetime(idx)

        x = np.arange(len(idx))

        if has_ohlc:
            opens  = price_df[col_map["open"]].values.astype(float)
            highs  = price_df[col_map["high"]].values.astype(float)
            lows   = price_df[col_map["low"]].values.astype(float)
            closes = price_df[col_map["close"]].values.astype(float)

            up   = closes >= opens
            col_up   = "#ef5350"  # 阳线（红）
            col_down = "#26a69a"  # 阴线（绿）

            # 画实体和影线
            width  = 0.6
            width2 = 0.08

            ax_k.bar(x[up],   closes[up]  - opens[up],   width,  bottom=opens[up],   color=col_up,   zorder=3)
            ax_k.bar(x[~up],  opens[~up]  - closes[~up], width,  bottom=closes[~up], color=col_down, zorder=3)
            ax_k.bar(x,       highs - np.maximum(opens, closes), width2,
                     bottom=np.maximum(opens, closes), color=np.where(up, col_up, col_down), zorder=3)
            ax_k.bar(x,       np.minimum(opens, closes) - lows, width2,
                     bottom=lows, color=np.where(up, col_up, col_down), zorder=3)
        else:
            # fallback：只画收盘价折线
            close_col = col_map.get("close", price_df.columns[0])
            ax_k.plot(x, price_df[close_col].values, color="#90caf9", linewidth=1.2)

        # 交易信号叠加
        signals = result.signals or []
        dt_to_x = {pd.Timestamp(t): xi for xi, t in enumerate(idx)}
        buy_xs, buy_ps, sell_xs, sell_ps = [], [], [], []
        for sig in signals:
            sig_time = getattr(sig, "timestamp", None) or getattr(sig, "datetime", None)
            if sig_time is None or not hasattr(sig, "price"):
                continue
            t = pd.Timestamp(sig_time)
            xi = dt_to_x.get(t)
            if xi is None:
                # 找最近
                diffs = np.abs(np.array([(t - ti).total_seconds() for ti in idx]))
                if diffs.min() < 86400:
                    xi = int(np.argmin(diffs))
                else:
                    continue
            d = getattr(sig, "direction", None)
            if d is None:
                continue
            ds = d.value if hasattr(d, "value") else str(d)
            if "long" in ds.lower() or "buy" in ds.lower():
                buy_xs.append(xi); buy_ps.append(sig.price)
            elif "short" in ds.lower() or "sell" in ds.lower():
                sell_xs.append(xi); sell_ps.append(sig.price)

        if buy_xs:
            ax_k.scatter(buy_xs, buy_ps, marker="^", color="#66bb6a", s=80, zorder=5,
                         label=f"买入 ({len(buy_xs)})")
        if sell_xs:
            ax_k.scatter(sell_xs, sell_ps, marker="v", color="#ef5350", s=80, zorder=5,
                         label=f"卖出 ({len(sell_xs)})")

        # X 轴刻度：每隔一段显示日期
        step = max(1, len(idx) // 8)
        tick_locs = x[::step]
        tick_lbls = [idx[i].strftime("%Y-%m") for i in tick_locs]
        ax_k.set_xticks(tick_locs)
        ax_k.set_xticklabels(tick_lbls, rotation=30, fontsize=7)
        ax_k.set_title(f"K线图 — {', '.join(result.symbols)}", fontsize=10)
        ax_k.set_ylabel("价格 (元)")
        if buy_xs or sell_xs:
            ax_k.legend(loc="upper left", fontsize=8, framealpha=0.3)

        # 成交量柱
        if ax_v is not None and has_vol:
            vols = price_df[col_map["volume"]].values.astype(float)
            vol_colors = np.where(up if has_ohlc else np.ones(len(vols), bool), "#ef5350", "#26a69a")
            ax_v.bar(x, vols, color=vol_colors, alpha=0.7)
            ax_v.set_ylabel("成交量", fontsize=8)
            ax_v.set_xticks([])

            axes_list = [ax_k, ax_v]
        else:
            axes_list = [ax_k]

        _apply_dark_style(self.figure, axes_list)
        self._redraw()


# ─────────────────────────────────────────────────────────────────────────────
# 主容器：四合一标签页（新增 K线图）
# ─────────────────────────────────────────────────────────────────────────────

class BacktestChartWidget(QWidget):
    """
    回测结果可视化主控件。
    嵌入三个图表标签页：K线图、权益曲线、交易详情。
    用法：
        widget.update_charts(result, price_df)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # 标题行
        title_bar = QHBoxLayout()
        title_lbl = QLabel("📈 回测结果可视化")
        title_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #c8ccd8; padding: 4px;")
        title_bar.addWidget(title_lbl)
        title_bar.addStretch()

        self.export_btn = QPushButton("导出图表")
        self.export_btn.setFixedWidth(90)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_charts)
        title_bar.addWidget(self.export_btn)
        layout.addLayout(title_bar)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3a4060; background: #1e2130; }
            QTabBar::tab { background: #262d3f; color: #888; padding: 6px 14px; }
            QTabBar::tab:selected { background: #1e2130; color: #c8ccd8; border-bottom: 2px solid #4fc3f7; }
        """)
        layout.addWidget(self.tab_widget)

        # 三个子图控件（去掉交易信号页）
        self.candle_widget  = CandlestickWidget()
        self.equity_widget  = EquityCurveWidget()
        self.trade_detail_widget = TradeDetailWidget()

        self.tab_widget.addTab(self.candle_widget,  "K线图")
        self.tab_widget.addTab(self.equity_widget,  "权益曲线")
        self.tab_widget.addTab(self.trade_detail_widget, "交易详情")

        self._result = None
        self._price_df = None

    # ------------------------------------------------------------------ public

    def update_charts(self, result: "BacktestResult",
                      price_df: Optional[pd.DataFrame] = None) -> None:
        """回测完成后调用，刷新三张图"""
        self._result = result
        self._price_df = price_df

        self.candle_widget.plot(result, price_df)
        self.equity_widget.plot(result)
        self.trade_detail_widget.plot(result)

        self.export_btn.setEnabled(True)
        # 自动跳到 K线图页
        self.tab_widget.setCurrentIndex(0)

    def clear_charts(self) -> None:
        """清空所有图表"""
        for w in (self.candle_widget, self.equity_widget, self.trade_detail_widget):
            w.clear()
        self.export_btn.setEnabled(False)

    # ------------------------------------------------------------------ private

    def _export_charts(self) -> None:
        """导出当前页面的图表为 PNG"""
        if self._result is None:
            return
        from PyQt5.QtWidgets import QFileDialog
        
        current_idx = self.tab_widget.currentIndex()
        if current_idx == 2:  # 交易详情页 (表格)
            # 表格无法用 matplotlib 导出，提示用户
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "交易详情为表格，请使用截图或其他工具保存")
            return
        
        # 获取当前页面的 Figure
        if current_idx == 0:
            current_widget = self.candle_widget
            chart_name = "K线图"
        elif current_idx == 1:
            current_widget = self.equity_widget
            chart_name = "权益曲线"
        else:
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图表", f"backtest_{self._result.strategy_name}_{chart_name}.png",
            "PNG 图片 (*.png)"
        )
        if path:
            current_widget.figure.savefig(path, dpi=150, bbox_inches="tight",
                                          facecolor="#1e2130")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "导出成功", f"图表已保存到:\\n{path}")
