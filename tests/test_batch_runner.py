"""
BatchRunner 单元测试

使用 mock 替换 BacktestEngine，验证批量调度逻辑：进度回调、单股票失败
不中断整体流程、取消机制、strategy_factory 调用方式等。

运行方式: python tests/test_batch_runner.py
"""

import sys
import time
import threading
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.batch_runner import BatchRunner
from src.backtesting.result import BacktestResult
from src.trading.strategy import Strategy
from src.trading.bar_data import BarData


# ─── 辅助 ─────────────────────────────────────────────────────────────────────

START = datetime(2023, 1, 1)
END   = datetime(2023, 12, 31)


def _make_fake_result(symbol: str) -> BacktestResult:
    """返回一个合法的 BacktestResult（无需真实数据）"""
    return BacktestResult(
        strategy_name='test',
        symbols=[symbol],
        start_date=START,
        end_date=END,
        initial_cash=100_000.0,
        final_value=110_000.0,
        trades=[],
        daily_portfolio=[
            {'date': None, 'total_value': 100_000.0, 'cash': 100_000.0,
             'position_value': 0.0, 'positions': {}},
            {'date': None, 'total_value': 110_000.0, 'cash': 110_000.0,
             'position_value': 0.0, 'positions': {}},
        ],
    )


class _DummyStrategy(Strategy):
    def on_init(self): pass
    def on_bar(self, bar: BarData): pass


def _factory():
    return _DummyStrategy('dummy', 'Dummy')


# ─── 测试 ─────────────────────────────────────────────────────────────────────

def test_run_returns_results_for_all_stocks():
    """成功回测的股票数 = ts_codes 长度"""
    codes = ['000001', '000002', '000003']
    runner = BatchRunner()

    with patch(
        'src.backtesting.batch_runner.BacktestEngine.run_backtest',
        side_effect=lambda strategy, syms: _make_fake_result(syms[0]),
    ):
        results = runner.run(codes, _factory, START, END, persist_results=False)

    assert len(results) == 3, f"期望 3 个结果，实际 {len(results)}"
    print(f"✓ 全部成功时返回 {len(results)} 个结果")


def test_strategy_factory_called_once_per_stock():
    """strategy_factory 每只股票调用一次"""
    codes = ['A', 'B', 'C']
    call_count = [0]

    def counting_factory():
        call_count[0] += 1
        return _DummyStrategy('sid', 'Dummy')

    runner = BatchRunner()
    with patch(
        'src.backtesting.batch_runner.BacktestEngine.run_backtest',
        side_effect=lambda strategy, syms: _make_fake_result(syms[0]),
    ):
        runner.run(codes, counting_factory, START, END, persist_results=False)

    assert call_count[0] == 3, f"期望 factory 调用 3 次，实际 {call_count[0]} 次"
    print(f"✓ strategy_factory 调用次数: {call_count[0]}")


def test_single_stock_failure_does_not_abort():
    """一只股票回测抛出异常，其他股票应继续完成"""
    codes = ['OK1', 'BAD', 'OK2']
    call_results = {'OK1': _make_fake_result('OK1'), 'OK2': _make_fake_result('OK2')}

    def side_effect(strategy, syms):
        code = syms[0]
        if code == 'BAD':
            raise RuntimeError("故意失败")
        return call_results[code]

    runner = BatchRunner()
    with patch(
        'src.backtesting.batch_runner.BacktestEngine.run_backtest',
        side_effect=side_effect,
    ):
        results = runner.run(codes, _factory, START, END, persist_results=False)

    # BAD 失败，OK1/OK2 成功 → 应有 2 个结果
    assert len(results) == 2, f"期望 2 个结果，实际 {len(results)}"
    returned_symbols = [r.symbols[0] for r in results]
    assert 'OK1' in returned_symbols
    assert 'OK2' in returned_symbols
    assert 'BAD' not in returned_symbols
    print(f"✓ 单股票失败不中断: {returned_symbols}")


def test_on_progress_callback_called():
    """on_progress 回调应在每只股票处理时被调用"""
    codes = ['A', 'B']
    progress_calls = []

    def on_progress(current, total, code):
        progress_calls.append((current, total, code))

    runner = BatchRunner()
    with patch(
        'src.backtesting.batch_runner.BacktestEngine.run_backtest',
        side_effect=lambda strategy, syms: _make_fake_result(syms[0]),
    ):
        runner.run(codes, _factory, START, END,
                   on_progress=on_progress, persist_results=False)

    assert len(progress_calls) >= len(codes), \
        f"回调次数 {len(progress_calls)} 应 >= {len(codes)}"
    print(f"✓ on_progress 回调: {progress_calls}")


def test_progress_callback_final_call():
    """最后一次 on_progress 应以 (total, total, '') 报告完成"""
    codes = ['X', 'Y']
    last_call = [None]

    def on_progress(current, total, code):
        last_call[0] = (current, total, code)

    runner = BatchRunner()
    with patch(
        'src.backtesting.batch_runner.BacktestEngine.run_backtest',
        side_effect=lambda strategy, syms: _make_fake_result(syms[0]),
    ):
        runner.run(codes, _factory, START, END,
                   on_progress=on_progress, persist_results=False)

    assert last_call[0] is not None
    final_current, final_total, final_code = last_call[0]
    assert final_current == final_total, \
        f"最终回调应 current==total，实际 {final_current}/{final_total}"
    print(f"✓ 最终进度回调: ({final_current}, {final_total}, '{final_code}')")


def test_cancel_stops_run():
    """调用 cancel() 后，后续股票不再被回测"""
    codes = ['S1', 'S2', 'S3', 'S4', 'S5']
    runner = BatchRunner()
    processed = []

    def slow_run(strategy, syms):
        processed.append(syms[0])
        if len(processed) == 2:
            # 处理第 2 只股票后取消
            runner.cancel()
        return _make_fake_result(syms[0])

    with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
               side_effect=slow_run):
        results = runner.run(codes, _factory, START, END, persist_results=False)

    # 取消后不应全部 5 只都处理完
    assert len(results) <= 4, f"取消后不应有 5 个结果，实际 {len(results)}"
    assert len(results) >= 1, "至少应完成 1 个"
    print(f"✓ cancel() 停止后续处理: 已处理 {len(results)} 只")


def test_empty_ts_codes():
    """空股票列表 → 返回空列表，不报错"""
    runner = BatchRunner()
    results = runner.run([], _factory, START, END, persist_results=False)
    assert results == []
    print("✓ 空股票列表 → 返回 []")


def test_persist_results_false_skips_db():
    """persist_results=False 时不调用 _persist_results"""
    runner = BatchRunner()
    with patch.object(runner, '_persist_results') as mock_persist:
        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=lambda strategy, syms: _make_fake_result(syms[0])):
            runner.run(['000001'], _factory, START, END, persist_results=False)
    mock_persist.assert_not_called()
    print("✓ persist_results=False 时跳过数据库写入")


def test_cancel_marks_remaining_status_as_cancelled():
    """取消后未处理标的应标记为 cancelled，且已完成结果可见"""
    codes = ['S1', 'S2', 'S3', 'S4']
    runner = BatchRunner()
    processed = []

    def slow_run(strategy, syms):
        code = syms[0]
        processed.append(code)
        if code == 'S2':
            runner.cancel()
        return _make_fake_result(code)

    with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest', side_effect=slow_run):
        results = runner.run(codes, _factory, START, END, persist_results=False)

    status = runner.get_last_run_status()
    assert len(results) == 2, f"取消后应仅完成2只，实际 {len(results)}"
    assert status['success'] == ['S1', 'S2']
    assert set(status['cancelled']) == {'S3', 'S4'}
    print(f"✓ 取消状态可见: success={status['success']} cancelled={status['cancelled']}")


def test_resume_incomplete_then_failed_scope():
    """续跑支持 incomplete 和 failed 范围"""
    codes = ['A', 'B', 'C']
    runner = BatchRunner()

    state = {'phase': 'first'}
    calls = []

    def side_effect(strategy, syms):
        code = syms[0]
        calls.append((state['phase'], code))

        if state['phase'] == 'first':
            if code == 'A':
                runner.cancel()
            return _make_fake_result(code)

        if state['phase'] == 'resume_incomplete':
            if code == 'B':
                raise RuntimeError('B failed in resume_incomplete')
            return _make_fake_result(code)

        # phase == resume_failed
        return _make_fake_result(code)

    with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest', side_effect=side_effect):
        first_results = runner.run(codes, _factory, START, END, persist_results=False)
        assert [r.symbols[0] for r in first_results] == ['A']

        state['phase'] = 'resume_incomplete'
        second_results = runner.resume(scope='incomplete', persist_results=False)
        assert [r.symbols[0] for r in second_results] == ['C']

        state['phase'] = 'resume_failed'
        third_results = runner.resume(scope='failed', persist_results=False)
        assert [r.symbols[0] for r in third_results] == ['B']

    print("✓ resume 支持 incomplete/failed 范围")


def test_persisted_config_json_contains_experiment_snapshot(tmp_path):
    """持久化结果应包含实验快照最小字段"""
    db_path = tmp_path / 'snapshot.db'
    runner = BatchRunner(str(db_path))

    def snapshot_factory():
        return _DummyStrategy('dual_ma', 'DualMA', params={'short': 5, 'long': 20})

    with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
               side_effect=lambda strategy, syms: _make_fake_result(syms[0])):
        runner.run(['000001.SZ'], snapshot_factory, START, END, persist_results=True)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT config_json FROM backtest_results ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None and row[0], "应存在持久化 config_json"
    cfg = json.loads(row[0])
    snap = cfg.get('experiment_snapshot')
    assert isinstance(snap, dict), "应包含 experiment_snapshot"
    assert snap.get('ts_codes_snapshot') == ['000001.SZ']
    assert snap.get('start_date') == START.strftime('%Y%m%d')
    assert snap.get('end_date') == END.strftime('%Y%m%d')
    assert snap.get('strategy_snapshot', {}).get('strategy_params') == {'short': 5, 'long': 20}
    print("✓ 持久化快照字段完整")


if __name__ == '__main__':
    tests = [
        test_run_returns_results_for_all_stocks,
        test_strategy_factory_called_once_per_stock,
        test_single_stock_failure_does_not_abort,
        test_on_progress_callback_called,
        test_progress_callback_final_call,
        test_cancel_stops_run,
        test_empty_ts_codes,
        test_persist_results_false_skips_db,
        test_cancel_marks_remaining_status_as_cancelled,
        test_resume_incomplete_then_failed_scope,
        test_persisted_config_json_contains_experiment_snapshot,
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
