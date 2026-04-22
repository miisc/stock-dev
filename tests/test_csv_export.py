"""
T9: CSV 导出规范 — 验证汇总 CSV 与交易记录 CSV 的格式规范

完成标准：
  - 字段顺序固定、时间格式 YYYY-MM-DD、编码 UTF-8 BOM、数值精度统一。
  - 常见表格工具（Excel）可正确解析（UTF-8 BOM 标志）。

运行方式: pytest tests/test_csv_export.py -v
"""
import sys
import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.result import BacktestResult
from src.analysis.aggregator import ResultAggregator


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _make_result(symbol: str = '000001', final_value: float = 110_000.0,
                 trades=None) -> BacktestResult:
    start, end = datetime(2023, 1, 1), datetime(2023, 12, 31)
    initial = 100_000.0
    n = 252
    step = (final_value - initial) / max(n - 1, 1)
    dp = [
        {'date': None, 'total_value': initial + step * i,
         'cash': initial + step * i, 'position_value': 0.0, 'positions': {}}
        for i in range(n)
    ]
    dp[-1]['total_value'] = final_value
    return BacktestResult(
        strategy_name='T9', symbols=[symbol],
        start_date=start, end_date=end,
        initial_cash=initial, final_value=final_value,
        trades=trades or [], daily_portfolio=dp,
    )


def _make_trade(symbol: str, date: str = '2023-03-15') -> dict:
    return {
        'ts_code': symbol,
        'trade_date': date,
        'direction': 'BUY',
        'price': 12.3456789,
        'volume': 100,
        'amount': 1234.56789,
        'pnl': 55.123456,
    }


# ════════════════════════════════════════════════════════════════════════════
# 汇总 CSV 规范
# ════════════════════════════════════════════════════════════════════════════

class TestSummaryCSV:
    def _export(self, results, tmpdir):
        agg = ResultAggregator(results)
        path = os.path.join(tmpdir, 'summary.csv')
        agg.to_csv(path)
        return path

    def test_utf8_bom(self):
        """文件开头应有 UTF-8 BOM（EF BB BF），兼容 Excel 直接打开"""
        with tempfile.TemporaryDirectory() as d:
            path = self._export([_make_result()], d)
            with open(path, 'rb') as f:
                bom = f.read(3)
            assert bom == b'\xef\xbb\xbf', f"BOM 不正确: {bom!r}"

    def test_column_order_fixed(self):
        """列顺序应与 ResultAggregator.COLUMNS 完全一致"""
        with tempfile.TemporaryDirectory() as d:
            path = self._export([_make_result()], d)
            with open(path, encoding='utf-8-sig') as f:
                header = next(csv.reader(f))
            assert header == ResultAggregator.COLUMNS, \
                f"列顺序不符: {header}"

    def test_date_format_yyyy_mm_dd(self):
        """start_date / end_date 列格式应为 YYYY-MM-DD"""
        import re
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        with tempfile.TemporaryDirectory() as d:
            path = self._export([_make_result()], d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            assert rows, "CSV 数据行为空"
            for row in rows:
                assert pattern.match(row['start_date']), \
                    f"start_date 格式错误: {row['start_date']}"
                assert pattern.match(row['end_date']), \
                    f"end_date 格式错误: {row['end_date']}"

    def test_numeric_precision_total_return(self):
        """total_return 精度为 2 位小数"""
        with tempfile.TemporaryDirectory() as d:
            path = self._export([_make_result(final_value=115_000.0)], d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            val = rows[0]['total_return']
            # should have at most 2 decimal digits
            parts = val.split('.')
            if len(parts) == 2:
                assert len(parts[1]) <= 2, f"total_return 精度超 2 位: {val}"

    def test_multiple_rows(self):
        """多只股票对应多行"""
        results = [_make_result(f'{i:06d}', 100_000 + i * 3_000) for i in range(4)]
        with tempfile.TemporaryDirectory() as d:
            path = self._export(results, d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 4

    def test_file_not_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._export([_make_result()], d)
            assert os.path.getsize(path) > 0

    def test_parent_dir_auto_created(self):
        """to_csv 应自动创建父目录"""
        with tempfile.TemporaryDirectory() as d:
            deep_path = os.path.join(d, 'a', 'b', 'c', 'out.csv')
            agg = ResultAggregator([_make_result()])
            agg.to_csv(deep_path)
            assert os.path.exists(deep_path)


# ════════════════════════════════════════════════════════════════════════════
# 交易记录 CSV 规范
# ════════════════════════════════════════════════════════════════════════════

TRADE_COLUMNS = ["ts_code", "trade_date", "direction", "price", "volume", "amount", "pnl"]


class TestTradesCSV:
    def _export_trades(self, results, tmpdir, ts_code=None):
        agg = ResultAggregator(results)
        path = os.path.join(tmpdir, 'trades.csv')
        agg.trades_to_csv(path, ts_code=ts_code)
        return path

    def test_utf8_bom_trades(self):
        trades = [_make_trade('000001')]
        r = _make_result('000001', trades=trades)
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r], d)
            with open(path, 'rb') as f:
                bom = f.read(3)
            assert bom == b'\xef\xbb\xbf', f"交易记录 BOM 不正确: {bom!r}"

    def test_trade_column_order(self):
        """交易记录列顺序固定"""
        trades = [_make_trade('000001')]
        r = _make_result('000001', trades=trades)
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r], d)
            with open(path, encoding='utf-8-sig') as f:
                header = next(csv.reader(f))
            assert header == TRADE_COLUMNS, f"列顺序不符: {header}"

    def test_price_rounded_to_4_decimals(self):
        """price 精度 4 位小数"""
        trade = _make_trade('000001')
        trade['price'] = 12.3456789
        r = _make_result('000001', trades=[trade])
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r], d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            val = rows[0]['price']
            parts = val.split('.')
            if len(parts) == 2:
                assert len(parts[1]) <= 4, f"price 精度超 4 位: {val}"

    def test_filter_by_ts_code(self):
        """ts_code 过滤后只包含指定股票的交易"""
        r1 = _make_result('000001', trades=[_make_trade('000001')])
        r2 = _make_result('000002', trades=[_make_trade('000002')])
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r1, r2], d, ts_code='000001')
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            codes = {row['ts_code'] for row in rows}
            assert codes == {'000001'}, f"过滤后应只有 000001, 实际 {codes}"

    def test_no_trades_produces_header_only(self):
        """无交易时应只有标题行（空文件仍符合格式）"""
        r = _make_result('000001', trades=[])
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r], d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            assert rows == []

    def test_trade_date_string_preserved(self):
        """交易日期字符串（YYYY-MM-DD 格式）应原样保留"""
        import re
        trade = _make_trade('000001', date='2023-05-21')
        r = _make_result('000001', trades=[trade])
        with tempfile.TemporaryDirectory() as d:
            path = self._export_trades([r], d)
            with open(path, encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            assert rows[0]['trade_date'] == '2023-05-21'
