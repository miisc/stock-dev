"""
数据管理面板（层次1：下载范围）

用户在此决定本地数据库存哪些股票的历史数据。
操作流程：选择股票池 → 点击下载 → 等待进度 → 查看失败列表。
所有网络操作在 DownloadWorker(QThread) 中执行，主线程只更新 UI。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QDateEdit, QTextEdit,
    QMessageBox, QSplitter, QSpinBox,
)

from ..data.universe import manager as universe_manager
from ..data.batch_downloader import BatchDownloader
from ..data.data_storage import DataStorage
from ..common.database import DatabaseManager

DB_PATH = "data/stock_data.db"

POOL_LABELS: Dict[str, str] = {
    "hs300": "沪深300（约300只）",
    "sh50":  "上证50（约50只）",
    "cyb50": "创业板50（约50只）",
    "zz500": "中证500（约500只）",
    "all":   "全部A股（约5000只）",
}


# ─────────────────────────────────────────────────────────────────────────────
# QThread Worker
# ─────────────────────────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    """在后台线程执行批量下载，通过信号通知主线程"""
    progress   = pyqtSignal(int, int, str)   # done, total, ts_code
    log        = pyqtSignal(str)             # 日志文本
    finished   = pyqtSignal(dict)            # 下载汇总结果

    def __init__(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        parent=None,
    ):
        super().__init__(parent)
        self.ts_codes  = ts_codes
        self.start_date = start_date
        self.end_date   = end_date
        self._downloader: Optional[BatchDownloader] = None

    def run(self):
        try:
            storage = DataStorage(DB_PATH)
            self._downloader = BatchDownloader(storage=storage, concurrency=3)

            def on_progress(done, total, ts):
                self.progress.emit(done, total, ts)
                self.log.emit(f"  [{done}/{total}] {ts}")

            result = self._downloader.download(
                self.ts_codes,
                self.start_date,
                self.end_date,
                progress_callback=on_progress,
            )
            self.finished.emit(result)
        except Exception as exc:
            self.log.emit(f"下载出错: {exc}")
            self.finished.emit({"total": 0, "done": 0, "successes": 0, "failures": []})

    def cancel(self):
        if self._downloader:
            self._downloader.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Panel Widget
# ─────────────────────────────────────────────────────────────────────────────

class UniversePanel(QWidget):
    """数据管理面板"""

    # 通知外部（主窗口/回测面板）本地数据已更新
    data_updated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[DownloadWorker] = None
        self._ts_codes: List[str] = []
        self._init_ui()
        self._refresh_local_stats()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Vertical)
        root.addWidget(splitter)

        # ── 上半：配置区 ──────────────────────────────────────────────
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # 股票池选择
        pool_group = QGroupBox("股票池选择（层次1：下载范围）")
        pool_form = QFormLayout(pool_group)

        self.pool_combo = QComboBox()
        for key, label in POOL_LABELS.items():
            self.pool_combo.addItem(label, key)
        self.pool_combo.currentIndexChanged.connect(self._on_pool_changed)
        pool_form.addRow("预置股票池:", self.pool_combo)

        self.count_label = QLabel("—")
        pool_form.addRow("预计股票数:", self.count_label)

        # 本地数据状态
        self.local_stats_label = QLabel("本地已有数据: 检查中…")
        self.local_stats_label.setStyleSheet("color: gray;")
        pool_form.addRow("本地数据状态:", self.local_stats_label)

        top_layout.addWidget(pool_group)

        # 日期范围
        date_group = QGroupBox("下载日期范围")
        date_form = QFormLayout(date_group)

        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDate(QDate.currentDate().addYears(-3))
        date_form.addRow("开始日期:", self.start_date_edit)

        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit.setDate(QDate.currentDate())
        date_form.addRow("结束日期:", self.end_date_edit)

        top_layout.addWidget(date_group)

        # 按钮行
        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setStyleSheet(
            "QPushButton { background:#4CAF50; color:white; font-weight:bold; padding:6px; }"
            "QPushButton:hover { background:#45a049; }"
            "QPushButton:disabled { background:#aaa; }"
        )
        self.download_btn.clicked.connect(self._start_download)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("QPushButton { padding:6px; }")
        self.cancel_btn.clicked.connect(self._cancel_download)

        self.refresh_btn = QPushButton("刷新本地统计")
        self.refresh_btn.setStyleSheet("QPushButton { padding:6px; }")
        self.refresh_btn.clicked.connect(self._refresh_local_stats)

        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        top_layout.addLayout(btn_row)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_label = QLabel("就绪")
        self.progress_label.setStyleSheet("color: gray;")
        top_layout.addWidget(self.progress_bar)
        top_layout.addWidget(self.progress_label)

        splitter.addWidget(top)

        # ── 下半：日志 + 失败列表 ──────────────────────────────────────
        bottom = QWidget()
        bot_layout = QVBoxLayout(bottom)
        bot_layout.setContentsMargins(0, 0, 0, 0)

        bot_tabs_splitter = QSplitter(Qt.Horizontal)

        # 日志
        log_box = QGroupBox("下载日志")
        log_vbox = QVBoxLayout(log_box)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_vbox.addWidget(self.log_text)
        bot_tabs_splitter.addWidget(log_box)

        # 失败列表
        fail_box = QGroupBox("失败列表（可单独重试）")
        fail_vbox = QVBoxLayout(fail_box)
        self.fail_table = QTableWidget(0, 2)
        self.fail_table.setHorizontalHeaderLabels(["股票代码", "失败原因"])
        self.fail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.fail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.retry_btn = QPushButton("重试选中")
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self._retry_failed)
        fail_vbox.addWidget(self.fail_table)
        fail_vbox.addWidget(self.retry_btn)
        bot_tabs_splitter.addWidget(fail_box)

        bot_layout.addWidget(bot_tabs_splitter)
        splitter.addWidget(bottom)
        splitter.setSizes([350, 250])

    # ------------------------------------------------------------------
    # 槽函数
    # ------------------------------------------------------------------

    def _on_pool_changed(self, _idx: int):
        """股票池切换时估算数量"""
        estimates = {"hs300": "约300只", "sh50": "约50只", "cyb50": "约50只",
                     "zz500": "约500只", "all": "约5000只"}
        pool = self.pool_combo.currentData()
        self.count_label.setText(estimates.get(pool, "—"))

    def _start_download(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示", "下载正在进行中，请等待或点击取消")
            return

        pool = self.pool_combo.currentData()
        self._log(f"正在获取股票池 [{pool}] 成分股列表…")

        try:
            codes = universe_manager.get_pool(pool)
            if not codes:
                self._log("获取股票列表失败或列表为空")
                QMessageBox.warning(self, "警告", "获取股票列表失败，请检查网络连接")
                return
        except Exception as exc:
            self._log(f"获取股票列表出错: {exc}")
            QMessageBox.critical(self, "错误", f"获取股票列表失败: {exc}")
            return

        self._ts_codes = codes
        start = self.start_date_edit.date().toString("yyyy-MM-dd")
        end   = self.end_date_edit.date().toString("yyyy-MM-dd")

        self._log(f"开始下载 {len(codes)} 只股票 ({start} ~ {end})…")
        self.fail_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(codes))

        # 启动 Worker
        self._worker = DownloadWorker(codes, start, end)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log)
        self._worker.finished.connect(self._on_finished)

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._worker.start()

    def _cancel_download(self):
        if self._worker:
            self._worker.cancel()
            self._log("用户取消下载…")
        self.cancel_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int, ts: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        pct = int(done / total * 100) if total else 0
        self.progress_label.setText(f"进度 {done}/{total}（{pct}%） — 当前: {ts}")

    def _on_finished(self, result: dict):
        successes = result.get("successes", 0)
        failures  = result.get("failures", [])
        total     = result.get("total", 0)

        self._log(
            f"下载完成：成功 {successes}/{total}，"
            f"失败 {len(failures)} 只"
        )
        self.progress_label.setText(
            f"完成：{successes}/{total} 成功，{len(failures)} 失败"
        )

        # 填充失败列表
        self.fail_table.setRowCount(len(failures))
        for row, f in enumerate(failures):
            self.fail_table.setItem(row, 0, QTableWidgetItem(f.get("ts_code", "")))
            self.fail_table.setItem(row, 1, QTableWidgetItem(f.get("error", "")))

        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.retry_btn.setEnabled(len(failures) > 0)

        if successes > 0:
            self._refresh_local_stats()
            self.data_updated.emit()

    def _retry_failed(self):
        """将失败列表中的股票重新加入下载"""
        codes = []
        for row in range(self.fail_table.rowCount()):
            item = self.fail_table.item(row, 0)
            if item:
                codes.append(item.text())
        if not codes:
            return

        start = self.start_date_edit.date().toString("yyyy-MM-dd")
        end   = self.end_date_edit.date().toString("yyyy-MM-dd")

        self._log(f"重试 {len(codes)} 只失败股票…")
        self.fail_table.setRowCount(0)
        self.progress_bar.setValue(0)

        self._worker = DownloadWorker(codes, start, end)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log)
        self._worker.finished.connect(self._on_finished)

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.retry_btn.setEnabled(False)
        self._worker.start()

    def _refresh_local_stats(self):
        """查询本地 DB 已有股票数量和最新日期"""
        try:
            db = DatabaseManager(DB_PATH)
            rows = db.execute_query(
                "SELECT COUNT(DISTINCT ts_code) AS cnt, MAX(trade_date) AS latest "
                "FROM stock_daily"
            )
            cnt    = rows[0]["cnt"] if rows else 0
            latest = rows[0]["latest"] if rows else "—"
            self.local_stats_label.setText(
                f"本地已有 {cnt} 只股票数据，最新日期: {latest}"
            )
            self.local_stats_label.setStyleSheet(
                "color: green;" if cnt > 0 else "color: orange;"
            )
        except Exception as exc:
            self.local_stats_label.setText(f"查询失败: {exc}")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")
