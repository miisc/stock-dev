"""
T4: 策略参数字典与校验 — 10 组合法/非法参数校验演练

完成标准：
  - 参数类型、范围、默认值、必填项、错误提示规则完整。
  - 合法参数通过校验；非法参数被拦截并输出错误信息。

运行方式: pytest tests/test_strategy_param_validation.py -v
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.trading.strategy_config import StrategyParameter, StrategyConfig, StrategyConfigManager
from src.trading.strategies import DualMovingAverageStrategy


# ─── 公共 fixture ──────────────────────────────────────────────────────────────

def _make_config() -> StrategyConfig:
    """构造含多种参数类型的测试策略配置。"""
    return StrategyConfig(
        strategy_id="t4_test",
        strategy_class=DualMovingAverageStrategy,
        name="T4测试策略",
        parameters={
            "window": StrategyParameter(
                name="window", type=int, default_value=10,
                min_value=1, max_value=200, required=True,
            ),
            "threshold": StrategyParameter(
                name="threshold", type=float, default_value=0.02,
                min_value=0.0, max_value=1.0, required=True,
            ),
            "mode": StrategyParameter(
                name="mode", type=str, default_value="aggressive",
                choices=["aggressive", "conservative", "neutral"],
                required=True,
            ),
            "optional_note": StrategyParameter(
                name="optional_note", type=str, default_value="",
                required=False,
            ),
        },
    )


# ════════════════════════════════════════════════════════════════════════════
# 10-case 校验演练表
# ════════════════════════════════════════════════════════════════════════════

class TestTenCaseValidation:
    """10 组合法 / 非法参数校验，验收记录用：需全部通过/被拦截。"""

    def _cfg(self):
        return _make_config()

    # --- 合法样例 (5 组) ---

    def test_01_all_valid_defaults(self):
        """Case 01 合法 — 默认值应全部通过校验"""
        cfg = self._cfg()
        params = {"window": 10, "threshold": 0.02, "mode": "aggressive"}
        assert cfg.validate_parameters(params), "默认值参数组合应通过"

    def test_02_min_boundary(self):
        """Case 02 合法 — 边界下限值（window=1, threshold=0.0）"""
        cfg = self._cfg()
        params = {"window": 1, "threshold": 0.0, "mode": "neutral"}
        assert cfg.validate_parameters(params), "下限边界值应通过"

    def test_03_max_boundary(self):
        """Case 03 合法 — 边界上限值（window=200, threshold=1.0）"""
        cfg = self._cfg()
        params = {"window": 200, "threshold": 1.0, "mode": "conservative"}
        assert cfg.validate_parameters(params), "上限边界值应通过"

    def test_04_with_optional_param(self):
        """Case 04 合法 — 含可选参数"""
        cfg = self._cfg()
        params = {"window": 50, "threshold": 0.05, "mode": "neutral",
                  "optional_note": "自定义备注"}
        assert cfg.validate_parameters(params), "含可选参数应通过"

    def test_05_type_coercible_int(self):
        """Case 05 合法 — 字符串 '20' 可被强制转换为 int"""
        cfg = self._cfg()
        param = StrategyParameter(name="window", type=int, default_value=10,
                                  min_value=1, max_value=200)
        # validate() 内部尝试 type(value) 强制转换
        assert param.validate("20"), "可强制转换的字符串值应通过"

    # --- 非法样例 (5 组) ---

    def test_06_missing_required_param(self):
        """Case 06 非法 — 缺少必填参数 window"""
        cfg = self._cfg()
        params = {"threshold": 0.02, "mode": "aggressive"}   # 缺 window
        assert not cfg.validate_parameters(params), "缺少必填参数应被拦截"

    def test_07_below_min_value(self):
        """Case 07 非法 — window=0 小于 min_value=1"""
        cfg = self._cfg()
        param = cfg.parameters["window"]
        assert not param.validate(0), "低于最小值应被拦截"

    def test_08_above_max_value(self):
        """Case 08 非法 — window=201 大于 max_value=200"""
        cfg = self._cfg()
        param = cfg.parameters["window"]
        assert not param.validate(201), "超过最大值应被拦截"

    def test_09_invalid_choice(self):
        """Case 09 非法 — mode='turbo' 不在 choices 列表"""
        cfg = self._cfg()
        param = cfg.parameters["mode"]
        assert not param.validate("turbo"), "不在 choices 列表的值应被拦截"

    def test_10_wrong_type_unconvertible(self):
        """Case 10 非法 — threshold='abc' 无法转换为 float"""
        cfg = self._cfg()
        param = cfg.parameters["threshold"]
        assert not param.validate("abc"), "无法转换类型的值应被拦截"


# ════════════════════════════════════════════════════════════════════════════
# StrategyConfigManager 工厂方法
# ════════════════════════════════════════════════════════════════════════════

class TestStrategyConfigManager:
    def test_dual_ma_registered(self):
        mgr = StrategyConfigManager()
        assert "dual_ma" in mgr.list_strategies()

    def test_rsi_registered(self):
        mgr = StrategyConfigManager()
        assert "rsi" in mgr.list_strategies()

    def test_create_with_invalid_params_raises(self):
        mgr = StrategyConfigManager()
        with pytest.raises(ValueError):
            mgr.create_strategy("dual_ma", {"short_window": -1, "long_window": 5})

    def test_create_with_valid_params(self):
        mgr = StrategyConfigManager()
        strategy = mgr.create_strategy("dual_ma", {"short_window": 5, "long_window": 20})
        assert strategy is not None

    def test_default_parameters_match_param_definitions(self):
        """默认参数值必须来源于参数定义，且通过各自的校验规则"""
        mgr = StrategyConfigManager()
        for sid in mgr.list_strategies():
            cfg = mgr.get_strategy_config(sid)
            for pname, pdef in cfg.parameters.items():
                default = cfg.default_parameters.get(pname)
                if default is not None:
                    assert pdef.validate(default), \
                        f"策略 {sid} 参数 {pname} 的默认值 {default} 未通过自身校验规则"
