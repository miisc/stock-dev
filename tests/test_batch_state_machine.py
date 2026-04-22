"""
T5: 批量回测任务状态机 — 验证 3 类场景下的状态迁移与计数一致性

完成标准：
  1. 正常完成：所有股票状态 = success，statuses 计数一致。
  2. 部分失败：成功/失败分别计入，失败不中断其他股票。
  3. 手动取消：剩余 pending 迁移到 cancelled；已完成保留 success。

运行方式: pytest tests/test_batch_state_machine.py -v
"""
import sys
import threading
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.batch_runner import BatchRunner
from src.backtesting.result import BacktestResult
from src.trading.strategy import Strategy
from src.trading.bar_data import BarData

START = datetime(2023, 1, 1)
END   = datetime(2023, 12, 31)

# ─── 辅助 ─────────────────────────────────────────────────────────────────────

def _fake_result(symbol: str) -> BacktestResult:
    return BacktestResult(
        strategy_name='SM',
        symbols=[symbol],
        start_date=START, end_date=END,
        initial_cash=100_000.0, final_value=105_000.0,
        trades=[], daily_portfolio=[
            {'date': None, 'total_value': 100_000.0, 'cash': 100_000.0,
             'position_value': 0.0, 'positions': {}},
            {'date': None, 'total_value': 105_000.0, 'cash': 105_000.0,
             'position_value': 0.0, 'positions': {}},
        ],
    )


class _Dummy(Strategy):
    def on_init(self): pass
    def on_bar(self, bar: BarData): pass


def _factory():
    return _Dummy('dummy', 'Dummy')


# ════════════════════════════════════════════════════════════════════════════
# 场景 1：正常完成
# ════════════════════════════════════════════════════════════════════════════

class TestScenario1NormalCompletion:
    def test_all_success_status(self):
        """全部成功时，每只股票状态为 success"""
        codes = ['A', 'B', 'C']
        runner = BatchRunner()

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=lambda s, syms: _fake_result(syms[0])):
            runner.run(codes, _factory, START, END, persist_results=False)

        summary = runner.get_last_run_status()
        assert summary['total'] == 3
        assert len(summary['success']) == 3
        assert len(summary['failed']) == 0
        assert len(summary['cancelled']) == 0
        assert len(summary['pending']) == 0
        for code in codes:
            assert summary['statuses'][code] == 'success'

    def test_results_count_equals_total(self):
        """结果列表长度 = 股票总数"""
        codes = ['X', 'Y', 'Z']
        runner = BatchRunner()

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=lambda s, syms: _fake_result(syms[0])):
            results = runner.run(codes, _factory, START, END, persist_results=False)

        assert len(results) == 3

    def test_progress_callback_done_equals_total_at_end(self):
        """最终进度回调应 current == total"""
        codes = ['P', 'Q']
        last = [None]

        def cb(cur, tot, code):
            last[0] = (cur, tot)

        runner = BatchRunner()
        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=lambda s, syms: _fake_result(syms[0])):
            runner.run(codes, _factory, START, END, persist_results=False, on_progress=cb)

        assert last[0] is not None
        assert last[0][0] == last[0][1], f"final progress {last[0][0]} != {last[0][1]}"


# ════════════════════════════════════════════════════════════════════════════
# 场景 2：部分失败
# ════════════════════════════════════════════════════════════════════════════

class TestScenario2PartialFailure:
    def _run(self, codes, fail_code):
        runner = BatchRunner()

        def side_effect(s, syms):
            if syms[0] == fail_code:
                raise RuntimeError("故意失败")
            return _fake_result(syms[0])

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=side_effect):
            results = runner.run(codes, _factory, START, END, persist_results=False)

        return runner, results

    def test_failed_stock_status_is_failed(self):
        codes = ['OK1', 'BAD', 'OK2']
        runner, _ = self._run(codes, 'BAD')
        summary = runner.get_last_run_status()
        assert summary['statuses']['BAD'] == 'failed'

    def test_successful_stocks_status_is_success(self):
        codes = ['OK1', 'BAD', 'OK2']
        runner, _ = self._run(codes, 'BAD')
        summary = runner.get_last_run_status()
        assert summary['statuses']['OK1'] == 'success'
        assert summary['statuses']['OK2'] == 'success'

    def test_failed_stock_not_in_results(self):
        codes = ['OK1', 'BAD', 'OK2']
        _, results = self._run(codes, 'BAD')
        returned = [r.symbols[0] for r in results]
        assert 'BAD' not in returned
        assert 'OK1' in returned
        assert 'OK2' in returned

    def test_error_message_recorded(self):
        codes = ['GOOD', 'ERR']
        runner, _ = self._run(codes, 'ERR')
        summary = runner.get_last_run_status()
        assert 'ERR' in summary['errors']
        assert '故意失败' in summary['errors']['ERR']

    def test_success_count_plus_failed_count_equals_total(self):
        codes = ['A', 'B', 'C', 'D', 'E']
        fail = 'C'
        runner, _ = self._run(codes, fail)
        summary = runner.get_last_run_status()
        assert len(summary['success']) + len(summary['failed']) == len(codes)


# ════════════════════════════════════════════════════════════════════════════
# 场景 3：手动取消
# ════════════════════════════════════════════════════════════════════════════

class TestScenario3ManualCancel:
    def test_cancelled_stocks_have_cancelled_status(self):
        """取消后，尚未处理的股票状态变为 cancelled"""
        codes = ['S1', 'S2', 'S3', 'S4', 'S5']
        runner = BatchRunner()
        processed = []

        def side_effect(s, syms):
            processed.append(syms[0])
            if len(processed) == 2:
                runner.cancel()
            return _fake_result(syms[0])

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=side_effect):
            runner.run(codes, _factory, START, END, persist_results=False)

        summary = runner.get_last_run_status()
        assert len(summary['cancelled']) > 0, "应有部分股票状态为 cancelled"
        # 已成功的股票不应变成 cancelled
        for code in summary['success']:
            assert summary['statuses'][code] == 'success'

    def test_completed_results_preserved_after_cancel(self):
        """取消后已完成的回测结果应保留"""
        codes = ['R1', 'R2', 'R3', 'R4']
        runner = BatchRunner()
        processed = []

        def side_effect(s, syms):
            processed.append(syms[0])
            if len(processed) == 2:
                runner.cancel()
            return _fake_result(syms[0])

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=side_effect):
            results = runner.run(codes, _factory, START, END, persist_results=False)

        assert 1 <= len(results) < len(codes), \
            f"取消后结果数应在 [1, {len(codes)}) 范围内，实际 {len(results)}"

    def test_no_pending_after_cancel(self):
        """取消完成后，不应再有 pending 状态的股票"""
        codes = ['T1', 'T2', 'T3']
        runner = BatchRunner()

        def side_effect(s, syms):
            runner.cancel()
            return _fake_result(syms[0])

        with patch('src.backtesting.batch_runner.BacktestEngine.run_backtest',
                   side_effect=side_effect):
            runner.run(codes, _factory, START, END, persist_results=False)

        summary = runner.get_last_run_status()
        assert len(summary['pending']) == 0, \
            f"取消后 pending 应为 0，实际: {summary['pending']}"
