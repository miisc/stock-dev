"""
批量回测配置面板（层次2+3：回测范围与个股筛选）

层次2：从本地已有数据中选择回测的大范围股票池
层次3：在层次2基础上进一步手动勾选/排除个别股票（可选）

所有耗时回测在 BatchBacktestWorker(QThread) 中执行。
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional

from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QComboBox, QProgressBar, QLineEdit,
    QDoubleSpinBox, QSpinBox, QDateEdit, QListWidget,
    QListWidgetItem, QSplitter, QTextEdit, QMessageBox,
    QCheckBox, QFrame,
)

from ..common.database import DatabaseManager
from ..trading import strategy_config_manager
from ..backtesting import BacktestConfig, BacktestEngine
from ..backtesting.batch_runner import BatchRunner

DB_PATH = "data/stock_data.db"

POOL_LABELS: Dict[str, str] = {
    "all_local": "全部本地已有",
    "hs300": "沪深300",
    "sh50":  "上证50",
    "cyb50": "创业板50",
    "zz500": "中证500",
}


# ─────────────────────────────────────────────────────────────────────────────
# QThread Worker
# ─────────────────────────────────────────────────────────────────────────────

class BatchBacktestWorker(QThread):
    """在后台线程执行批量回测"""
    progress  = pyqtSignal(int, int, str)   # current, total, ts_code
    log       = pyqtSignal(str)
    finished  = pyqtSignal(list)            # List[BacktestResult]
    error     = pyqtSignal(str)

    def __init__(
        self,
        ts_codes: List[str],
        strategy_factory: Callable,
        start_date: datetime,
        end_date: datetime,
        initial_cash: float,
        commission_rate: float,
        slippage_rate: float,
        parent=None,
    ):
        super().__init__(parent)
        self.ts_codes        = ts_codes
        self.strategy_factory = strategy_factory
        self.start_date      = start_date
        self.end_date        = end_date
        self.initial_cash    = initial_cash
        self.commission_rate = commission_rate
        self.slippage_rate   = slippage_rate
        self._runner: Optional[BatchRunner] = None

    def run(self):
        try:
            self._runner = BatchRunner(DB_PATH)

            def on_progress(current, total, ts):
                self.progress.emit(current, total, ts)
                if ts:
                    self.log.emit(f"  [{current+1}/{total}] 正在回测 {ts}…")

            results = self._runner.run(
                ts_codes=self.ts_codes,
                strategy_factory=self.strategy_factory,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_cash=self.initial_cash,
                commission_rate=self.commission_rate,
                slippage_rate=self.slippage_rate,
                on_progress=on_progress,
                persist_results=True,
            )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))

    def cancel(self):
        if self._runner:
            self._runner.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Panel Widget
# ─────────────────────────────────────────────────────────────────────────────

class BacktestPanel(QWidget):
    """批量回测配置面板"""

    # 回测成功完成后向外广播结果
    backtest_finished = pyqtSignal(list)   # List[BacktestResult]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[BatchBacktestWorker] = None
        self._all_local_codes: List[str] = []   # 本地DB全部股票
        self._pool_codes: Dict[str, List[str]] = {}  # 已加载的池代码
        self._param_widgets: Dict[str, QWidget] = {}
        self._init_ui()
        self._load_strategies()
        self._refresh_local_codes()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        h_splitter = QSplitter(Qt.Horizontal)
        root.addWidget(h_splitter)

        # ── 左列：股票选择 ────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 层次2：股票池选择
        pool_group = QGroupBox("层次2：股票池（回测范围）")
        pool_form = QFormLayout(pool_group)

        self.pool_combo = QComboBox()
        for key, label in POOL_LABELS.items():
            self.pool_combo.addItem(label, key)
        self.pool_combo.currentIndexChanged.connect(self._on_pool_changed)
        pool_form.addRow("股票池:", self.pool_combo)

        self.pool_count_label = QLabel("—")
        pool_form.addRow("股票总数:", self.pool_count_label)

        left_layout.addWidget(pool_group)

        # 层次3：个股勾选
        stock_group = QGroupBox("层次3：个股筛选（可选）")
        stock_layout = QVBoxLayout(stock_group)

        # 搜索框
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("按代码/名称搜索…")
        self.search_edit.textChanged.connect(self._filter_stock_list)
        search_row.addWidget(QLabel("搜索:"))
        search_row.addWidget(self.search_edit)
        stock_layout.addLayout(search_row)

        # 全选/全不选按钮
        sel_row = QHBoxLayout()
        self.select_all_btn  = QPushButton("全选")
        self.deselect_all_btn = QPushButton("全不选")
        self.select_all_btn.clicked.connect(self._select_all)
        self.deselect_all_btn.clicked.connect(self._deselect_all)
        sel_row.addWidget(self.select_all_btn)
        sel_row.addWidget(self.deselect_all_btn)
        sel_row.addStretch()
        stock_layout.addLayout(sel_row)

        self.stock_list = QListWidget()
        self.stock_list.setSelectionMode(QListWidget.NoSelection)
        self.stock_list.itemChanged.connect(self._on_item_changed)
        stock_layout.addWidget(self.stock_list)

        self.selected_label = QLabel("已选: 0 只")
        self.selected_label.setStyleSheet("font-weight: bold; color: #1976D2;")
        stock_layout.addWidget(self.selected_label)

        left_layout.addWidget(stock_group)
        h_splitter.addWidget(left)

        # ── 右列：策略 + 成本 + 操作 ─────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 策略选择
        strategy_group = QGroupBox("策略选择")
        strategy_form = QFormLayout(strategy_group)

        self.strategy_combo = QComboBox()
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        strategy_form.addRow("策略:", self.strategy_combo)

        self.params_group = QGroupBox("策略参数")
        self.params_form  = QFormLayout(self.params_group)

        right_layout.addWidget(strategy_group)
        right_layout.addWidget(self.params_group)

        # 回测时间范围
        date_group = QGroupBox("回测时间范围")
        date_form = QFormLayout(date_group)

        self.bt_start = QDateEdit(calendarPopup=True)
        self.bt_start.setDate(QDate.currentDate().addYears(-3))
        date_form.addRow("开始日期:", self.bt_start)

        self.bt_end = QDateEdit(calendarPopup=True)
        self.bt_end.setDate(QDate.currentDate())
        date_form.addRow("结束日期:", self.bt_end)

        right_layout.addWidget(date_group)

        # 交易成本
        cost_group = QGroupBox("交易成本参数")
        cost_form = QFormLayout(cost_group)

        self.cash_spin = QDoubleSpinBox()
        self.cash_spin.setRange(1000, 10_000_000)
        self.cash_spin.setValue(100_000)
        self.cash_spin.setSuffix(" 元")
        self.cash_spin.setSingleStep(10_000)
        cost_form.addRow("初始资金:", self.cash_spin)

        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setRange(0, 0.01)
        self.commission_spin.setValue(0.0003)
        self.commission_spin.setDecimals(4)
        self.commission_spin.setSingleStep(0.0001)
        cost_form.addRow("手续费率:", self.commission_spin)

        self.slippage_spin = QDoubleSpinBox()
        self.slippage_spin.setRange(0, 0.01)
        self.slippage_spin.setValue(0.001)
        self.slippage_spin.setDecimals(4)
        self.slippage_spin.setSingleStep(0.0001)
        cost_form.addRow("滑点率:", self.slippage_spin)

        self.trade_amount_spin = QDoubleSpinBox()
        self.trade_amount_spin.setRange(1000, 1_000_000)
        self.trade_amount_spin.setValue(10_000)
        self.trade_amount_spin.setSuffix(" 元")
        self.trade_amount_spin.setSingleStep(1000)
        self.trade_amount_spin.setDecimals(0)
        cost_form.addRow("每笔金额:", self.trade_amount_spin)

        stamp_label = QLabel("印花税: 0.1% 卖出时固定")
        stamp_label.setStyleSheet("color: gray; font-size: 11px;")
        cost_form.addRow("", stamp_label)

        right_layout.addWidget(cost_group)

        # 运行按钮 + 进度
        ctrl_group = QGroupBox("执行")
        ctrl_layout = QVBoxLayout(ctrl_group)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("开始批量回测")
        self.run_btn.setStyleSheet(
            "QPushButton { background:#1976D2; color:white; font-weight:bold; padding:8px; }"
            "QPushButton:hover { background:#1565C0; }"
            "QPushButton:disabled { background:#aaa; }"
        )
        self.run_btn.clicked.connect(self._start_backtest)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet("QPushButton { padding:8px; }")
        self.cancel_btn.clicked.connect(self._cancel_backtest)

        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.cancel_btn)
        ctrl_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        ctrl_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("就绪")
        self.progress_label.setStyleSheet("color: gray;")
        ctrl_layout.addWidget(self.progress_label)

        right_layout.addWidget(ctrl_group)

        # 回测日志
        log_group = QGroupBox("回测日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        right_layout.addWidget(log_group)

        h_splitter.addWidget(right)
        h_splitter.setSizes([380, 420])

    # ------------------------------------------------------------------
    # 策略相关
    # ------------------------------------------------------------------

    def _load_strategies(self):
        try:
            strategies = strategy_config_manager.get_all_strategies()
            self.strategy_combo.clear()
            for sid, cfg in strategies.items():
                self.strategy_combo.addItem(cfg["description"], sid)
            if strategies:
                self._on_strategy_changed(0)
        except Exception as exc:
            self._log(f"加载策略失败: {exc}")

    def _on_strategy_changed(self, _idx: int):
        sid = self.strategy_combo.currentData()
        if not sid:
            return
        # 清理旧参数控件
        while self.params_form.count():
            item = self.params_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._param_widgets.clear()
        try:
            cfg    = strategy_config_manager.get_strategy_config(sid)
            params = cfg.parameters if cfg else {}
            for pname, pcfg in params.items():
                if pcfg.type == int:
                    w = QSpinBox()
                    w.setRange(int(pcfg.min_value or 1), int(pcfg.max_value or 1000))
                    w.setValue(int(pcfg.default_value))
                elif pcfg.type == float:
                    w = QDoubleSpinBox()
                    w.setRange(float(pcfg.min_value or 0), float(pcfg.max_value or 1000))
                    w.setValue(float(pcfg.default_value))
                    w.setDecimals(4)
                else:
                    w = QLineEdit(str(pcfg.default_value))
                self._param_widgets[pname] = w
                self.params_form.addRow(f"{pcfg.name}:", w)
        except Exception as exc:
            self._log(f"加载策略参数失败: {exc}")

    def _build_strategy_factory(self):
        """返回一个每次调用都产生新策略实例的工厂函数"""
        sid = self.strategy_combo.currentData()
        if not sid:
            return None
        # 收集当前参数值
        params = {}
        for pname, widget in self._param_widgets.items():
            if hasattr(widget, "value"):
                params[pname] = widget.value()
            else:
                params[pname] = widget.text()

        def factory():
            instance = strategy_config_manager.create_strategy(sid)
            merged_params = dict(params)
            merged_params["sizing_mode"] = "fixed_amount"
            merged_params["trade_amount"] = self.trade_amount_spin.value()
            if merged_params and hasattr(instance, "set_parameters"):
                instance.set_parameters(merged_params)
            return instance

        return factory

    # ------------------------------------------------------------------
    # 股票池 / 股票列表
    # ------------------------------------------------------------------

    def refresh_from_db(self):
        """外部调用：数据下载后刷新本地股票列表"""
        self._refresh_local_codes()
        self._on_pool_changed(self.pool_combo.currentIndex())

    def _refresh_local_codes(self):
        """从 DB 读取全部本地股票代码"""
        try:
            db = DatabaseManager(DB_PATH)
            rows = db.execute_query(
                "SELECT DISTINCT ts_code FROM stock_daily ORDER BY ts_code"
            )
            self._all_local_codes = [r["ts_code"] for r in rows]
            self._log(f"本地共有 {len(self._all_local_codes)} 只股票数据")
        except Exception as exc:
            self._log(f"读取本地股票列表失败: {exc}")
            self._all_local_codes = []

    def _on_pool_changed(self, _idx: int):
        pool = self.pool_combo.currentData()
        if pool == "all_local":
            codes = self._all_local_codes
        else:
            # 从universe缓存获取pool成员，再与本地DB取交集
            codes = self._get_pool_intersection(pool)
        self._populate_stock_list(codes)
        self.pool_count_label.setText(str(len(codes)))

    def _get_pool_intersection(self, pool: str) -> List[str]:
        """返回指定池中本地已有数据的股票代码"""
        if pool in self._pool_codes:
            pool_set = set(self._pool_codes[pool])
        else:
            try:
                from ..data.universe import manager as um
                raw = um.get_pool(pool, force_refresh=False)
                # universe返回不带后缀的代码，需要与DB代码（带后缀）匹配
                raw_set = set(raw)
                # 尝试直接交集（如果DB也有纯代码）
                pool_set = raw_set
                self._pool_codes[pool] = list(raw_set)
            except Exception:
                return self._all_local_codes

        local_set = set(self._all_local_codes)
        # DB 代码带后缀 (000001.SZ), universe 缓存可能不带后缀，做宽松匹配
        matched = []
        for code in local_set:
            bare = code.split(".")[0]
            if code in pool_set or bare in pool_set:
                matched.append(code)
        return sorted(matched)

    def _populate_stock_list(self, codes: List[str]):
        self.stock_list.blockSignals(True)
        self.stock_list.clear()
        for code in codes:
            item = QListWidgetItem(code)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.stock_list.addItem(item)
        self.stock_list.blockSignals(False)
        self._update_selected_count()

    def _filter_stock_list(self, text: str):
        text = text.strip().lower()
        for i in range(self.stock_list.count()):
            item = self.stock_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _select_all(self):
        self.stock_list.blockSignals(True)
        for i in range(self.stock_list.count()):
            self.stock_list.item(i).setCheckState(Qt.Checked)
        self.stock_list.blockSignals(False)
        self._update_selected_count()

    def _deselect_all(self):
        self.stock_list.blockSignals(True)
        for i in range(self.stock_list.count()):
            self.stock_list.item(i).setCheckState(Qt.Unchecked)
        self.stock_list.blockSignals(False)
        self._update_selected_count()

    def _on_item_changed(self, _item):
        self._update_selected_count()

    def _update_selected_count(self):
        cnt = sum(
            1 for i in range(self.stock_list.count())
            if self.stock_list.item(i).checkState() == Qt.Checked
        )
        self.selected_label.setText(f"已选: {cnt} 只")

    def _get_selected_codes(self) -> List[str]:
        return [
            self.stock_list.item(i).text()
            for i in range(self.stock_list.count())
            if self.stock_list.item(i).checkState() == Qt.Checked
        ]

    # ------------------------------------------------------------------
    # 回测执行
    # ------------------------------------------------------------------

    def _start_backtest(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示", "回测正在进行中，请等待或取消")
            return

        codes = self._get_selected_codes()
        if not codes:
            QMessageBox.warning(self, "警告", "请先选择至少一只股票")
            return

        factory = self._build_strategy_factory()
        if factory is None:
            QMessageBox.warning(self, "警告", "请选择策略")
            return

        start = datetime(
            self.bt_start.date().year(),
            self.bt_start.date().month(),
            self.bt_start.date().day(),
        )
        end = datetime(
            self.bt_end.date().year(),
            self.bt_end.date().month(),
            self.bt_end.date().day(),
        )
        if start >= end:
            QMessageBox.warning(self, "警告", "开始日期必须早于结束日期")
            return

        self._log(
            f"开始批量回测 {len(codes)} 只股票，策略: "
            f"{self.strategy_combo.currentText()}，"
            f"{start.date()} ~ {end.date()}"
        )
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(codes))
        self.log_text.clear()

        self._worker = BatchBacktestWorker(
            ts_codes=codes,
            strategy_factory=factory,
            start_date=start,
            end_date=end,
            initial_cash=self.cash_spin.value(),
            commission_rate=self.commission_spin.value(),
            slippage_rate=self.slippage_spin.value(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._worker.start()

    def _cancel_backtest(self):
        if self._worker:
            self._worker.cancel()
            self._log("用户取消回测…")
        self.cancel_btn.setEnabled(False)

    def _on_progress(self, current: int, total: int, ts: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        pct = int(current / total * 100) if total else 0
        self.progress_label.setText(
            f"进度 {current}/{total}（{pct}%）" + (f" — {ts}" if ts else "")
        )

    def _on_finished(self, results: list):
        self._log(f"批量回测完成，共 {len(results)} 只股票成功")
        self.progress_label.setText(f"完成：{len(results)} 只成功")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if results:
            self.backtest_finished.emit(results)

    def _on_error(self, msg: str):
        self._log(f"回测出错: {msg}")
        QMessageBox.critical(self, "错误", f"批量回测失败: {msg}")
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {msg}")
