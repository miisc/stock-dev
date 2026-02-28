"""
策略配置管理面板

功能：
  - 查看所有已注册策略及参数说明
  - 实时编辑策略默认参数
  - 保存/加载参数预设（JSON 文件）
  - 验证参数合法性
"""
from __future__ import annotations

import json
from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QComboBox, QSplitter, QTextEdit,
    QDoubleSpinBox, QSpinBox, QLineEdit, QCheckBox,
    QFileDialog, QMessageBox, QScrollArea, QFrame,
)

from ..trading import strategy_config_manager


class StrategyPanel(QWidget):
    """策略配置管理面板"""

    # 策略参数保存后通知外部（例如 BacktestPanel 刷新）
    strategy_updated = pyqtSignal(str)   # strategy_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._param_widgets: Dict[str, QWidget] = {}
        self._current_sid: Optional[str] = None
        self._init_ui()
        self._load_strategies()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # ── 左列：策略列表 + 说明 ──────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        select_group = QGroupBox("策略列表")
        select_form = QFormLayout(select_group)

        self.strategy_combo = QComboBox()
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        select_form.addRow("选择策略:", self.strategy_combo)

        left_layout.addWidget(select_group)

        desc_group = QGroupBox("策略描述")
        desc_layout = QVBoxLayout(desc_group)
        self.desc_label = QLabel("—")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #444; padding: 4px;")
        desc_layout.addWidget(self.desc_label)
        left_layout.addWidget(desc_group)

        # 参数说明文档
        doc_group = QGroupBox("参数说明")
        doc_layout = QVBoxLayout(doc_group)
        self.doc_text = QTextEdit()
        self.doc_text.setReadOnly(True)
        self.doc_text.setFont(QFont("Consolas", 9))
        self.doc_text.setStyleSheet("background: #f8f9fa;")
        doc_layout.addWidget(self.doc_text)
        left_layout.addWidget(doc_group)

        splitter.addWidget(left)

        # ── 右列：参数编辑 ────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        params_group = QGroupBox("参数配置")
        params_outer = QVBoxLayout(params_group)

        # 滚动区域承载参数控件
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self._params_container = QWidget()
        self.params_form = QFormLayout(self._params_container)
        self.params_form.setLabelAlignment(Qt.AlignRight)
        scroll.setWidget(self._params_container)
        params_outer.addWidget(scroll)
        right_layout.addWidget(params_group)

        # 操作按钮行
        btn_row = QHBoxLayout()

        self.apply_btn = QPushButton("✔ 应用参数")
        self.apply_btn.setStyleSheet(
            "QPushButton { background:#1976D2; color:white; font-weight:bold; padding:7px 16px; }"
            "QPushButton:hover { background:#1565C0; }"
        )
        self.apply_btn.clicked.connect(self._apply_params)

        self.reset_btn = QPushButton("↺ 重置默认")
        self.reset_btn.setStyleSheet("QPushButton { padding:7px 14px; }")
        self.reset_btn.clicked.connect(self._reset_params)

        self.save_preset_btn = QPushButton("💾 保存预设")
        self.save_preset_btn.setStyleSheet("QPushButton { padding:7px 14px; }")
        self.save_preset_btn.clicked.connect(self._save_preset)

        self.load_preset_btn = QPushButton("📂 加载预设")
        self.load_preset_btn.setStyleSheet("QPushButton { padding:7px 14px; }")
        self.load_preset_btn.clicked.connect(self._load_preset)

        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_preset_btn)
        btn_row.addWidget(self.load_preset_btn)
        right_layout.addLayout(btn_row)

        # 状态提示
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #388E3C; font-style: italic; padding: 2px;")
        right_layout.addWidget(self.status_label)

        splitter.addWidget(right)
        splitter.setSizes([320, 480])

    # ------------------------------------------------------------------
    # 策略加载
    # ------------------------------------------------------------------

    def _load_strategies(self):
        try:
            strategies = strategy_config_manager.get_all_strategies()
            self.strategy_combo.blockSignals(True)
            self.strategy_combo.clear()
            for sid, info in strategies.items():
                self.strategy_combo.addItem(f"{info['name']}  [{sid}]", sid)
            self.strategy_combo.blockSignals(False)
            if strategies:
                self._on_strategy_changed(0)
        except Exception as exc:
            self.status_label.setText(f"加载策略失败: {exc}")
            self.status_label.setStyleSheet("color: #C62828;")

    def _on_strategy_changed(self, _idx: int):
        sid = self.strategy_combo.currentData()
        if not sid:
            return
        self._current_sid = sid
        try:
            cfg = strategy_config_manager.get_strategy_config(sid)
            if cfg is None:
                return
            self.desc_label.setText(cfg.description or "（无描述）")
            self._build_param_widgets(cfg)
            self._build_doc(cfg)
        except Exception as exc:
            self.status_label.setText(f"加载策略参数失败: {exc}")

    # ------------------------------------------------------------------
    # 参数控件构建
    # ------------------------------------------------------------------

    def _build_param_widgets(self, cfg):
        """根据策略配置构建参数编辑控件"""
        # 清旧控件
        while self.params_form.count():
            item = self.params_form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._param_widgets.clear()

        for pname, pcfg in cfg.parameters.items():
            if pcfg.type == bool:
                w = QCheckBox()
                w.setChecked(bool(pcfg.default_value))
            elif pcfg.type == int:
                w = QSpinBox()
                w.setRange(int(pcfg.min_value or 0), int(pcfg.max_value or 100000))
                w.setValue(int(pcfg.default_value))
            elif pcfg.type == float:
                w = QDoubleSpinBox()
                w.setRange(float(pcfg.min_value or 0), float(pcfg.max_value or 100000))
                w.setDecimals(4)
                w.setSingleStep(0.001 if (pcfg.max_value or 1) <= 1 else 1)
                w.setValue(float(pcfg.default_value))
            else:
                w = QLineEdit(str(pcfg.default_value))

            self._param_widgets[pname] = w
            label = QLabel(f"{pcfg.name}:")
            label.setToolTip(pcfg.description)
            self.params_form.addRow(label, w)

    def _build_doc(self, cfg):
        """生成参数说明文档文本"""
        lines = [f"策略：{cfg.name}", f"ID：{cfg.strategy_id}", ""]
        for pname, pcfg in cfg.parameters.items():
            range_str = ""
            if pcfg.min_value is not None or pcfg.max_value is not None:
                range_str = f"  范围: [{pcfg.min_value} ~ {pcfg.max_value}]"
            lines.append(
                f"• {pname} ({pcfg.type.__name__}){range_str}\n"
                f"  默认值: {pcfg.default_value}\n"
                f"  说明: {pcfg.description or '—'}"
            )
        self.doc_text.setPlainText("\n\n".join(lines))

    # ------------------------------------------------------------------
    # 按钮操作
    # ------------------------------------------------------------------

    def _get_current_params(self) -> Dict[str, Any]:
        """从控件读取当前参数值"""
        params = {}
        for pname, widget in self._param_widgets.items():
            if isinstance(widget, QCheckBox):
                params[pname] = widget.isChecked()
            elif hasattr(widget, "value"):
                params[pname] = widget.value()
            else:
                params[pname] = widget.text()
        return params

    def _apply_params(self):
        """把当前控件值写入策略默认参数"""
        if not self._current_sid:
            return
        cfg = strategy_config_manager.get_strategy_config(self._current_sid)
        if cfg is None:
            return
        params = self._get_current_params()
        if cfg.validate_parameters(params):
            cfg.default_parameters.update(params)
            self.status_label.setText(f"✔ 参数已应用：{cfg.name}")
            self.status_label.setStyleSheet("color: #388E3C; font-style: italic;")
            self.strategy_updated.emit(self._current_sid)
        else:
            QMessageBox.warning(self, "参数错误", "参数验证失败，请检查输入值范围。")

    def _reset_params(self):
        """重置为策略默认参数"""
        if not self._current_sid:
            return
        cfg = strategy_config_manager.get_strategy_config(self._current_sid)
        if cfg is None:
            return
        for pname, widget in self._param_widgets.items():
            pcfg = cfg.parameters.get(pname)
            if pcfg is None:
                continue
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(pcfg.default_value))
            elif hasattr(widget, "setValue"):
                widget.setValue(type(pcfg.default_value)(pcfg.default_value))
            else:
                widget.setText(str(pcfg.default_value))
        self.status_label.setText("↺ 已重置为默认值")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")

    def _save_preset(self):
        """保存当前参数到 JSON 预设文件"""
        if not self._current_sid:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存策略预设",
            f"preset_{self._current_sid}.json",
            "JSON 文件 (*.json)"
        )
        if not path:
            return
        params = self._get_current_params()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "strategy_id": self._current_sid,
                    "parameters": params,
                }, f, indent=2, ensure_ascii=False)
            self.status_label.setText(f"💾 预设已保存: {path}")
            self.status_label.setStyleSheet("color: #388E3C; font-style: italic;")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _load_preset(self):
        """从 JSON 预设文件加载参数"""
        path, _ = QFileDialog.getOpenFileName(
            self, "加载策略预设", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sid = data.get("strategy_id", "")
            params = data.get("parameters", {})

            # 如果预设对应的策略与当前不同，切换策略
            if sid and sid != self._current_sid:
                for i in range(self.strategy_combo.count()):
                    if self.strategy_combo.itemData(i) == sid:
                        self.strategy_combo.setCurrentIndex(i)
                        break

            # 填充参数
            for pname, val in params.items():
                if pname not in self._param_widgets:
                    continue
                widget = self._param_widgets[pname]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(val))
                elif hasattr(widget, "setValue"):
                    widget.setValue(val)
                else:
                    widget.setText(str(val))

            self.status_label.setText(f"📂 预设已加载: {path}")
            self.status_label.setStyleSheet("color: #1976D2; font-style: italic;")
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", str(exc))
