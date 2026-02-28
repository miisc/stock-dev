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
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QSizePolicy, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

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
        self.figure = Figure(tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

    def _redraw(self):
        self.figure.tight_layout()
        self.canvas.draw()

    def clear(self):
        self.figure.clear()
        self.canvas.draw()


# ─────────────────────────────────────────────────────────────────────────────
# 图1：权益曲线 + 回撤
# ─────────────────────────────────────────────────────────────────────────────

class EquityCurveWidget(_BaseFigureWidget):
    """权益曲线（上）+ 最大回撤（下）"""

    def plot(self, result: "BacktestResult") -> None:
        self.figure.clear()

        equity = result.equity_curve
        if equity.empty:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "暂无权益曲线数据", ha="center", va="center",
                    fontsize=14, color="#888")
            _apply_dark_style(self.figure, [ax])
            self._redraw()
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
        self._redraw()


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
        ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        self.figure.autofmt_xdate(rotation=30)

        _apply_dark_style(self.figure, [ax])
        self._redraw()


# ─────────────────────────────────────────────────────────────────────────────
# 图3：每笔交易收益分布
# ─────────────────────────────────────────────────────────────────────────────

class TradeDistributionWidget(_BaseFigureWidget):
    """每笔交易盈亏直方图 + 关键统计线"""

    def plot(self, result: "BacktestResult") -> None:
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        trades = result.trades or []
        pnl_list = [t.get("pnl", t.get("profit", 0)) for t in trades
                    if t.get("pnl", t.get("profit")) is not None]

        if not pnl_list:
            ax.text(0.5, 0.5, "暂无交易记录", ha="center", va="center",
                    fontsize=14, color="#888")
            _apply_dark_style(self.figure, [ax])
            self._redraw()
            return

        pnl_arr = np.array(pnl_list, dtype=float)
        bins = min(30, max(10, len(pnl_arr) // 3))

        colors = ["#66bb6a" if v >= 0 else "#ef5350" for v in pnl_arr]
        n, bin_edges, patches = ax.hist(pnl_arr, bins=bins, edgecolor="#333")
        for patch, c in zip(patches, [colors[int(len(colors) * (i / bins))]
                                       for i in range(len(patches))]):
            patch.set_facecolor(c)
            patch.set_alpha(0.75)

        # 均值线
        mean_val = np.mean(pnl_arr)
        ax.axvline(mean_val, color="#ffd54f", linewidth=1.5,
                   linestyle="--", label=f"均值: {mean_val:.2f}")
        ax.axvline(0, color="#aaa", linewidth=1.0, linestyle="-")

        ax.set_xlabel("每笔盈亏 (元)")
        ax.set_ylabel("交易次数")
        ax.set_title(f"交易盈亏分布  (共 {len(pnl_arr)} 笔)")
        ax.legend(fontsize=8, framealpha=0.3)

        # 统计注释
        win_count = np.sum(pnl_arr > 0)
        lose_count = np.sum(pnl_arr < 0)
        win_rate = win_count / len(pnl_arr) * 100
        note = (f"盈利: {int(win_count)}笔  亏损: {int(lose_count)}笔  "
                f"胜率: {win_rate:.1f}%")
        ax.text(0.98, 0.97, note, transform=ax.transAxes, fontsize=8,
                color="#aaa", ha="right", va="top")

        _apply_dark_style(self.figure, [ax])
        self._redraw()


# ─────────────────────────────────────────────────────────────────────────────
# 主容器：三合一标签页
# ─────────────────────────────────────────────────────────────────────────────

class BacktestChartWidget(QWidget):
    """
    回测结果可视化主控件。
    嵌入三个图表标签页：权益曲线、交易信号、收益分布。
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

        # 三个子图控件
        self.equity_widget = EquityCurveWidget()
        self.signal_widget = PriceSignalWidget()
        self.dist_widget = TradeDistributionWidget()

        self.tab_widget.addTab(self.equity_widget, "权益曲线")
        self.tab_widget.addTab(self.signal_widget, "交易信号")
        self.tab_widget.addTab(self.dist_widget, "收益分布")

        self._result = None
        self._price_df = None

    # ------------------------------------------------------------------ public

    def update_charts(self, result: "BacktestResult",
                      price_df: Optional[pd.DataFrame] = None) -> None:
        """回测完成后调用，刷新三张图"""
        self._result = result
        self._price_df = price_df

        self.equity_widget.plot(result)
        self.signal_widget.plot(result, price_df)
        self.dist_widget.plot(result)

        self.export_btn.setEnabled(True)
        # 自动跳到权益曲线页
        self.tab_widget.setCurrentIndex(0)

    def clear_charts(self) -> None:
        """清空所有图表"""
        for w in (self.equity_widget, self.signal_widget, self.dist_widget):
            w.clear()
        self.export_btn.setEnabled(False)

    # ------------------------------------------------------------------ private

    def _export_charts(self) -> None:
        """（可扩展）将当前图表保存为 PNG"""
        if self._result is None:
            return
        from PyQt5.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图表", f"backtest_{self._result.strategy_name}.png",
            "PNG 图片 (*.png)"
        )
        if path:
            # 将三张图合并保存
            fig_combined, axes = plt.subplots(3, 1, figsize=(14, 16))
            plt.tight_layout(pad=3)
            fig_combined.savefig(path, dpi=150, bbox_inches="tight",
                                 facecolor="#1e2130")
            plt.close(fig_combined)
