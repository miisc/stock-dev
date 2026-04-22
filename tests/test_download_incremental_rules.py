"""
T2: 下载与增量更新规则 验证测试

目标：验证「同区间重复执行不重复下载」的判定依据，及增量边界逻辑。

完成标准：
  1. 同区间同股票重复 download() — 第二次全部跳过（total=0）。
  2. 部分存在时只下载缺失股票。
  3. 失败后重试策略覆盖（max_retries）。
  4. 取消后状态可见，不影响已成功股票的统计。

运行方式: pytest tests/test_download_incremental_rules.py -v
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from src.data.batch_downloader import BatchDownloader


# ─── 辅助 ─────────────────────────────────────────────────────────────────────

def _make_df(rows=5) -> pd.DataFrame:
    return pd.DataFrame({
        'ts_code':    ['000001.SZ'] * rows,
        'trade_date': [f'20230{i+1:02d}01' for i in range(rows)],
        'open':  [10.0] * rows, 'high': [11.0] * rows,
        'low':   [9.0]  * rows, 'close': [10.5] * rows,
        'vol':   [1_000_000] * rows,
    })


def _components(exists: bool = False, return_df: bool = True):
    ds = MagicMock()
    ds.get_stock_daily.return_value = _make_df() if return_df else pd.DataFrame()
    st = MagicMock()
    st.check_data_exists.return_value = exists
    st.save_stock_daily.return_value = 5
    return ds, st


# ─── 规则 1：同区间重复执行不重复下载 ─────────────────────────────────────────

def test_repeat_download_same_interval_skipped():
    """规则 1 — 第一次下载成功后，同区间第二次调用 total=0（全部跳过）"""
    ds, st = _components(exists=True)   # 模拟"已存在"
    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1)

    result = dl.download(['000001', '000002'], '20230101', '20231231')

    assert result['total'] == 0, \
        f"全部应跳过，total 应为 0，实际 {result['total']}"
    assert result['successes'] == 0
    ds.get_stock_daily.assert_not_called()
    print(f"✓ 规则1 — 重复下载全部跳过: total={result['total']}")


def test_first_download_succeeds():
    """规则 1 — 首次下载（数据不存在）全部成功，successes == total"""
    ds, st = _components(exists=False)
    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1)

    result = dl.download(['000001', '000002'], '20230101', '20231231')

    assert result['total'] == 2
    assert result['successes'] == 2
    assert len(result['failures']) == 0
    print(f"✓ 规则1 — 首次下载全部成功: {result}")


# ─── 规则 2：增量边界 — 部分存在只下载缺失 ────────────────────────────────────

def test_incremental_partial_exists():
    """规则 2 — 000001 已存在，000002/000003 缺失，只下载 2 只"""
    codes = ['000001', '000002', '000003']

    def _exists(ts, start, end):
        return ts == '000001'  # 仅 000001 已存在

    ds, st = _components()
    st.check_data_exists.side_effect = _exists

    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1)
    result = dl.download(codes, '20230101', '20231231')

    assert result['total'] == 2, f"应只下载 2 只，实际 {result['total']}"
    assert result['successes'] == 2
    print(f"✓ 规则2 — 增量部分跳过: total={result['total']}, successes={result['successes']}")


# ─── 规则 3：失败重试策略 ──────────────────────────────────────────────────────

def test_retry_success_on_second_attempt():
    """规则 3 — 第一次请求失败，第二次成功（max_retries=2）"""
    attempts = {'000001': 0}

    def flaky_fetch(ts, start, end):
        attempts[ts] = attempts.get(ts, 0) + 1
        if attempts[ts] == 1:
            raise RuntimeError("临时网络错误")
        return _make_df()

    ds, st = _components()
    ds.get_stock_daily.side_effect = flaky_fetch

    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1,
                         max_retries=2, retry_delay=0)
    result = dl.download(['000001'], '20230101', '20231231')

    assert result['successes'] == 1, f"重试成功期望 successes=1, 实际 {result}"
    print(f"✓ 规则3 — 重试后成功: attempts={attempts}, result={result}")


def test_retry_exhausted_marks_failure():
    """规则 3 — 超过 max_retries 次数后，标记为 failure"""
    ds, st = _components()
    ds.get_stock_daily.side_effect = RuntimeError("持续网络错误")

    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1,
                         max_retries=2, retry_delay=0)
    result = dl.download(['BAD'], '20230101', '20231231')

    assert result['successes'] == 0
    assert len(result['failures']) == 1
    assert result['failures'][0]['ts_code'] == 'BAD'
    print(f"✓ 规则3 — 重试耗尽标记失败: {result['failures']}")


# ─── 规则 4：取消后统计可见 ────────────────────────────────────────────────────

def test_cancel_preserves_completed_stats():
    """规则 4 — 取消后，已成功完成的股票计入 successes；结果结构完整"""
    codes = [f'{i:06d}' for i in range(8)]
    ds, st = _components()

    dl = BatchDownloader(data_source=ds, storage=st, concurrency=1)

    def on_progress(done, total, ts):
        if done >= 3:
            dl.cancel()

    result = dl.download(codes, '20230101', '20231231',
                         progress_callback=on_progress)

    # 取消后不应下载完全部
    assert result['successes'] < len(codes), \
        f"取消后 successes 应小于 {len(codes)}, 实际 {result['successes']}"
    # 返回值结构完整
    for key in ('total', 'done', 'successes', 'failures'):
        assert key in result, f"返回值缺少 {key}"
    print(f"✓ 规则4 — 取消后统计: {result}")
