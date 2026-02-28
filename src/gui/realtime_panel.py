"""
实时行情展示面板

功能：
  - 自选股行情列表（代码/名称/现价/涨跌幅/成交量等）
  - 定时自动刷新（默认 10 秒）
  - 多股票同时监控
  - 手动添加/删除自选股
  - 通过 AKShare 获取实时行情
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox,
    QMessageBox, QFrame, QCheckBox,
)


# ─────────────────────────────────────────────────────────────────────────────
# 后台拉取实时行情的 Worker
# ─────────────────────────────────────────────────────────────────────────────

class RealtimeQuoteWorker(QThread):
    """在后台线程获取实时行情，避免阻塞 UI"""
    quotes_ready = pyqtSignal(list)   # List[dict]
    error        = pyqtSignal(str)

    def __init__(self, symbols: List[str], parent=None):
        super().__init__(parent)
        self.symbols = symbols

    def run(self):
        try:
            rows = []
            # ak.stock_zh_a_spot_em() 返回全市场实时行情
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                self.quotes_ready.emit([])
                return

            # 构建代码到行的映射（代码格式：600000, 000001, …）
            code_map: Dict[str, pd.Series] = {}
            for _, row in df.iterrows():
                code = str(row.get("代码", "")).strip()
                code_map[code] = row

            for sym in self.symbols:
                bare = sym.split(".")[0]  # 去掉 .SZ/.SH 后缀
                row = code_map.get(bare)
                if row is None:
                    rows.append({"代码": sym, "名称": "—", "现价": "—",
                                 "涨跌幅": "—", "成交量": "—", "成交额": "—",
                                 "最高": "—", "最低": "—", "开盘": "—",
                                 "昨收": "—", "状态": "未找到"})
                    continue

                def _fmt(key, digits=2):
                    v = row.get(key, "")
                    if v == "" or pd.isna(v):
                        return "—"
                    try:
                        return f"{float(v):.{digits}f}"
                    except (ValueError, TypeError):
                        return str(v)

                rows.append({
                    "代码":  sym,
                    "名称":  str(row.get("名称", "—")),
                    "现价":  _fmt("最新价"),
                    "涨跌幅": _fmt("涨跌幅") + "%",
                    "成交量": _fmt("成交量", 0),
                    "成交额": _fmt("成交额", 0),
                    "最高":  _fmt("最高"),
                    "最低":  _fmt("最低"),
                    "开盘":  _fmt("今开"),
                    "昨收":  _fmt("昨收"),
                    "状态":  "正常",
                })

            self.quotes_ready.emit(rows)
        except Exception as exc:
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# 面板主控件
# ─────────────────────────────────────────────────────────────────────────────

_COLUMNS = ["代码", "名称", "现价", "涨跌幅", "成交量", "成交额",
            "最高", "最低", "开盘", "昨收", "状态"]

_DEFAULT_SYMBOLS = ["600000.SH", "000001.SZ", "000002.SZ", "600519.SH", "300750.SZ"]


class RealtimePanel(QWidget):
    """实时行情展示面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbols: List[str] = list(_DEFAULT_SYMBOLS)
        self._worker: Optional[RealtimeQuoteWorker] = None
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._refresh)
        self._init_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── 控制栏 ──────────────────────────────────────────────────────
        ctrl_group = QGroupBox("自选股行情监控")
        ctrl_layout = QVBoxLayout(ctrl_group)

        # 添加股票行
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("添加股票:"))
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("输入股票代码，如 600000.SH 或 000001.SZ")
        self.add_edit.returnPressed.connect(self._add_symbol)
        add_row.addWidget(self.add_edit)

        self.add_btn = QPushButton("添加")
        self.add_btn.setFixedWidth(70)
        self.add_btn.clicked.connect(self._add_symbol)
        add_row.addWidget(self.add_btn)

        self.del_btn = QPushButton("删除选中")
        self.del_btn.setFixedWidth(80)
        self.del_btn.clicked.connect(self._del_selected)
        add_row.addWidget(self.del_btn)

        ctrl_layout.addLayout(add_row)

        # 刷新控制行
        refresh_row = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 立即刷新")
        self.refresh_btn.setStyleSheet(
            "QPushButton { background:#1976D2; color:white; padding:6px 14px; }"
            "QPushButton:hover { background:#1565C0; }"
            "QPushButton:disabled { background:#aaa; }"
        )
        self.refresh_btn.clicked.connect(self._refresh)
        refresh_row.addWidget(self.refresh_btn)

        self.auto_check = QCheckBox("自动刷新")
        self.auto_check.stateChanged.connect(self._toggle_auto)
        refresh_row.addWidget(self.auto_check)

        refresh_row.addWidget(QLabel("间隔 (秒):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 300)
        self.interval_spin.setValue(30)
        self.interval_spin.setFixedWidth(70)
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        refresh_row.addWidget(self.interval_spin)

        refresh_row.addStretch()

        self.last_update_label = QLabel("最后更新: —")
        self.last_update_label.setStyleSheet("color: gray; font-size: 11px;")
        refresh_row.addWidget(self.last_update_label)

        ctrl_layout.addLayout(refresh_row)
        root.addWidget(ctrl_group)

        # ── 行情表格 ──────────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setFont(QFont("Microsoft YaHei", 10))
        root.addWidget(self.table)

        # ── 状态栏 ────────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        self.status_label = QLabel("就绪  |  共 0 只股票")
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        disclaimer = QLabel("⚠ 实时行情通过公网接口获取，可能存在延迟，仅供参考")
        disclaimer.setStyleSheet("color: #B71C1C; font-size: 10px;")
        status_row.addWidget(disclaimer)
        root.addLayout(status_row)

        # 初始显示默认自选股
        self._populate_symbol_rows()

    # ------------------------------------------------------------------
    # 自选股管理
    # ------------------------------------------------------------------

    def _normalize_symbol(self, code: str) -> Optional[str]:
        """标准化股票代码，自动补全交易所后缀"""
        code = code.strip().upper()
        if not code:
            return None
        if "." in code:
            return code
        # 根据首位数字判断交易所
        if code.startswith("6") or code.startswith("5") or code.startswith("9"):
            return f"{code}.SH"
        return f"{code}.SZ"

    def _add_symbol(self):
        code = self._normalize_symbol(self.add_edit.text())
        if not code:
            return
        if code in self._symbols:
            QMessageBox.information(self, "提示", f"{code} 已在列表中")
            return
        self._symbols.append(code)
        self.add_edit.clear()
        self._populate_symbol_rows()
        self.status_label.setText(f"已添加 {code}  |  共 {len(self._symbols)} 只股票")

    def _del_selected(self):
        rows = sorted(
            {idx.row() for idx in self.table.selectedIndexes()},
            reverse=True,
        )
        for r in rows:
            if r < len(self._symbols):
                self._symbols.pop(r)
        self._populate_symbol_rows()
        self.status_label.setText(f"共 {len(self._symbols)} 只股票")

    def _populate_symbol_rows(self):
        """用占位符填充表格（不含实时数据）"""
        self.table.setRowCount(len(self._symbols))
        for row, sym in enumerate(self._symbols):
            self.table.setItem(row, 0, QTableWidgetItem(sym))
            for col in range(1, len(_COLUMNS)):
                self.table.setItem(row, col, QTableWidgetItem("…"))

    # ------------------------------------------------------------------
    # 刷新逻辑
    # ------------------------------------------------------------------

    def _refresh(self):
        if not self._symbols:
            self.status_label.setText("请先添加股票")
            return
        if self._worker and self._worker.isRunning():
            return  # 上次还没完成，跳过本次

        self.refresh_btn.setEnabled(False)
        self.status_label.setText("正在获取行情…")

        self._worker = RealtimeQuoteWorker(list(self._symbols))
        self._worker.quotes_ready.connect(self._on_quotes_ready)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_quotes_ready(self, rows: list):
        self.refresh_btn.setEnabled(True)
        self._fill_table(rows)
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.setText(f"最后更新: {ts}")
        self.status_label.setText(f"已更新  |  共 {len(self._symbols)} 只股票")

    def _on_fetch_error(self, msg: str):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"获取失败: {msg}")

    def _fill_table(self, rows: list):
        self.table.setRowCount(len(rows))
        for row_idx, data in enumerate(rows):
            for col_idx, col_name in enumerate(_COLUMNS):
                val = data.get(col_name, "—")
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)

                # 涨跌幅着色
                if col_name == "涨跌幅":
                    try:
                        pct = float(str(val).replace("%", ""))
                        if pct > 0:
                            item.setForeground(QColor("#C62828"))   # 涨 红
                        elif pct < 0:
                            item.setForeground(QColor("#2E7D32"))   # 跌 绿
                    except (ValueError, TypeError):
                        pass

                self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # 自动刷新控制
    # ------------------------------------------------------------------

    def _toggle_auto(self, state: int):
        if state == Qt.Checked:
            interval_ms = self.interval_spin.value() * 1000
            self._auto_timer.start(interval_ms)
            self._refresh()  # 立即先刷新一次
        else:
            self._auto_timer.stop()

    def _on_interval_changed(self, value: int):
        if self._auto_timer.isActive():
            self._auto_timer.setInterval(value * 1000)
