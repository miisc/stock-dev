"""
股票池管理器
- 提供预置指数成分股获取（尝试使用 AKShare）
- 提供全部A股列表获取（使用 AKShareSource.get_stock_list）
- 本地缓存机制，默认TTL 7天
- 支持自定义代码列表
"""
from typing import Optional, List
from pathlib import Path
import json
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from .akshare_source import AKShareSource


class StockPoolManager:
    """管理股票池与本地缓存"""

    INDEX_CODE_MAP = {
        "hs300": "000300",
        "sh50": "000016",
        "cyb50": "399006",
        "zz500": "000905",
    }

    def __init__(self, data_source: Optional[AKShareSource] = None, cache_dir: Optional[str] = None, ttl_days: int = 7):
        self.data_source = data_source or AKShareSource()
        self.ttl = timedelta(days=ttl_days)
        base = Path(cache_dir) if cache_dir else Path(__file__).parent / "cache"
        base.mkdir(parents=True, exist_ok=True)
        self.cache_dir = base

    def _cache_path(self, name: str) -> Path:
        return self.cache_dir / f"{name}.json"

    def _load_cache(self, name: str) -> Optional[pd.DataFrame]:
        path = self._cache_path(name)
        if not path.exists():
            return None
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > self.ttl:
                logger.info(f"缓存 {name} 已过期")
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"加载缓存失败 {name}: {e}")
            return None

    def _save_cache(self, name: str, df: pd.DataFrame):
        path = self._cache_path(name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(df.to_json(orient="records", force_ascii=False))
        except Exception as e:
            logger.error(f"保存缓存失败 {name}: {e}")

    def get_all_a_shares(self) -> pd.DataFrame:
        """获取全部A股列表，使用缓存"""
        cached = self._load_cache("all_a_shares")
        if cached is not None:
            return cached
        df = self.data_source.get_stock_list()
        if df is None:
            df = pd.DataFrame()
        self._save_cache("all_a_shares", df)
        return df

    def get_index_components(self, index_key: str) -> pd.DataFrame:
        """获取指定预置指数的成分股
        index_key: 支持 'hs300','sh50','cyb50','zz500' 或者直接传入指数代码
        """
        # try cache
        cache_name = f"index_{index_key}"
        cached = self._load_cache(cache_name)
        if cached is not None:
            return cached

        code = self.INDEX_CODE_MAP.get(index_key.lower(), index_key)
        try:
            # 尝试使用 akshare 的接口获取成分股
            import akshare as ak
            try:
                # ak.index_stock_cons 支持传入指数代码（不同版本行为略有差异）
                df = ak.index_stock_cons(index=code)
            except TypeError:
                # 备选参数名
                df = ak.index_stock_cons(index_code=code)

            if df is None or df.empty:
                logger.warning(f"未从 akshare 获取到指数 {index_key}({code}) 的成分股")
                df = pd.DataFrame()
            else:
                # 规范化列名为 ts_code, symbol, name
                if "code" in df.columns and "name" in df.columns:
                    df = df.rename(columns={"code": "symbol", "name": "name"})
                if "symbol" in df.columns and "exchange" in df.columns:
                    # 如果没有 ts_code，尝试添加后缀
                    df["ts_code"] = df.apply(lambda r: f"{r['symbol']}.SH" if str(r.get("symbol", "")).startswith("6") else f"{r['symbol']}.SZ", axis=1)
                elif "ts_code" not in df.columns and "symbol" in df.columns:
                    df["ts_code"] = df.apply(lambda r: f"{r['symbol']}.SH" if str(r['symbol']).startswith("6") else f"{r['symbol']}.SZ", axis=1)
        except Exception as e:
            logger.warning(f"获取指数成分失败: {e}")
            df = pd.DataFrame()

        self._save_cache(cache_name, df)
        return df

    def build_custom_pool(self, symbols: List[str]) -> pd.DataFrame:
        """根据自定义 symbol 列表构建 DataFrame，接受带或不带交易所后缀的代码"""
        rows = []
        for s in symbols:
            ts = s if ("." in s) else (f"{s}.SH" if str(s).startswith("6") else f"{s}.SZ")
            rows.append({"symbol": s, "ts_code": ts})
        return pd.DataFrame(rows)
