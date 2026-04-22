"""
T1: 股票池与输入规则 单元测试

覆盖预置池名称合法性校验、自定义输入格式（带/不带交易所后缀、前缀）、
去重、非法代码过滤的 5 组样例判定。

运行方式: pytest tests/test_stock_pool_rules.py -v
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.stock_pool import StockPoolManager


# ─── 辅助 ─────────────────────────────────────────────────────────────────────

MGR = StockPoolManager.__new__(StockPoolManager)  # 不需要真实 data_source


# ════════════════════════════════════════════════════════════════════════════
# is_valid_code — 单码校验
# ════════════════════════════════════════════════════════════════════════════

class TestIsValidCode:
    """样例 1：合法格式判定"""

    def test_bare_6_digits(self):
        assert StockPoolManager.is_valid_code("000001")

    def test_suffix_sz(self):
        assert StockPoolManager.is_valid_code("000001.SZ")

    def test_suffix_sh(self):
        assert StockPoolManager.is_valid_code("600000.SH")

    def test_suffix_bj(self):
        assert StockPoolManager.is_valid_code("430047.BJ")

    def test_prefix_sh(self):
        assert StockPoolManager.is_valid_code("sh600000")

    def test_prefix_sz(self):
        assert StockPoolManager.is_valid_code("sz000001")

    def test_case_insensitive_suffix(self):
        assert StockPoolManager.is_valid_code("000001.sz")

    """样例 2：非法格式判定"""

    def test_too_short(self):
        assert not StockPoolManager.is_valid_code("00001")

    def test_too_long(self):
        assert not StockPoolManager.is_valid_code("0000011")

    def test_non_numeric(self):
        assert not StockPoolManager.is_valid_code("ABCDEF")

    def test_empty_string(self):
        assert not StockPoolManager.is_valid_code("")

    def test_whitespace_only(self):
        assert not StockPoolManager.is_valid_code("   ")

    def test_invalid_suffix(self):
        assert not StockPoolManager.is_valid_code("000001.XX")


# ════════════════════════════════════════════════════════════════════════════
# validate_codes — 批量校验
# ════════════════════════════════════════════════════════════════════════════

class TestValidateCodes:
    """样例 3：混合输入去重与非法过滤"""

    def test_all_valid_no_dup(self):
        codes = ["000001", "600000.SH", "300001.SZ"]
        result = StockPoolManager.validate_codes(codes)
        assert len(result["valid"]) == 3
        assert result["invalid"] == []
        assert result["duplicates"] == []

    def test_deduplicate_same_code_different_format(self):
        """000001 与 000001.SZ 代表同一股票，应去重"""
        codes = ["000001", "000001.SZ", "000001.sz"]
        result = StockPoolManager.validate_codes(codes)
        assert len(result["valid"]) == 1
        assert len(result["duplicates"]) == 2

    def test_invalid_codes_filtered(self):
        """非法代码被过滤到 invalid 列表，不进入 valid"""
        codes = ["000001", "INVALID", "ABCDEF", "600000"]
        result = StockPoolManager.validate_codes(codes)
        assert "000001.SZ" in result["valid"]
        assert "600000.SH" in result["valid"]
        assert "INVALID" in result["invalid"]
        assert "ABCDEF" in result["invalid"]

    def test_empty_input(self):
        result = StockPoolManager.validate_codes([])
        assert result["valid"] == []
        assert result["invalid"] == []
        assert result["duplicates"] == []

    def test_ts_code_normalization(self):
        """裸 6 位代码应被规范化为 ts_code 格式（含交易所后缀）"""
        result = StockPoolManager.validate_codes(["000001", "600000"])
        assert "000001.SZ" in result["valid"]
        assert "600000.SH" in result["valid"]


# ════════════════════════════════════════════════════════════════════════════
# build_custom_pool — DataFrame 输出
# ════════════════════════════════════════════════════════════════════════════

class TestBuildCustomPool:
    """样例 4：DataFrame 字段与去重"""

    def _mgr(self):
        from unittest.mock import MagicMock
        mgr = StockPoolManager.__new__(StockPoolManager)
        return mgr

    def test_columns_exist(self):
        mgr = self._mgr()
        df = mgr.build_custom_pool(["000001", "600000.SH"])
        assert "ts_code" in df.columns
        assert "symbol" in df.columns

    def test_invalid_codes_excluded(self):
        mgr = self._mgr()
        df = mgr.build_custom_pool(["000001", "INVALID_CODE"])
        ts_codes = df["ts_code"].tolist()
        assert "000001.SZ" in ts_codes
        assert "INVALID_CODE" not in ts_codes

    def test_dedup_in_output(self):
        """重复代码在 DataFrame 中只出现一次"""
        mgr = self._mgr()
        df = mgr.build_custom_pool(["000001", "000001.SZ"])
        assert len(df) == 1

    def test_empty_input_returns_empty_df(self):
        mgr = self._mgr()
        df = mgr.build_custom_pool([])
        assert df.empty


# ════════════════════════════════════════════════════════════════════════════
# 样例 5：5 组输入的通过 / 失败判定表
# ════════════════════════════════════════════════════════════════════════════

class TestSampleJudgmentTable:
    """5 组样例输入，模拟验收记录中的判定表。"""

    CASES = [
        # (输入列表, 期望通过数, 期望失败数)
        (["000001.SZ", "000002.SZ", "600000.SH"],        3, 0),   # 全合法
        (["ABCDEF", "12345", "INVALID"],                 0, 3),   # 全非法
        (["000001", "INVALID", "600000"],                2, 1),   # 混合
        (["000001", "000001.SZ", "000001.sz"],           1, 0),   # 全重复
        (["000001", "000002", "000003", "X", "Y"],       3, 2),   # 5 个混合
    ]

    def _run(self, codes, expected_valid, expected_invalid):
        result = StockPoolManager.validate_codes(codes)
        # duplicates count as valid (already added once)
        assert len(result["valid"]) == expected_valid, \
            f"valid 期望 {expected_valid}, 实际 {len(result['valid'])}: {result}"
        assert len(result["invalid"]) == expected_invalid, \
            f"invalid 期望 {expected_invalid}, 实际 {len(result['invalid'])}: {result}"

    def test_case_1_all_valid(self):
        self._run(*self.CASES[0])

    def test_case_2_all_invalid(self):
        self._run(*self.CASES[1])

    def test_case_3_mixed(self):
        self._run(*self.CASES[2])

    def test_case_4_all_duplicates(self):
        self._run(*self.CASES[3])

    def test_case_5_large_mixed(self):
        self._run(*self.CASES[4])
