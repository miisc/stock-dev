"""
数据获取器
整合数据获取、处理和存储功能

新增：支持基于 `data/market_meta.json` 的增量更新（`fetch_incremental`），并保留旧接口兼容。
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger

from .akshare_source import AKShareSource
from .data_processor import DataProcessor
from .data_storage import DataStorage
from .data_query import DataQuery
from ..common.config import Config


class DataFetcher:
    """数据获取器类
    
    说明：
    - 旧方法 `fetch_and_store_data(symbol, days)` 保持行为不变（全量请求）。
    - 新方法 `fetch_incremental(symbol, start_date=None, end_date=None, force_refresh=False, backfill_days=0)`
      会根据本地 `market_meta.json` 决定需要下载的区间，仅下载缺失部分并合并。
    """

    def __init__(self, config: Optional[Config] = None):
        """初始化数据获取器"""
        self.config = config or Config()

        # 获取配置
        db_path = self.config.get('database.path', 'data/stock_data.db')
        data_source_config = self.config.get('data_source', {})

        # 初始化组件
        self.data_source = AKShareSource(data_source_config)
        self.data_processor = DataProcessor()
        self.data_storage = DataStorage(db_path)
        self.data_query = DataQuery(db_path)

        # meta 文件用于记录每只股票的本地最新日期（用于增量更新）
        self.meta_path = Path(self.config.get('market.meta_path', 'data/market_meta.json'))
        self._meta = self._load_meta()

        # 质量评估配置
        self.quality_report_dir = Path(self.config.get('quality.report_dir', 'data/quality_reports'))
        self.quality_gate_warning_allow = bool(self.config.get('quality.gate_warning_allow', True))
        self.quality_thresholds = self._load_quality_thresholds()

        logger.info("数据获取器初始化完成")

    def _load_quality_thresholds(self) -> Dict[str, Any]:
        defaults = dict(DataProcessor.DEFAULT_QUALITY_THRESHOLDS)
        for k, v in defaults.items():
            defaults[k] = self.config.get(f'quality.{k}', v)
        return defaults

    def _quality_report_path(self, symbol: str) -> Path:
        self.quality_report_dir.mkdir(parents=True, exist_ok=True)
        return self.quality_report_dir / f"{symbol}.json"

    def load_quality_report(self, symbol: str) -> Optional[Dict[str, Any]]:
        path = self._quality_report_path(symbol)
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f'读取质量报告失败 {symbol}: {e}')
            return None

    def assess_stock_quality(self, symbol: str,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             force: bool = False) -> Dict[str, Any]:
        """评估单只股票数据质量并落盘 JSON 报告。"""
        if not force:
            cached = self.load_quality_report(symbol)
            if cached is not None:
                return cached

        df = self.get_stock_data(symbol, start_date, end_date)
        if not df.empty:
            eval_df = df.reset_index()
            eval_df['trade_date'] = eval_df['trade_date'].dt.strftime('%Y%m%d')
            eval_df['ts_code'] = symbol
        else:
            eval_df = pd.DataFrame(columns=['trade_date', 'open', 'high', 'low', 'close', 'volume', 'ts_code'])

        report = DataProcessor.evaluate_quality(eval_df, thresholds=self.quality_thresholds, symbol=symbol)
        report['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        path = self._quality_report_path(symbol)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存质量报告失败 {symbol}: {e}')

        return report

    # ---------------- 基本全量接口（保持兼容） ----------------
    def fetch_and_store_data(self, symbol: str, days: int = 5 * 365) -> bool:
        """获取并存储股票数据（全量区间，兼容旧代码）"""
        try:
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            logger.info(f"开始获取股票 {symbol} 从 {start_date_str} 到 {end_date_str} 的数据")

            # 获取原始数据
            raw_data = self.data_source.get_stock_daily(symbol, start_date_str, end_date_str)

            if raw_data.empty:
                logger.error(f"未获取到股票 {symbol} 的数据")
                return False

            # 处理数据
            processed_data = self.data_processor.process_data(raw_data)

            if processed_data.empty:
                logger.error(f"数据处理后为空")
                return False

            # 存储数据
            saved_count = self.data_storage.save_stock_daily(processed_data)

            if saved_count > 0:
                logger.info(f"成功获取并存储股票 {symbol} 的数据，共 {saved_count} 条记录")
                # 更新 meta
                latest = self.data_query.get_latest_date(symbol)
                if latest:
                    self._set_meta_last_date(symbol, latest)
                return True
            else:
                logger.warning(f"股票 {symbol} 的数据可能已存在，未新增记录")
                return True

        except Exception as e:
            logger.error(f"获取并存储股票 {symbol} 数据失败: {str(e)}")
            return False

    def fetch_and_store_stock_list(self) -> bool:
        """获取并存储股票列表"""
        try:
            logger.info("开始获取股票列表")

            # 获取股票列表
            stock_list = self.data_source.get_stock_list()

            if stock_list.empty:
                logger.error("未获取到股票列表")
                return False

            # 存储股票列表
            saved_count = self.data_storage.save_stock_list(stock_list)

            if saved_count > 0:
                logger.info(f"成功获取并存储股票列表，共 {saved_count} 只股票")
                return True
            else:
                logger.error("存储股票列表失败")
                return False

        except Exception as e:
            logger.error(f"获取并存储股票列表失败: {str(e)}")
            return False

    # ---------------- meta 管理 ----------------
    def _load_meta(self) -> Dict[str, str]:
        try:
            if not self.meta_path.exists():
                return {}
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logger.warning('加载 market_meta 失败，使用空 meta')
            return {}

    def _save_meta(self) -> None:
        try:
            self.meta_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.meta_path, 'w', encoding='utf-8') as f:
                json.dump(self._meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f'保存 market_meta 失败: {e}')

    def _get_meta_last_date(self, symbol: str) -> Optional[str]:
        return self._meta.get(symbol)

    def _set_meta_last_date(self, symbol: str, last_date: str) -> None:
        self._meta[symbol] = last_date
        self._save_meta()

    # ---------------- 增量更新接口 ----------------
    def fetch_incremental(self, symbol: str, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, force_refresh: bool = False,
                          backfill_days: int = 0) -> bool:
        """
        增量获取并存储股票数据：仅下载缺失区间并合并。

        Args:
            symbol: 股票代码（可带/不带后缀）
            start_date: 可选开始日期，格式 `YYYY-MM-DD`；若不指定基于本地 meta 自动决定
            end_date: 可选结束日期，默认今天
            force_refresh: 若 True 则忽略本地最新日期，按 full-range 下载并覆盖（合并）
            backfill_days: 向前回溯天数以修正可能的复权或数据修正
        """
        try:
            # 结束日期默认今天
            if end_date is None:
                end_date_dt = datetime.now()
                end_date = end_date_dt.strftime('%Y-%m-%d')
            else:
                end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')

            # 决定开始日期
            if start_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            else:
                # 首先尝试 meta 记录
                last = self._get_meta_last_date(symbol)
                if last and not force_refresh:
                    latest_dt = datetime.strptime(last, '%Y%m%d')
                    start_dt = latest_dt + timedelta(days=1)
                    # 回溯若干天
                    if backfill_days > 0:
                        start_dt = start_dt - timedelta(days=backfill_days)
                else:
                    # 无历史或强制刷新，则默认过去5年
                    start_dt = datetime.now() - timedelta(days=5 * 365)

            # 如果 start_dt 已经在或晚于 end_date，认为无更新
            if start_dt.date() > end_date_dt.date():
                logger.info(f"{symbol} 无需更新：start> end ({start_dt.date()} >= {end_date_dt.date()})")
                return True

            start_date_str = start_dt.strftime('%Y-%m-%d')
            logger.info(f"增量获取 {symbol} 从 {start_date_str} 到 {end_date} (force={force_refresh}, backfill={backfill_days})")

            raw_data = self.data_source.get_stock_daily(symbol, start_date_str, end_date)
            if raw_data.empty:
                logger.info(f"未获取到 {symbol} 的新数据")
                return True

            processed_data = self.data_processor.process_data(raw_data)
            if processed_data.empty:
                logger.error("处理后数据为空")
                return False

            # 存储（DataStorage.save_stock_daily 应当实现合并已有数据的逻辑）
            saved_count = self.data_storage.save_stock_daily(processed_data)

            # 更新 meta：以数据库中最新日期为准
            latest = self.data_query.get_latest_date(symbol)
            if latest:
                self._set_meta_last_date(symbol, latest)

            logger.info(f"增量获取完成 {symbol}, 新增 {saved_count} 条")
            return True
        except Exception as e:
            logger.error(f"增量获取 {symbol} 失败: {e}")
            return False

    # ---------------- 旧的 update_data 兼容映射 ----------------
    def update_data(self, symbol: str, force_update: bool = False) -> bool:
        """推荐使用 `fetch_incremental`。此处保持兼容并调用增量实现。"""
        return self.fetch_incremental(symbol, force_refresh=force_update)

    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取股票数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYYMMDD 或 YYYY-MM-DD)
            end_date: 结束日期 (YYYYMMDD 或 YYYY-MM-DD)
        """
        # 标准化股票代码
        ts_code = self.data_source.normalize_symbol(symbol)
        return self.data_query.get_stock_daily(ts_code, start_date, end_date)

    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        return self.data_query.get_stock_list()

    def search_stocks(self, keyword: str) -> pd.DataFrame:
        """搜索股票"""
        return self.data_query.search_stocks(keyword)

    def get_stock_summary(self) -> pd.DataFrame:
        """获取所有股票的数据摘要"""
        return self.data_query.get_stock_summary()

    def batch_fetch_data(self, symbols: list, days: int = 5 * 365) -> Dict[str, bool]:
        """批量获取股票数据（兼容旧行为）"""
        results = {}

        for symbol in symbols:
            logger.info(f"正在获取股票 {symbol} 的数据...")
            success = self.fetch_and_store_data(symbol, days)
            results[symbol] = success

            # 添加延迟，避免请求过于频繁
            import time
            time.sleep(1)

        success_count = sum(results.values())
        total_count = len(symbols)

        logger.info(f"批量获取完成，成功 {success_count}/{total_count} 只股票")

        return results
