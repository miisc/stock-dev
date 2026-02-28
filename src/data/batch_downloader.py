"""
简单的批量下载管理器：
- 并发控制（ThreadPoolExecutor）
- 失败重试
- 进度回调
- 支持增量下载（使用 DataStorage.check_data_exists / get_missing_dates）
"""
from typing import List, Callable, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from loguru import logger

from .akshare_source import AKShareSource
from .data_storage import DataStorage


class BatchDownloader:
    def __init__(self, data_source: Optional[AKShareSource] = None, storage: Optional[DataStorage] = None,
                 concurrency: int = 5, max_retries: int = 3, retry_delay: float = 1.0):
        self.data_source = data_source or AKShareSource()
        self.storage = storage
        self.concurrency = concurrency
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _download_one(self, ts_code: str, start_date: str, end_date: str) -> Dict[str, Any]:
        result = {"ts_code": ts_code, "success": False, "saved": 0, "error": None}
        for attempt in range(1, self.max_retries + 1):
            if self._cancel_event.is_set():
                result["error"] = "cancelled"
                return result
            try:
                df = self.data_source.get_stock_daily(ts_code, start_date, end_date)
                if df is None or df.empty:
                    result["error"] = "no_data"
                    logger.warning(f"{ts_code} 无数据, attempt {attempt}")
                else:
                    if self.storage:
                        saved = self.storage.save_stock_daily(df)
                        result["saved"] = saved
                    result["success"] = True
                    return result
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"下载 {ts_code} 失败 (attempt {attempt}): {e}")
            time.sleep(self.retry_delay)
        return result

    def download(self, ts_codes: List[str], start_date: str, end_date: str,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Any]:
        """批量下载，返回成功数和失败列表
        progress_callback 接收 (done_count, total_count, current_ts)
        """
        total = len(ts_codes)
        done = 0
        successes = 0
        failures = []

        # 如果提供 storage，可以先检查已存在的数据并执行增量下载
        if self.storage:
            filtered = []
            for ts in ts_codes:
                try:
                    exists = self.storage.check_data_exists(ts, start_date.replace('-', ''), end_date.replace('-', ''))
                except Exception:
                    exists = False
                if exists:
                    logger.info(f"数据已存在，跳过 {ts}")
                else:
                    filtered.append(ts)
            ts_codes = filtered
            total = len(ts_codes)

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            futures = {ex.submit(self._download_one, ts, start_date, end_date): ts for ts in ts_codes}
            for fut in as_completed(futures):
                ts = futures[fut]
                if self._cancel_event.is_set():
                    logger.info("下载已取消")
                    break
                try:
                    res = fut.result()
                except Exception as e:
                    res = {"ts_code": ts, "success": False, "error": str(e)}
                done += 1
                if res.get("success"):
                    successes += 1
                else:
                    failures.append({"ts_code": ts, "error": res.get("error")})

                if progress_callback:
                    try:
                        progress_callback(done, total, ts)
                    except Exception:
                        pass

        return {"total": total, "done": done, "successes": successes, "failures": failures}
