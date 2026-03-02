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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from ..trading.signal import Direction
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

class PriceSignalWidget(QWidget):
    """收盘价折线 + 买卖信号标记 + 交易列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")

        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["日期", "代码", "价格", "方向", "数量", "盈亏"])
        table.horizontalHeader().setStyleSheet("color: #aaa;")
        table.setStyleSheet("""
            QTableWidget { background: #1e2130; color: #c8ccd8; gridline-color: #3a4060; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #4fc3f7; color: #000; }
            QHeaderView::section { background: #262d3f; color: #aaa; padding: 4px; }
        """)
        table.setMaximumHeight(180)
        layout.addWidget(table)
        self._table = table

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

            if close_col:
                idx = pd.to_datetime(price_df.index) if not isinstance(
                    price_df.index, pd.DatetimeIndex) else price_df.index
                ax.plot(idx, price_df[close_col].values.astype(float),
                        color="#4fc3f7", linewidth=1.2, label="收盘价", zorder=2)
                ax.set_ylabel("价格 (元)")

        # ── 交易信号 ──
        signals = result.signals or []
        print(f"[DEBUG] PriceSignalWidget: 获取到 {len(signals)} 个信号")
        
        # 检查信号属性
        if signals:
            first_sig = signals[0]
            print(f"[DEBUG] 第一个信号: datetime={getattr(first_sig, 'datetime', None)}, direction={getattr(first_sig, 'direction', None)}, price={getattr(first_sig, 'price', None)}")
            
            # 统计买入和卖出信号数量
            buy_count = sum(1 for s in signals if getattr(s, 'direction', None) == Direction.BUY or (hasattr(getattr(s, 'direction', None), 'name') and getattr(s, 'direction', None).name == "BUY"))
            sell_count = sum(1 for s in signals if getattr(s, 'direction', None) == Direction.SELL or (hasattr(getattr(s, 'direction', None), 'name') and getattr(s, 'direction', None).name == "SELL"))
            print(f"[DEBUG] 信号统计: 买入={buy_count}, 卖出={sell_count}")
        
        # 如果有价格数据，尝试匹配信号日期与价格数据日期
        if price_df is not None and not price_df.empty:
            idx = pd.to_datetime(price_df.index) if not isinstance(
                price_df.index, pd.DatetimeIndex) else price_df.index
            
            # 创建日期到价格的映射，用于查找信号日期对应的价格
            date_to_price = {}
            for date in idx:
                date_to_price[pd.Timestamp(date).date()] = price_df.loc[date, close_col] if close_col in price_df.columns else None
            
            # 处理信号
            buy_times, buy_prices = [], []
            sell_times, sell_prices = [], []
            
            for sig in signals:
                if not hasattr(sig, "datetime") or not hasattr(sig, "price"):
                    continue
                t = pd.to_datetime(sig.datetime)
                p = sig.price
                
                # 尝试在价格数据中找到最接近的日期
                sig_date = pd.Timestamp(t).date()
                if sig_date in date_to_price and date_to_price[sig_date] is not None:
                    # 使用价格数据中的价格，确保信号点在价格线上
                    p = date_to_price[sig_date]
                
                direction = getattr(sig, "direction", None)
                if direction is None:
                    continue
                # 更灵活的方向判断，支持枚举对象和字符串
                if direction == Direction.BUY or (hasattr(direction, 'name') and direction.name == "BUY"):
                    buy_times.append(t)
                    buy_prices.append(p)
                elif direction == Direction.SELL or (hasattr(direction, 'name') and direction.name == "SELL"):
                    sell_times.append(t)
                    sell_prices.append(p)
        else:
            # 如果没有价格数据，使用原始方法
            buy_times, buy_prices = [], []
            sell_times, sell_prices = [], []
            
            for sig in signals:
                if not hasattr(sig, "datetime") or not hasattr(sig, "price"):
                    continue
                t = pd.to_datetime(sig.datetime)
                p = sig.price
                direction = getattr(sig, "direction", None)
                if direction is None:
                    continue
                # 更灵活的方向判断，支持枚举对象和字符串
                if direction == Direction.BUY or (hasattr(direction, 'name') and direction.name == "BUY"):
                    buy_times.append(t)
                    buy_prices.append(p)
                elif direction == Direction.SELL or (hasattr(direction, 'name') and direction.name == "SELL"):
                    sell_times.append(t)
                    sell_prices.append(p)

        if buy_times:
            ax.scatter(buy_times, buy_prices, marker="^", color="#66bb6a",
                       s=80, zorder=3, label=f"买入 ({len(buy_times)})")
        if sell_times:
            ax.scatter(sell_times, sell_prices, marker="v", color="#ef5350",
                       s=80, zorder=3, label=f"卖出 ({len(sell_times)})")

        # ── 样式设置 ──
        ax.set_title(f"交易信号 — {', '.join(result.symbols)}")

        # 只在有带 label 的 artist 时才显示图例，避免 UserWarning
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(loc="upper left", fontsize=8, framealpha=0.3)

        ax.grid(True, linestyle="--", alpha=0.3)
        self.figure.autofmt_xdate(rotation=30)

        _apply_dark_style(self.figure, [ax])
        self.canvas.draw()
        
        self._populate_table(result)
    
    def _populate_table(self, result):
        if self._table is None:
            return
        
        trades = result.trades or []
        signals = result.signals or []
        
        # 如果没有交易记录但有信号，则显示信号信息
        if not trades and signals:
            print(f"[DEBUG] 没有交易记录但有 {len(signals)} 个信号，显示信号信息")
            self._table.setRowCount(len(signals))
            
            for i, sig in enumerate(signals):
                date = getattr(sig, 'datetime', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                symbol = getattr(sig, 'symbol', '')
                price = getattr(sig, 'price', 0)
                direction = getattr(sig, 'direction', '')
                if hasattr(direction, 'name'):
                    direction = direction.name
                volume = getattr(sig, 'volume', 0)
                
                self._table.setItem(i, 0, QTableWidgetItem(str(date)))
                self._table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                self._table.setItem(i, 2, QTableWidgetItem(f"{price:.2f}"))
                self._table.setItem(i, 3, QTableWidgetItem(direction))
                self._table.setItem(i, 4, QTableWidgetItem(str(volume)))
                self._table.setItem(i, 5, QTableWidgetItem(""))  # 信号没有盈亏信息
        else:
            # 显示交易记录
            print(f"[DEBUG] 显示 {len(trades)} 条交易记录")
            self._table.setRowCount(len(trades))
            
            for i, trade in enumerate(trades):
                date = trade.get('datetime', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                symbol = trade.get('symbol', '')
                price = trade.get('price', 0)
                direction = trade.get('direction', '')
                if hasattr(direction, 'name'):
                    direction = direction.name
                volume = trade.get('volume', 0)
                pnl = trade.get('pnl', 0)
                
                self._table.setItem(i, 0, QTableWidgetItem(str(date)))
                self._table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                self._table.setItem(i, 2, QTableWidgetItem(f"{price:.2f}"))
                self._table.setItem(i, 3, QTableWidgetItem(direction))
                self._table.setItem(i, 4, QTableWidgetItem(str(volume)))
                self._table.setItem(i, 5, QTableWidgetItem(f"{pnl:.2f}"))
                
                if pnl > 0:
                    self._table.item(i, 5).setForeground(QColor("#66bb6a"))
                elif pnl < 0:
                    self._table.item(i, 5).setForeground(QColor("#ef5350"))
        
        self._table.resizeColumnsToContents()


# ─────────────────────────────────────────────────────────────────────────────
# 图3：交易分布直方图
# ─────────────────────────────────────────────────────────────────────────────

class TradeDistributionWidget(_BaseFigureWidget):
    """交易盈亏分布直方图 + 统计摘要"""

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

class CandlestickWidget(QWidget):
    """OHLC 蜡烛图 + 成交量 + 买卖信号 + 交易列表"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 创建图表部分
        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        toolbar = NavigationToolbar(self.canvas, self)
        toolbar.setStyleSheet("background: #1e2130; color: #c8ccd8;")

        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

        # 创建交易详情表格
        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["日期", "代码", "价格", "方向", "数量", "盈亏"])
        table.horizontalHeader().setStyleSheet("color: #aaa;")
        table.setStyleSheet("""
            QTableWidget { background: #1e2130; color: #c8ccd8; gridline-color: #3a4060; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #4fc3f7; color: #000; }
            QHeaderView::section { background: #262d3f; color: #aaa; padding: 4px; }
        """)
        table.setMaximumHeight(180)
        layout.addWidget(table)
        self._table = table

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
        print(f"[DEBUG] K线图: 获取到 {len(signals)} 个信号")
        
        # 检查信号属性
        if signals:
            first_sig = signals[0]
            print(f"[DEBUG] 第一个信号: datetime={getattr(first_sig, 'datetime', None)}, direction={getattr(first_sig, 'direction', None)}, price={getattr(first_sig, 'price', None)}")
            
            # 统计买入和卖出信号数量
            buy_count = sum(1 for s in signals if getattr(s, 'direction', None) == Direction.BUY or (hasattr(getattr(s, 'direction', None), 'name') and getattr(s, 'direction', None).name == "BUY"))
            sell_count = sum(1 for s in signals if getattr(s, 'direction', None) == Direction.SELL or (hasattr(getattr(s, 'direction', None), 'name') and getattr(s, 'direction', None).name == "SELL"))
            print(f"[DEBUG] 信号统计: 买入={buy_count}, 卖出={sell_count}")
        
        # 创建日期到索引的映射，使用更灵活的匹配方式
        dt_to_x = {}
        print(f"[DEBUG] K线数据日期范围: {idx[0]} 到 {idx[-1]}")
        for xi, t in enumerate(idx):
            dt = pd.Timestamp(t)
            dt_to_x[dt] = xi
            # 使用日期部分进行匹配，忽略时间部分
            dt_to_x[dt.date()] = xi
            # 同时添加前后多天的日期，提高匹配成功率
            for days in range(-3, 4):  # 前后3天
                dt_to_x[(dt + pd.Timedelta(days=days)).date()] = xi
        
        buy_xs, buy_ps, sell_xs, sell_ps = [], [], [], []
        for i, sig in enumerate(signals):
            if not hasattr(sig, "datetime") or not hasattr(sig, "price"):
                continue
                
            t = pd.Timestamp(sig.datetime)
            d = getattr(sig, "direction", None)
            
            # 使用信号的日期部分查找对应的K线位置
            sig_date = t.date()
            xi = dt_to_x.get(sig_date)
            
            if xi is None:
                # 如果找不到精确日期，尝试最接近的日期
                diffs = [(abs((pd.Timestamp(ti)).date() - sig_date), idx) for idx, ti in enumerate(idx)]
                if diffs:
                    closest = min(diffs, key=lambda x: x[0])
                    if closest[0][0] <= pd.Timedelta(days=30):  # 如果最接近的日期在一个月内
                        xi = closest[1]
                    else:
                        print(f"[DEBUG] 信号日期 {sig_date} 距离太远，无法匹配到K线数据")
                        continue
                else:
                    print(f"[DEBUG] 无法找到匹配的K线数据索引")
                    continue
            
            # 确保索引在有效范围内
            if xi < 0 or xi >= len(idx):
                print(f"[DEBUG] 索引 {xi} 超出范围 [0, {len(idx)-1}]")
                continue
                
            if d is None:
                continue
                
            # 使用K线收盘价作为信号标记的Y坐标，确保标记在K线上
            if has_ohlc and closes is not None and 0 <= xi < len(closes):
                price = closes[xi]
            else:
                price = sig.price
                
            # 直接比较枚举值
            if d == Direction.BUY or (hasattr(d, 'name') and d.name == "BUY"):
                buy_xs.append(xi); buy_ps.append(price)
                print(f"[DEBUG] 添加买入信号 {i}: 位置=({xi}, {price:.2f})")
            elif d == Direction.SELL or (hasattr(d, 'name') and d.name == "SELL"):
                sell_xs.append(xi); sell_ps.append(price)
                print(f"[DEBUG] 添加卖出信号 {i}: 位置=({xi}, {price:.2f})")
        
        print(f"[DEBUG] K线图: 买入点={len(buy_xs)}, 卖出点={len(sell_xs)}")

        if buy_xs:
            # 显示红色"B"标记表示买入
            for x_val, y_val in zip(buy_xs, buy_ps):
                ax_k.text(x_val, y_val * 1.02, "B", color="#ef5350", fontsize=14, 
                         ha='center', va='bottom', fontweight='bold', zorder=5)
            ax_k.scatter(buy_xs, buy_ps, marker="^", color="#ef5350", s=80, zorder=5,
                         label=f"买入 ({len(buy_xs)})")
        if sell_xs:
            # 显示绿色"S"标记表示卖出
            for x_val, y_val in zip(sell_xs, sell_ps):
                ax_k.text(x_val, y_val * 0.98, "S", color="#66bb6a", fontsize=14,
                         ha='center', va='top', fontweight='bold', zorder=5)
            ax_k.scatter(sell_xs, sell_ps, marker="v", color="#66bb6a", s=80, zorder=5,
                         label=f"卖出 ({len(sell_xs)})")

        # X 轴刻度：每隔一段显示日期
        step = max(1, len(idx) // 8)
        tick_locs = x[::step]
        tick_lbls = [idx[i].strftime("%Y-%m-%d") for i in tick_locs]
        ax_k.set_xticks(tick_locs)
        ax_k.set_xticklabels(tick_lbls, rotation=45, fontsize=8)
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
            
            # 共享x轴，但隐藏成交量图的x轴标签
            ax_v.set_xticks(tick_locs)
            ax_v.set_xticklabels([])  # 不显示成交量图的x轴标签

            axes_list = [ax_k, ax_v]
        else:
            axes_list = [ax_k]

        _apply_dark_style(self.figure, axes_list)
        self.canvas.draw()
        
        # 填充交易详情表格
        self._populate_table(result)
    
    def _populate_table(self, result):
        if self._table is None:
            return
        
        trades = result.trades or []
        signals = result.signals or []
        
        # 如果没有交易记录但有信号，则显示信号信息
        if not trades and signals:
            print(f"[DEBUG] 没有交易记录但有 {len(signals)} 个信号，显示信号信息")
            self._table.setRowCount(len(signals))
            
            for i, sig in enumerate(signals):
                date = getattr(sig, 'datetime', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                symbol = getattr(sig, 'symbol', '')
                price = getattr(sig, 'price', 0)
                direction = getattr(sig, 'direction', '')
                if hasattr(direction, 'name'):
                    direction = direction.name
                volume = getattr(sig, 'volume', 0)
                
                self._table.setItem(i, 0, QTableWidgetItem(str(date)))
                self._table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                self._table.setItem(i, 2, QTableWidgetItem(f"{price:.2f}"))
                self._table.setItem(i, 3, QTableWidgetItem(direction))
                self._table.setItem(i, 4, QTableWidgetItem(str(volume)))
                self._table.setItem(i, 5, QTableWidgetItem(""))  # 信号没有盈亏信息
        else:
            # 显示交易记录
            print(f"[DEBUG] 显示 {len(trades)} 条交易记录")
            self._table.setRowCount(len(trades))
            
            for i, trade in enumerate(trades):
                date = trade.get('datetime', '')
                if hasattr(date, 'strftime'):
                    date = date.strftime('%Y-%m-%d')
                symbol = trade.get('symbol', '')
                price = trade.get('price', 0)
                direction = trade.get('direction', '')
                if hasattr(direction, 'name'):
                    direction = direction.name
                volume = trade.get('volume', 0)
                pnl = trade.get('pnl', 0)
                
                self._table.setItem(i, 0, QTableWidgetItem(str(date)))
                self._table.setItem(i, 1, QTableWidgetItem(str(symbol)))
                self._table.setItem(i, 2, QTableWidgetItem(f"{price:.2f}"))
                self._table.setItem(i, 3, QTableWidgetItem(direction))
                self._table.setItem(i, 4, QTableWidgetItem(str(volume)))
                self._table.setItem(i, 5, QTableWidgetItem(f"{pnl:.2f}"))
                
                if pnl > 0:
                    self._table.item(i, 5).setForeground(QColor("#66bb6a"))
                elif pnl < 0:
                    self._table.item(i, 5).setForeground(QColor("#ef5350"))
        
        self._table.resizeColumnsToContents()


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

        # 三个子图控件
        self.candle_widget  = CandlestickWidget()
        self.equity_widget  = EquityCurveWidget()
        self.dist_widget    = TradeDistributionWidget()

        self.tab_widget.addTab(self.candle_widget,  "K线图")
        self.tab_widget.addTab(self.equity_widget,  "权益曲线")
        self.tab_widget.addTab(self.dist_widget,    "收益分布")

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
        self.dist_widget.plot(result)

        self.export_btn.setEnabled(True)
        # 自动跳到 K线图页
        self.tab_widget.setCurrentIndex(0)

    def clear_charts(self) -> None:
        """清空所有图表"""
        for w in (self.candle_widget, self.equity_widget, self.dist_widget):
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
            fig_combined = Figure(figsize=(14, 16))
            axes = fig_combined.subplots(3, 1)
            plt.tight_layout(pad=3)
            fig_combined.savefig(path, dpi=150, bbox_inches="tight",
                                 facecolor="#1e2130")
            plt.close(fig_combined)
            print(f"[DEBUG] 图表已保存至: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# 图1：权益曲线 + 回撤
# ─────────────────────────────────────────────────────────────────────────────
