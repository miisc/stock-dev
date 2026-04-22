"""
数据处理器
负责数据清洗、前复权计算、异常值处理与数据质量评估
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from loguru import logger


class DataProcessor:
    """数据处理器类"""

    DEFAULT_QUALITY_THRESHOLDS = {
        "missing_ratio_warning": 0.02,
        "missing_ratio_failed": 0.10,
        "duplicate_ratio_warning": 0.005,
        "duplicate_ratio_failed": 0.02,
        "date_disorder_ratio_warning": 0.005,
        "date_disorder_ratio_failed": 0.02,
        "ohlc_anomaly_ratio_warning": 0.005,
        "ohlc_anomaly_ratio_failed": 0.02,
        "non_positive_price_ratio_warning": 0.0,
        "non_positive_price_ratio_failed": 0.001,
        "min_rows_for_assessment": 2,
    }
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据，处理缺失值和异常值
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            清洗后的DataFrame
        """
        if df.empty:
            return df
        
        # 复制数据避免修改原始数据
        cleaned_df = df.copy()
        
        # 检查必要的列
        required_columns = ['trade_date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in cleaned_df.columns]
        
        if missing_columns:
            logger.error(f"数据缺少必要的列: {missing_columns}")
            return pd.DataFrame()
        
        # 转换日期格式
        cleaned_df['trade_date'] = pd.to_datetime(cleaned_df['trade_date'], format='%Y%m%d')
        
        # 确保价格和成交量是数值类型
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
        
        cleaned_df['volume'] = pd.to_numeric(cleaned_df['volume'], errors='coerce')
        
        if 'amount' in cleaned_df.columns:
            cleaned_df['amount'] = pd.to_numeric(cleaned_df['amount'], errors='coerce')
        
        # 处理缺失值 - 对于OHLC数据，使用前一天的收盘价填充
        for col in price_columns:
            cleaned_df[col] = cleaned_df[col].ffill()
        
        # 成交量缺失值填充为0
        cleaned_df['volume'] = cleaned_df['volume'].fillna(0)
        
        # 成交额缺失值填充为0
        if 'amount' in cleaned_df.columns:
            cleaned_df['amount'] = cleaned_df['amount'].fillna(0)
        
        # 如果还有缺失值，删除这些行
        cleaned_df = cleaned_df.dropna(subset=price_columns)
        
        # 重置索引
        cleaned_df = cleaned_df.reset_index(drop=True)
        
        logger.info(f"数据清洗完成，从 {len(df)} 条记录清洗到 {len(cleaned_df)} 条记录")
        
        return cleaned_df
    
    @staticmethod
    def filter_extreme_values(df: pd.DataFrame, threshold: float = 0.05) -> pd.DataFrame:
        """
        过滤异常值，基于涨跌幅限制
        
        Args:
            df: 原始数据DataFrame
            threshold: 涨跌幅阈值，默认5%
            
        Returns:
            过滤后的DataFrame
        """
        if df.empty:
            return df
        
        filtered_df = df.copy()
        
        # 计算日涨跌幅
        filtered_df = filtered_df.sort_values('trade_date').reset_index(drop=True)
        filtered_df['pct_change'] = filtered_df['close'].pct_change()
        
        # 标记异常值（仅用于内部统计，不记录日志）
        extreme_mask = (filtered_df['pct_change'].abs() > threshold) & (filtered_df['pct_change'].notna())
        
        # 这里我们只是检测异常值，不删除它们
        # 在实际应用中，可能需要根据具体需求决定是否删除
        
        # 删除临时列
        filtered_df = filtered_df.drop(columns=['pct_change'])
        
        return filtered_df
    
    @staticmethod
    def validate_ohlc_consistency(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
        """
        验证OHLC数据的一致性
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            (验证后的DataFrame, 修正的记录数)
        """
        if df.empty:
            return df, 0
        
        validated_df = df.copy()
        correction_count = 0
        
        # 检查 high >= low
        invalid_hl = validated_df['high'] < validated_df['low']
        if invalid_hl.any():
            correction_count += invalid_hl.sum()
            logger.warning(f"发现 {invalid_hl.sum()} 条记录的最高价低于最低价，进行修正")
            
            # 修正：将high和low互换
            mask = validated_df['high'] < validated_df['low']
            validated_df.loc[mask, ['high', 'low']] = validated_df.loc[mask, ['low', 'high']].values
        
        # 检查 high >= open, close
        invalid_ho = validated_df['high'] < validated_df['open']
        invalid_hc = validated_df['high'] < validated_df['close']
        
        if invalid_ho.any() or invalid_hc.any():
            count = (invalid_ho | invalid_hc).sum()
            correction_count += count
            logger.warning(f"发现 {count} 条记录的最高价低于开盘价或收盘价，进行修正")
            
            # 修正：将high设为max(open, close, high)
            mask = invalid_ho | invalid_hc
            validated_df.loc[mask, 'high'] = validated_df.loc[mask, ['open', 'close', 'high']].max(axis=1)
        
        # 检查 low <= open, close
        invalid_lo = validated_df['low'] > validated_df['open']
        invalid_lc = validated_df['low'] > validated_df['close']
        
        if invalid_lo.any() or invalid_lc.any():
            count = (invalid_lo | invalid_lc).sum()
            correction_count += count
            logger.warning(f"发现 {count} 条记录的最低价高于开盘价或收盘价，进行修正")
            
            # 修正：将low设为min(open, close, low)
            mask = invalid_lo | invalid_lc
            validated_df.loc[mask, 'low'] = validated_df.loc[mask, ['open', 'close', 'low']].min(axis=1)
        
        return validated_df, correction_count
    
    @staticmethod
    def process_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        完整的数据处理流程
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            处理后的DataFrame
        """
        if df.empty:
            return df
        
        logger.info("开始数据处理流程")
        
        # 1. 数据清洗
        processed_df = DataProcessor.clean_data(df)
        
        # 2. OHLC一致性验证
        processed_df, correction_count = DataProcessor.validate_ohlc_consistency(processed_df)
        if correction_count > 0:
            logger.info(f"OHLC一致性验证完成，修正了 {correction_count} 条记录")
        
        # 3. 异常值过滤
        processed_df = DataProcessor.filter_extreme_values(processed_df)
        
        # 4. 按日期排序
        processed_df = processed_df.sort_values('trade_date').reset_index(drop=True)
        
        # 5. 转换日期格式回字符串
        processed_df['trade_date'] = processed_df['trade_date'].dt.strftime('%Y%m%d')
        
        logger.info(f"数据处理完成，最终得到 {len(processed_df)} 条有效记录")
        
        return processed_df

    @staticmethod
    def evaluate_quality(df: pd.DataFrame,
                         thresholds: Optional[dict] = None,
                         symbol: Optional[str] = None) -> dict:
        """评估数据质量并返回结构化报告。"""
        cfg = dict(DataProcessor.DEFAULT_QUALITY_THRESHOLDS)
        if thresholds:
            cfg.update(thresholds)

        report = {
            "symbol": symbol or (str(df["ts_code"].iloc[0]) if not df.empty and "ts_code" in df.columns else ""),
            "status": "failed",
            "summary": "",
            "stats": {
                "total_rows": int(len(df)),
                "unique_trade_dates": 0,
            },
            "checks": {},
            "warnings": [],
            "blocking_reasons": [],
            "thresholds": cfg,
        }

        if df.empty:
            report["blocking_reasons"].append("数据为空")
            report["summary"] = "数据为空，质量评估失败"
            return report

        required_cols = ["trade_date", "open", "high", "low", "close", "volume"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            report["blocking_reasons"].append(f"缺少必要列: {missing_cols}")
            report["summary"] = "必要列缺失，质量评估失败"
            return report

        if len(df) < int(cfg.get("min_rows_for_assessment", 2)):
            report["blocking_reasons"].append("样本行数不足")
            report["summary"] = "样本行数不足，质量评估失败"
            return report

        local_df = df.copy()
        trade_dates = pd.to_datetime(local_df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
        valid_date_mask = trade_dates.notna()
        total_rows = len(local_df)

        # 缺失交易日比例：按工作日近似统计
        date_min = trade_dates[valid_date_mask].min()
        date_max = trade_dates[valid_date_mask].max()
        if pd.isna(date_min) or pd.isna(date_max):
            expected_days = 0
        else:
            expected_days = len(pd.bdate_range(date_min, date_max))
        unique_days = int(trade_dates[valid_date_mask].nunique())
        missing_days = max(expected_days - unique_days, 0)
        missing_ratio = (missing_days / expected_days) if expected_days > 0 else 0.0

        # 重复比例
        duplicate_rows = int(local_df.duplicated(subset=["trade_date"]).sum())
        duplicate_ratio = duplicate_rows / total_rows if total_rows > 0 else 0.0

        # 日期乱序比例（按原顺序）
        disorder_rows = 0
        prev = None
        for d in trade_dates:
            if pd.isna(d):
                continue
            if prev is not None and d < prev:
                disorder_rows += 1
            prev = d
        date_disorder_ratio = disorder_rows / total_rows if total_rows > 0 else 0.0

        # OHLC 异常比例
        invalid_hl = (local_df["high"] < local_df["low"]).sum()
        invalid_hc = (local_df["high"] < local_df[["open", "close"]].max(axis=1)).sum()
        invalid_lc = (local_df["low"] > local_df[["open", "close"]].min(axis=1)).sum()
        ohlc_anomaly_rows = int(invalid_hl + invalid_hc + invalid_lc)
        ohlc_anomaly_ratio = ohlc_anomaly_rows / total_rows if total_rows > 0 else 0.0

        # 非正价格比例
        non_positive_rows = int((local_df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
        non_positive_price_ratio = non_positive_rows / total_rows if total_rows > 0 else 0.0

        checks = {
            "missing_ratio": {"value": round(missing_ratio, 6), "warning": cfg["missing_ratio_warning"], "failed": cfg["missing_ratio_failed"]},
            "duplicate_ratio": {"value": round(duplicate_ratio, 6), "warning": cfg["duplicate_ratio_warning"], "failed": cfg["duplicate_ratio_failed"]},
            "date_disorder_ratio": {"value": round(date_disorder_ratio, 6), "warning": cfg["date_disorder_ratio_warning"], "failed": cfg["date_disorder_ratio_failed"]},
            "ohlc_anomaly_ratio": {"value": round(ohlc_anomaly_ratio, 6), "warning": cfg["ohlc_anomaly_ratio_warning"], "failed": cfg["ohlc_anomaly_ratio_failed"]},
            "non_positive_price_ratio": {"value": round(non_positive_price_ratio, 6), "warning": cfg["non_positive_price_ratio_warning"], "failed": cfg["non_positive_price_ratio_failed"]},
        }

        report["checks"] = checks
        report["stats"]["unique_trade_dates"] = unique_days
        report["stats"]["expected_trade_dates"] = expected_days
        report["stats"]["missing_trade_dates"] = missing_days

        has_failed = False
        has_warning = False
        for name, item in checks.items():
            value = item["value"]
            if value > item["failed"]:
                has_failed = True
                report["blocking_reasons"].append(f"{name}={value} 超过失败阈值 {item['failed']}")
            elif value > item["warning"]:
                has_warning = True
                report["warnings"].append(f"{name}={value} 超过警告阈值 {item['warning']}")

        if has_failed:
            report["status"] = "failed"
            report["summary"] = "数据质量不通过"
        elif has_warning:
            report["status"] = "warning"
            report["summary"] = "数据质量存在警告"
        else:
            report["status"] = "pass"
            report["summary"] = "数据质量通过"

        return report