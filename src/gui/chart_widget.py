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
            if not hasattr(sig, "timestamp") or not hasattr(sig, "price"):
                continue
            t = pd.Timestamp(sig.timestamp)
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
    嵌入四个图表标签页：K线图、权益曲线、交易信号、收益分布。
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

        # 四个子图控件
        self.candle_widget  = CandlestickWidget()
        self.equity_widget  = EquityCurveWidget()
        self.signal_widget  = PriceSignalWidget()
        self.dist_widget    = TradeDistributionWidget()

        self.tab_widget.addTab(self.candle_widget,  "K线图")
        self.tab_widget.addTab(self.equity_widget,  "权益曲线")
        self.tab_widget.addTab(self.signal_widget,  "交易信号")
        self.tab_widget.addTab(self.dist_widget,    "收益分布")

        self._result = None
        self._price_df = None

    # ------------------------------------------------------------------ public

    def update_charts(self, result: "BacktestResult",
                      price_df: Optional[pd.DataFrame] = None) -> None:
        """回测完成后调用，刷新四张图"""
        self._result = result
        self._price_df = price_df

        self.candle_widget.plot(result, price_df)
        self.equity_widget.plot(result)
        self.signal_widget.plot(result, price_df)
        self.dist_widget.plot(result)

        self.export_btn.setEnabled(True)
        # 自动跳到 K线图页
        self.tab_widget.setCurrentIndex(0)

    def clear_charts(self) -> None:
        """清空所有图表"""
        for w in (self.candle_widget, self.equity_widget, self.signal_widget, self.dist_widget):
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
