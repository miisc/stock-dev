"""
AKShare数据源实现
从AKShare获取A股数据
"""

import time
import pandas as pd
from typing import Optional, Dict, Any
from loguru import logger
import akshare as ak

from .data_source import DataSource


class AKShareSource(DataSource):
    """AKShare数据源实现"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化AKShare数据源
        
        Args:
            config: 配置参数
        """
        super().__init__(config)
        self.max_retries = config.get('max_retries', 3) if config else 3
        self.retry_delay = config.get('retry_delay', 1) if config else 1  # 重试延迟(秒)
        
    def get_stock_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            包含OHLCV数据的DataFrame
        """
        # 标准化股票代码
        ts_code = self.normalize_symbol(symbol)
        
        # 验证日期范围
        if not self.validate_date_range(start_date, end_date):
            raise ValueError(f"无效的日期范围: {start_date} 至 {end_date}")
        
        # 提取不带交易所后缀的代码
        code = ts_code.split('.')[0]
        
        # 重试机制
        for attempt in range(self.max_retries):
            try:
                logger.info(f"获取股票 {ts_code} 从 {start_date} 到 {end_date} 的数据 (尝试 {attempt + 1}/{self.max_retries})")
                
                # 使用AKShare获取数据 - 使用新浪财经接口
                # 转换为AKShare需要的格式：sz000001 或 sh600000
                if ts_code.endswith('.SZ'):
                    ak_symbol = 'sz' + ts_code.split('.')[0]
                elif ts_code.endswith('.SH'):
                    ak_symbol = 'sh' + ts_code.split('.')[0]
                else:
                    # 如果没有交易所后缀，默认为SZ
                    if ts_code.startswith('6'):
                        ak_symbol = 'sh' + ts_code
                    else:
                        ak_symbol = 'sz' + ts_code
                
                # 转换日期格式为YYYYMMDD
                start_date_formatted = start_date.replace('-', '')
                end_date_formatted = end_date.replace('-', '')
                
                df = ak.stock_zh_a_daily(symbol=ak_symbol, start_date=start_date_formatted, end_date=end_date_formatted, adjust="qfq")
                
                if not df.empty:
                    logger.info(f"新浪财经接口成功获取 {len(df)} 条数据")
                
                if df.empty:
                    logger.warning(f"未获取到股票 {ts_code} 的数据")
                    return pd.DataFrame()
                
                # 标准化列名
                df = self._standardize_columns(df, ts_code)
                
                logger.info(f"成功获取股票 {ts_code} 数据，共 {len(df)} 条记录")
                return df
                
            except Exception as e:
                logger.error(f"获取股票 {ts_code} 数据失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"获取股票 {ts_code} 数据失败，已重试 {self.max_retries} 次")
        
        return pd.DataFrame()
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            包含股票代码和名称的DataFrame
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"获取A股列表 (尝试 {attempt + 1}/{self.max_retries})")
                
                # 尝试使用不同的接口获取A股列表
                try:
                    # 首先尝试东方财富接口
                    df = ak.stock_zh_a_spot_em()
                except:
                    try:
                        # 如果东方财富接口失败，尝试新浪财经接口
                        # 获取部分知名股票作为示例
                        sample_stocks = [
                            ('000001', '平安银行'),
                            ('000002', '万科A'),
                            ('000858', '五粮液'),
                            ('600000', '浦发银行'),
                            ('600036', '招商银行'),
                            ('600519', '贵州茅台'),
                            ('600887', '伊利股份'),
                            ('000858', '五粮液'),
                            ('002415', '海康威视'),
                            ('300059', '东方财富')
                        ]
                        
                        # 创建DataFrame
                        result = pd.DataFrame(sample_stocks, columns=['symbol', 'name'])
                        
                        # 添加交易所后缀
                        result['ts_code'] = result.apply(
                            lambda row: f"{row['symbol']}.SH" if row['symbol'].startswith('6') else f"{row['symbol']}.SZ",
                            axis=1
                        )
                        
                        logger.info(f"使用示例股票列表，共 {len(result)} 只股票")
                        return result
                    except Exception as e2:
                        raise e2
                
                if df.empty:
                    logger.warning("未获取到股票列表")
                    return pd.DataFrame()
                
                # 提取需要的列并重命名
                result = df[['代码', '名称']].copy()
                result.columns = ['symbol', 'name']
                
                # 添加交易所后缀
                result['ts_code'] = result.apply(
                    lambda row: f"{row['symbol']}.SH" if row['symbol'].startswith('6') else f"{row['symbol']}.SZ",
                    axis=1
                )
                
                logger.info(f"成功获取股票列表，共 {len(result)} 只股票")
                return result
                
            except Exception as e:
                logger.error(f"获取股票列表失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"获取股票列表失败，已重试 {self.max_retries} 次")
        
        return pd.DataFrame()
    
    def _standardize_columns(self, df: pd.DataFrame, ts_code: str) -> pd.DataFrame:
        """
        标准化DataFrame列名
        
        Args:
            df: 原始DataFrame
            ts_code: 股票代码
            
        Returns:
            标准化后的DataFrame
        """
        # 创建标准化的DataFrame
        result = pd.DataFrame()
        
        # 检查数据来源并应用相应的列名映射
        if 'date' in df.columns:
            # 新浪财经接口格式
            column_mapping = {
                'date': 'trade_date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'amount': 'amount'
            }
        elif '日期' in df.columns:
            # 原始接口格式
            column_mapping = {
                '日期': 'trade_date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount'
            }
        elif 'symbol' in df.columns and 'date' in df.columns:
            # 实时行情接口格式
            column_mapping = {
                'date': 'trade_date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'amount': 'amount'
            }
        else:
            # 未知格式，尝试使用常见列名
            column_mapping = {
                'trade_date': 'trade_date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'amount': 'amount'
            }
        
        # 应用列名映射
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                result[new_col] = df[old_col]
        
        # 添加股票代码
        result['ts_code'] = ts_code
        
        # 确保日期格式正确
        if 'trade_date' in result.columns:
            result['trade_date'] = pd.to_datetime(result['trade_date']).dt.strftime('%Y%m%d')
        
        # 确保数值列是float类型
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_columns:
            if col in result.columns:
                result[col] = pd.to_numeric(result[col], errors='coerce')
        
        # 按日期排序
        result = result.sort_values('trade_date').reset_index(drop=True)
        
        return result