"""
UniverseManager 单元测试

验证代码标准化、缓存刷新判断、get_pool() 缓存使用/跳过逻辑。
不进行真实网络请求（mock _fetch_index / _fetch_all_a）。

运行方式: python tests/test_universe.py
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.data.universe import UniverseManager


# ────────────────────────────────────────────────────────────────────────────
# _normalize_code
# ────────────────────────────────────────────────────────────────────────────

def test_normalize_stripes_sz_suffix():
    assert UniverseManager._normalize_code('000001.SZ') == '000001'
    print("✓ _normalize_code: 000001.SZ → 000001")


def test_normalize_strips_sh_suffix():
    assert UniverseManager._normalize_code('600000.SH') == '600000'
    print("✓ _normalize_code: 600000.SH → 600000")


def test_normalize_strips_sz_prefix():
    assert UniverseManager._normalize_code('sz000001') == '000001'
    print("✓ _normalize_code: sz000001 → 000001")


def test_normalize_strips_sh_prefix():
    assert UniverseManager._normalize_code('sh600000') == '600000'
    print("✓ _normalize_code: sh600000 → 600000")


def test_normalize_bare_code_unchanged():
    assert UniverseManager._normalize_code('000001') == '000001'
    print("✓ _normalize_code: 000001 → 000001 (不变)")


def test_normalize_empty_string():
    assert UniverseManager._normalize_code('') == ''
    print("✓ _normalize_code: '' → ''")


def test_normalize_strips_whitespace():
    assert UniverseManager._normalize_code('  000001  ') == '000001'
    print("✓ _normalize_code: '  000001  ' → '000001'")


# ────────────────────────────────────────────────────────────────────────────
# _is_cache_stale
# ────────────────────────────────────────────────────────────────────────────

def _manager_with_cache(updated_at=None, pool_data=None) -> UniverseManager:
    """创建使用临时缓存文件的 UniverseManager。
    先将文件完全关闭再读取，避免 Windows 缓冲未刷盘问题。
    """
    f = tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w',
                                    encoding='utf-8')
    try:
        payload = {}
        if updated_at is not None:
            payload['updated_at'] = updated_at
        if pool_data is not None:
            payload.update(pool_data)
        json.dump(payload, f)
    finally:
        f.close()          # 确保写入并关闭文件后再让 UniverseManager 读取
    return UniverseManager(cache_path=Path(f.name))


def test_cache_stale_no_updated_at():
    """缓存中无 updated_at 字段 → 认为过期"""
    mgr = _manager_with_cache(updated_at=None)
    assert mgr._is_cache_stale() is True
    print("✓ 无 updated_at → cache is stale")


def test_cache_stale_yesterday():
    """updated_at 为昨天 → 过期"""
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    mgr = _manager_with_cache(updated_at=yesterday)
    assert mgr._is_cache_stale() is True
    print(f"✓ yesterday ({yesterday}) → cache is stale")


def test_cache_fresh_today():
    """updated_at 为今天 → 未过期"""
    today_str = date.today().strftime('%Y-%m-%d')
    mgr = _manager_with_cache(updated_at=today_str)
    assert mgr._is_cache_stale() is False
    print(f"✓ today ({today_str}) → cache is fresh")


def test_cache_stale_old_date():
    """updated_at 很久以前 → 过期"""
    mgr = _manager_with_cache(updated_at='2020-01-01')
    assert mgr._is_cache_stale() is True
    print("✓ 2020-01-01 → cache is stale")


# ────────────────────────────────────────────────────────────────────────────
# get_pool
# ────────────────────────────────────────────────────────────────────────────

def _temp_manager() -> UniverseManager:
    """创建指向临时文件的 UniverseManager（无现有缓存）"""
    tmp = Path(tempfile.mktemp(suffix='.json'))
    return UniverseManager(cache_path=tmp)


def test_get_pool_fetches_when_no_cache():
    """无缓存时应调用 _fetch_index 并返回结果"""
    mgr = _temp_manager()
    mock_codes = ['000001', '000002', '000300']
    with patch.object(mgr, '_fetch_index', return_value=mock_codes) as mock_fetch:
        result = mgr.get_pool('hs300')
    mock_fetch.assert_called_once()
    assert set(result) == set(mock_codes), f"期望 {mock_codes}，实际 {result}"
    print(f"✓ 无缓存时调用 _fetch_index: {result[:3]}")


def test_get_pool_uses_cache_when_fresh():
    """缓存新鲜时不调用网络接口"""
    today_str = date.today().strftime('%Y-%m-%d')
    cached_codes = ['000001', '000002']
    mgr = _manager_with_cache(updated_at=today_str,
                               pool_data={'hs300': cached_codes})
    with patch.object(mgr, '_fetch_index') as mock_fetch:
        result = mgr.get_pool('hs300')
    mock_fetch.assert_not_called()
    assert result == cached_codes, f"期望 {cached_codes}，实际 {result}"
    print(f"✓ 缓存新鲜时不调用网络: {result}")


def test_get_pool_force_refresh_bypasses_cache():
    """force_refresh=True 即使缓存新鲜也重新获取"""
    today_str = date.today().strftime('%Y-%m-%d')
    old_codes = ['000001']
    new_codes  = ['600000', '601318']
    mgr = _manager_with_cache(updated_at=today_str, pool_data={'hs300': old_codes})
    with patch.object(mgr, '_fetch_index', return_value=new_codes):
        result = mgr.get_pool('hs300', force_refresh=True)
    # 应返回新获取的数据
    assert set(result) == set(new_codes), f"期望 {new_codes}，实际 {result}"
    print(f"✓ force_refresh=True 绕过缓存: {result}")


def test_get_pool_returns_pure_codes():
    """get_pool 返回的代码应为纯数字（无交易所后缀），且全部为 isdigit()"""
    mgr = _temp_manager()
    raw = ['000001.SZ', '600000.SH', 'sz000002', '000300']
    with patch.object(mgr, '_fetch_index', return_value=raw):
        result = mgr.get_pool('hs300')
    assert all(c.isdigit() for c in result), f"含非数字代码: {result}"
    print(f"✓ 返回纯数字代码: {result}")


def test_get_pool_unknown_pool_raises():
    """传入未知池名称應 raise ValueError"""
    mgr = _temp_manager()
    try:
        mgr.get_pool('unknown_pool')
        assert False, "应抛出 ValueError"
    except ValueError:
        print("✓ 未知池抛出 ValueError")


def test_get_pool_all_calls_fetch_all_a():
    """pool='all' 时调用 _fetch_all_a，而非 _fetch_index"""
    mgr = _temp_manager()
    with patch.object(mgr, '_fetch_all_a', return_value=['000001', '000002']) as mock_all, \
         patch.object(mgr, '_fetch_index') as mock_idx:
        result = mgr.get_pool('all')
    mock_all.assert_called_once()
    mock_idx.assert_not_called()
    print(f"✓ pool='all' 调用 _fetch_all_a: {result}")


def test_get_pool_network_failure_falls_back_to_cache():
    """网络获取失败时回退到已有缓存数据"""
    today_str = date.today().strftime('%Y-%m-%d')
    # 注意：要让 get_pool 尝试刷新（force_refresh=True），但 _fetch_index 失败
    cached_codes = ['000001', '000002']
    mgr = _manager_with_cache(updated_at=today_str, pool_data={'hs300': cached_codes})
    with patch.object(mgr, '_fetch_index', side_effect=RuntimeError("网络断开")):
        result = mgr.get_pool('hs300', force_refresh=True)
    # 应回退到缓存
    assert result == cached_codes, f"期望回退到缓存 {cached_codes}，实际 {result}"
    print(f"✓ 网络失败回退到缓存: {result}")


# ────────────────────────────────────────────────────────────────────────────
# clear_cache
# ────────────────────────────────────────────────────────────────────────────

def test_clear_cache_removes_file():
    """clear_cache() 应删除缓存文件"""
    today_str = date.today().strftime('%Y-%m-%d')
    mgr = _manager_with_cache(updated_at=today_str, pool_data={'hs300': ['000001']})
    assert mgr.cache_path.exists()
    mgr.clear_cache()
    assert not mgr.cache_path.exists()
    print("✓ clear_cache 删除缓存文件")


def test_clear_cache_empties_memory():
    """clear_cache() 应清空内存缓存"""
    today_str = date.today().strftime('%Y-%m-%d')
    mgr = _manager_with_cache(updated_at=today_str, pool_data={'hs300': ['000001']})
    assert 'hs300' in mgr._cache
    mgr.clear_cache()
    assert mgr._cache == {}
    print("✓ clear_cache 清空内存缓存")


if __name__ == '__main__':
    tests = [
        test_normalize_stripes_sz_suffix,
        test_normalize_strips_sh_suffix,
        test_normalize_strips_sz_prefix,
        test_normalize_strips_sh_prefix,
        test_normalize_bare_code_unchanged,
        test_normalize_empty_string,
        test_normalize_strips_whitespace,
        test_cache_stale_no_updated_at,
        test_cache_stale_yesterday,
        test_cache_fresh_today,
        test_cache_stale_old_date,
        test_get_pool_fetches_when_no_cache,
        test_get_pool_uses_cache_when_fresh,
        test_get_pool_force_refresh_bypasses_cache,
        test_get_pool_returns_pure_codes,
        test_get_pool_unknown_pool_raises,
        test_get_pool_all_calls_fetch_all_a,
        test_get_pool_network_failure_falls_back_to_cache,
        test_clear_cache_removes_file,
        test_clear_cache_empties_memory,
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
