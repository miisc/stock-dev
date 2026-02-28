"""
ResultAggregator 单元测试

使用合成的 BacktestResult 列表验证聚合器统计、排名和导出功能。
运行方式: python tests/test_aggregator.py
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.result import BacktestResult
from src.analysis.aggregator import ResultAggregator


# ─── 辅助函数 ──────────────────────────────────────────────────────────────────

def make_result(symbol, final_value, initial_cash=100_000.0,
                trades=None, n_days=252,
                strategy_name='TestStrategy') -> BacktestResult:
    """创建最简单的 BacktestResult，用固定涨幅模拟每日组合价值。"""
    start = datetime(2023, 1, 1)
    end   = datetime(2023, 12, 31)
    # 生成线性增长的每日组合值（简化：不影响聚合器测试）
    step = (final_value - initial_cash) / max(n_days - 1, 1)
    daily_portfolio = [
        {'date': None, 'total_value': initial_cash + step * i,
         'cash': initial_cash + step * i, 'position_value': 0.0, 'positions': {}}
        for i in range(n_days)
    ]
    daily_portfolio[-1]['total_value'] = final_value   # ensure exact final value
    return BacktestResult(
        strategy_name=strategy_name,
        symbols=[symbol],
        start_date=start,
        end_date=end,
        initial_cash=initial_cash,
        final_value=final_value,
        trades=trades or [],
        daily_portfolio=daily_portfolio,
    )


# ─── 测试 ─────────────────────────────────────────────────────────────────────

def test_build_summary_columns():
    """build_summary 返回包含所有预期列的 DataFrame"""
    results = [make_result('000001', 110_000), make_result('000002', 90_000)]
    agg = ResultAggregator(results)
    df = agg.build_summary()
    for col in ResultAggregator.COLUMNS:
        assert col in df.columns, f"缺少列: {col}"
    print(f"✓ 列完整性: {list(df.columns)}")


def test_build_summary_row_count():
    """每只股票对应 DataFrame 中的 1 行"""
    results = [make_result(f'00000{i}', 100_000 + i * 5_000) for i in range(5)]
    agg = ResultAggregator(results)
    df = agg.build_summary()
    assert len(df) == 5, f"期望 5 行，实际 {len(df)} 行"
    print(f"✓ 行数: {len(df)}")


def test_build_summary_symbol_and_strategy():
    """code 和 strategy 列正确填充"""
    results = [make_result('000001', 110_000, strategy_name='DualMA')]
    agg = ResultAggregator(results)
    df = agg.build_summary()
    assert df.iloc[0]['code'] == '000001'
    assert df.iloc[0]['strategy'] == 'DualMA'
    print(f"✓ code={df.iloc[0]['code']}, strategy={df.iloc[0]['strategy']}")


def test_build_summary_total_return_sign():
    """total_return 正负符号正确"""
    results = [
        make_result('000001', 120_000),   # +20%
        make_result('000002',  80_000),   # -20%
    ]
    agg = ResultAggregator(results)
    df = agg.build_summary()
    assert df.loc[df['code'] == '000001', 'total_return'].iloc[0] > 0
    assert df.loc[df['code'] == '000002', 'total_return'].iloc[0] < 0
    print("✓ total_return 正负符号正确")


def test_overall_win_rate():
    """2 盈 1 亏 → 整体胜率 = 66.67%"""
    results = [
        make_result('A', 110_000),   # +10%
        make_result('B', 120_000),   # +20%
        make_result('C',  90_000),   # -10%
    ]
    agg = ResultAggregator(results)
    wr = agg.overall_win_rate()
    expected = round(2 / 3 * 100, 2)
    assert abs(wr - expected) < 0.01, f"期望 {expected}，实际 {wr}"
    print(f"✓ 整体胜率: {wr}% (期望 {expected}%)")


def test_overall_win_rate_all_positive():
    results = [make_result(f'{i:06d}', 110_000) for i in range(4)]
    agg = ResultAggregator(results)
    assert agg.overall_win_rate() == 100.0
    print("✓ 全盈利整体胜率: 100.0%")


def test_overall_win_rate_all_negative():
    results = [make_result(f'{i:06d}', 90_000) for i in range(3)]
    agg = ResultAggregator(results)
    assert agg.overall_win_rate() == 0.0
    print("✓ 全亏损整体胜率: 0.0%")


def test_overall_win_rate_empty():
    agg = ResultAggregator([])
    assert agg.overall_win_rate() == 0.0
    print("✓ 空列表整体胜率: 0.0%")


def test_top_n_returns_correct_count():
    results = [make_result(f'{i:06d}', 100_000 + i * 3_000) for i in range(10)]
    agg = ResultAggregator(results)
    top3 = agg.top_n(3, by='total_return')
    assert len(top3) == 3
    print(f"✓ top_n(3) 行数: {len(top3)}")


def test_top_n_sorted_descending():
    """top_n 应按 sharpe_ratio 降序排列"""
    results = [
        make_result('A', 150_000),   # 高收益
        make_result('B', 110_000),
        make_result('C', 120_000),
        make_result('D',  90_000),
    ]
    agg = ResultAggregator(results)
    top2 = agg.top_n(2, by='total_return')
    assert top2.iloc[0]['total_return'] >= top2.iloc[1]['total_return']
    print(f"✓ top_n 降序: {top2.iloc[0]['total_return']} >= {top2.iloc[1]['total_return']}")


def test_bottom_n_sorted_ascending():
    """bottom_n 应按 total_return 升序排列"""
    results = [
        make_result('A', 110_000),
        make_result('B',  80_000),
        make_result('C', 130_000),
        make_result('D',  70_000),
    ]
    agg = ResultAggregator(results)
    bot2 = agg.bottom_n(2, by='total_return')
    assert bot2.iloc[0]['total_return'] <= bot2.iloc[1]['total_return']
    print(f"✓ bottom_n 升序: {bot2.iloc[0]['total_return']} <= {bot2.iloc[1]['total_return']}")


def test_to_csv_creates_file():
    """to_csv 应创建文件，文件非空"""
    results = [make_result('000001', 110_000)]
    agg = ResultAggregator(results)
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, 'subdir', 'result.csv')
        returned_path = agg.to_csv(csv_path)
        assert os.path.exists(returned_path), "CSV 文件未创建"
        assert os.path.getsize(returned_path) > 0, "CSV 文件为空"
        print(f"✓ CSV 已创建: {returned_path}")


def test_to_csv_utf8_bom():
    """导出的 CSV 应以 UTF-8 BOM (EF BB BF) 开头，兼容 Excel"""
    results = [make_result('000001', 110_000)]
    agg = ResultAggregator(results)
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, 'result.csv')
        agg.to_csv(csv_path)
        with open(csv_path, 'rb') as f:
            bom = f.read(3)
        assert bom == b'\xef\xbb\xbf', f"BOM 错误: {bom!r}"
        print("✓ CSV UTF-8 BOM 正确")


def test_to_csv_column_headers():
    """CSV 第一行应包含所有列名"""
    import csv
    results = [make_result('000001', 110_000)]
    agg = ResultAggregator(results)
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, 'result.csv')
        agg.to_csv(csv_path)
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
        for col in ResultAggregator.COLUMNS:
            assert col in header, f"CSV 缺少列: {col}"
        print(f"✓ CSV 列名完整: {header}")


def test_summary_cached():
    """第二次访问 summary 不重新构建（缓存有效）"""
    results = [make_result('000001', 110_000)]
    agg = ResultAggregator(results)
    df1 = agg.summary
    df2 = agg.summary
    assert df1 is df2, "summary 未缓存（每次返回新对象）"
    print("✓ summary 缓存有效")


if __name__ == '__main__':
    tests = [
        test_build_summary_columns,
        test_build_summary_row_count,
        test_build_summary_symbol_and_strategy,
        test_build_summary_total_return_sign,
        test_overall_win_rate,
        test_overall_win_rate_all_positive,
        test_overall_win_rate_all_negative,
        test_overall_win_rate_empty,
        test_top_n_returns_correct_count,
        test_top_n_sorted_descending,
        test_bottom_n_sorted_ascending,
        test_to_csv_creates_file,
        test_to_csv_utf8_bom,
        test_to_csv_column_headers,
        test_summary_cached,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} 通过 / {failed} 失败")
