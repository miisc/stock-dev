"""
批量下载管理器：
- 并发控制（默认 <=3，避免 akshare 限流）
- 请求间隔 >= 500ms 限速
- Queue + 单一写入线程，避免并发 SQLite 写冲突
- 失败重试（默认最多 3 次）
- 进度回调
- 支持取消和增量下载跳过
"""
from typing import List, Callable, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue
import time
from loguru import logger

from .akshare_source import AKShareSource
from .data_storage import DataStorage

# 下载线程之间的全局限速锁（保证所有线程合计间隔 >= 500ms）
_rate_lock = threading.Lock()
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL = 0.5  # 500ms


def _rate_limited_sleep():
    """确保距上次请求至少 500ms"""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _MIN_REQUEST_INTERVAL:
            time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.monotonic()


class BatchDownloader:
    def __init__(
        self,
        data_source: Optional[AKShareSource] = None,
        storage: Optional[DataStorage] = None,
        concurrency: int = 3,       # 默认 <=3，避免 IP 限流
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.data_source = data_source or AKShareSource()
        self.storage = storage
        self.concurrency = concurrency
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    # ------------------------------------------------------------------
    # 下载线程：只负责网络请求，通过 write_queue 传递数据给写入线程
    # ------------------------------------------------------------------
    def _download_one(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        write_queue: Optional[queue.Queue] = None,
    ) -> Dict[str, Any]:
        result = {"ts_code": ts_code, "success": False, "saved": 0, "error": None}
        for attempt in range(1, self.max_retries + 1):
            if self._cancel_event.is_set():
                result["error"] = "cancelled"
                return result
            try:
                _rate_limited_sleep()  # 每次请求前限速
                df = self.data_source.get_stock_daily(ts_code, start_date, end_date)
                if df is None or df.empty:
                    result["error"] = "no_data"
                    logger.warning(f"{ts_code} 无数据, attempt {attempt}")
                else:
                    if write_queue is not None:
                        # 通过队列交给专用写入线程，避免并发 SQLite 写冲突
                        write_queue.put((ts_code, df))
                        result["saved"] = len(df)
                    elif self.storage:
                        # 无写入队列时回退到直接写入（单线程场景）
                        saved = self.storage.save_stock_daily(df)
                        result["saved"] = saved
                    result["success"] = True
                    return result
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"下载 {ts_code} 失败 (attempt {attempt}): {e}")
            time.sleep(self.retry_delay)
        return result

    # ------------------------------------------------------------------
    # 写入线程：串行消费队列，独占 SQLite 写入
    # ------------------------------------------------------------------
    def _writer_worker(self, write_queue: queue.Queue) -> None:
        """从队列读取 (ts_code, df) 并串行写入 SQLite"""
        while True:
            item = write_queue.get()
            if item is None:  # 毒丸信号，退出
                write_queue.task_done()
                break
            ts_code, df = item
            try:
                if self.storage:
                    self.storage.save_stock_daily(df)
            except Exception as e:
                logger.error(f"写入 {ts_code} 失败: {e}")
            write_queue.task_done()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    def download(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """批量下载，返回统计信息字典。

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期
            progress_callback: (done_count, total_count, current_ts_code)

        Returns:
            {"total": int, "done": int, "successes": int, "failures": list}
        """
        # 跳过本地已有数据
        if self.storage:
            filtered = []
            start_clean = start_date.replace("-", "")
            end_clean = end_date.replace("-", "")
            for ts in ts_codes:
                try:
                    exists = self.storage.check_data_exists(ts, start_clean, end_clean)
                except Exception:
                    exists = False
                if exists:
                    logger.info(f"数据已存在，跳过 {ts}")
                else:
                    filtered.append(ts)
            ts_codes = filtered

        total = len(ts_codes)
        done = 0
        successes = 0
        failures: List[Dict] = []

        # 启动专用写入线程（只在有 storage 时需要）
        write_queue: Optional[queue.Queue] = None
        writer_thread: Optional[threading.Thread] = None
        if self.storage:
            write_queue = queue.Queue()
            writer_thread = threading.Thread(
                target=self._writer_worker, args=(write_queue,), daemon=True, name="db-writer"
            )
            writer_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
                futures = {
                    ex.submit(self._download_one, ts, start_date, end_date, write_queue): ts
                    for ts in ts_codes
                }
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
        finally:
            # 发送毒丸，等待写入线程完成所有待写数据
            if write_queue is not None:
                write_queue.put(None)
                write_queue.join()
            if writer_thread is not None:
                writer_thread.join(timeout=30)

        return {"total": total, "done": done, "successes": successes, "failures": failures}
