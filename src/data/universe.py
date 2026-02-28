"""
股票池管理器

功能：
- 使用 akshare 获取各类指数成分股或全市场列表（默认为不包含退市股票）
- 本地缓存到 `data/universe_cache.json`（纯代码，不含交易所后缀）
- 缓存每日过期，默认每次程序启动时可检查并刷新

注意：为兼容不同版本的 akshare，本模块在尝试获取指数成分时会尝试多个可能的函数名/参数。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
from loguru import logger


DEFAULT_CACHE = Path("data") / "universe_cache.json"


class UniverseManager:
    """管理预置股票池及本地缓存"""

    # 预置池到常用指数编码的映射（用于向 akshare 请求）
    POOL_MAP = {
        "hs300": "000300",
        "sh50": "000016",
        "cyb50": "399006",
        "zz500": "000905",
        "all": None,
    }

    def __init__(self, cache_path: Optional[Path] = None):
        self.cache_path = Path(cache_path) if cache_path else DEFAULT_CACHE
        self._cache: Dict = self._load_cache()

    # ----------------- 缓存管理 -----------------
    def _load_cache(self) -> Dict:
        if not self.cache_path.exists():
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception:
            logger.warning("加载 universe 缓存失败，忽略并重新创建")
            return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(self._cache)
        payload.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d"))
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _is_cache_stale(self) -> bool:
        updated = self._cache.get("updated_at")
        if not updated:
            return True
        try:
            updated_date = datetime.strptime(updated, "%Y-%m-%d").date()
            return updated_date < date.today()
        except Exception:
            return True

    # ----------------- 公共接口 -----------------
    def get_pool(self, pool: str, force_refresh: bool = False) -> List[str]:
        """返回指定池的代码列表（纯代码，例如 '000001'），默认每日刷新一次。

        参数:
            pool: 支持 'hs300','sh50','cyb50','zz500','all'
            force_refresh: 强制不使用缓存，直接刷新
        """
        pool = pool.lower()
        if pool not in self.POOL_MAP:
            raise ValueError(f"未知池: {pool}")

        if force_refresh or self._is_cache_stale() or pool not in self._cache:
            logger.info(f"刷新股票池: {pool}")
            try:
                if pool == "all":
                    codes = self._fetch_all_a()
                else:
                    codes = self._fetch_index(self.POOL_MAP[pool])

                # 仅保留纯代码（不含后缀）并去重
                normalized = sorted({self._normalize_code(c) for c in codes if c})

                # 排除显式的退市标记：akshare 的现货接口通常不包含退市，此处以简单规则过滤空/非数字
                normalized = [c for c in normalized if c.isdigit()]

                self._cache[pool] = normalized
                self._cache["updated_at"] = datetime.now().strftime("%Y-%m-%d")
                self._save_cache()
            except Exception as e:
                logger.error(f"获取池 {pool} 失败: {e}")
                # 回退到缓存（如果存在）
                return self._cache.get(pool, [])

        return list(self._cache.get(pool, []))

    def clear_cache(self) -> None:
        self._cache = {}
        try:
            if self.cache_path.exists():
                self.cache_path.unlink()
        except Exception:
            pass

    # ----------------- 内部工具 -----------------
    @staticmethod
    def _call_with_retry(func, kwargs: dict, max_retries: int = 3, base_delay: float = 2.0):
        """带指数退让的重试调用，针对瞬态网络错误"""
        last_err = None
        for attempt in range(max_retries):
            try:
                return func(**kwargs)
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1}/{max_retries} 次失败: {e}，"
                        f"{delay:.1f}s 后重试..."
                    )
                    time.sleep(delay)
        raise last_err

    # ----------------- akshare 获取实现 -----------------
    def _fetch_all_a(self) -> List[str]:
        """使用 akshare 获取当前在市的全部 A 股（spot 列表）"""
        # ak.stock_zh_a_spot_em 通常返回当前上市的股票
        try:
            df = self._call_with_retry(ak.stock_zh_a_spot_em, {})
        except Exception as e:
            logger.error(f"调用 ak.stock_zh_a_spot_em 失败: {e}")
            raise

        # 支持多种列名
        for col in ("代码", "symbol", "代码(上海)"):
            if col in df.columns:
                series = df[col]
                break
        else:
            # 选择第一个看起来像代码的列
            series = df.select_dtypes(include=["object"]).iloc[:, 0]

        codes = [self._normalize_code(str(v)) for v in series.tolist()]
        return codes

    def _fetch_index(self, index_code: str) -> List[str]:
        """尝试通过多种 akshare 接口获取某指数成分股（兼容不同 ak 版本）"""
        candidates = [
            ("index_stock_cons_em", {"symbol": index_code}),
            ("index_stock_cons_em", {"index": index_code}),
            ("index_stock_cons_ths", {"index": index_code}),
            ("index_stock_cons_ths", {"symbol": index_code}),
            ("index_stock_cons", {"symbol": index_code}),
            ("index_stock_cons", {"index": index_code}),
        ]

        last_err = None
        for name, kwargs in candidates:
            if not hasattr(ak, name):
                continue
            func = getattr(ak, name)
            try:
                df = self._call_with_retry(func, kwargs)
                if df is None or (isinstance(df, list) and not df):
                    continue

                # 常见的列名： '股票代码','代码','symbol'
                for col in ("股票代码", "代码", "symbol", "证券代码"):
                    if col in df.columns:
                        series = df[col]
                        break
                else:
                    # fallback: 取第一列
                    series = df.iloc[:, 0]

                codes = [self._normalize_code(str(v)) for v in series.tolist()]
                return codes
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"无法通过 akshare 获取指数 {index_code} 的成分: {last_err}")

    @staticmethod
    def _normalize_code(code: str) -> str:
        """将各种形式的代码标准化为纯数字字符串，例如 '000001.SZ' -> '000001'"""
        if not code:
            return ""
        code = code.strip()
        # 如果含有 '.', 取 '.' 前面的部分
        if "." in code:
            return code.split(".")[0]
        # 如果含有字母前缀（如 sh600000 或 sz000001），去掉字母
        if code[:2].isalpha():
            return code[2:]
        # 否则返回原样（可能已是纯代码）
        return code


# module-level 便利单例
manager = UniverseManager()

if __name__ == "__main__":
    # 简单手动测试
    print("HS300 示例（前10）:")
    try:
        print(manager.get_pool('hs300', force_refresh=True)[:10])
    except Exception as e:
        print("测试失败:", e)
