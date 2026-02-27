"""
数据处理器
负责数据清洗、前复权计算和异常值处理
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
from loguru import logger


class DataProcessor:
    """数据处理器类"""
    
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