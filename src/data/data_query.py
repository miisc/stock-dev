"""
数据查询类
负责从SQLite数据库查询数据
"""

import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
from loguru import logger

from ..common.database import DatabaseManager


class DataQuery:
    """数据查询类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据查询
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_manager = DatabaseManager(db_path)
        logger.info(f"数据查询初始化完成，数据库路径: {db_path}")
    
    def get_stock_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            
        Returns:
            股票日线数据DataFrame
        """
        try:
            query = "SELECT * FROM stock_daily WHERE ts_code = ?"
            params = [ts_code]
            
            if start_date:
                # 转换日期格式为YYYYMMDD
                if isinstance(start_date, datetime):
                    start_date_str = start_date.strftime('%Y%m%d')
                else:
                    start_date_str = start_date.replace('-', '')
                query += " AND trade_date >= ?"
                params.append(start_date_str)
            
            if end_date:
                # 转换日期格式为YYYYMMDD
                if isinstance(end_date, datetime):
                    end_date_str = end_date.strftime('%Y%m%d')
                else:
                    end_date_str = end_date.replace('-', '')
                query += " AND trade_date <= ?"
                params.append(end_date_str)
            
            query += " ORDER BY trade_date"
            
            with self.db_manager.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)
            
            # 转换日期格式从YYYYMMDD到datetime
            if not df.empty and 'trade_date' in df.columns:
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                df.set_index('trade_date', inplace=True)
            
            if not df.empty:
                logger.info(f"查询到股票 {ts_code} 的 {len(df)} 条日线数据")
            else:
                logger.warning(f"未查询到股票 {ts_code} 的日线数据")
            
            return df
            
        except Exception as e:
            logger.error(f"查询股票日线数据失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取股票列表
        
        Returns:
            股票列表DataFrame
        """
        try:
            with self.db_manager.get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM stock_list ORDER BY ts_code", conn)
            
            if not df.empty:
                logger.info(f"查询到 {len(df)} 只股票的列表")
            else:
                logger.warning("未查询到股票列表")
            
            return df
            
        except Exception as e:
            logger.error(f"查询股票列表失败: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_info(self, ts_code: str) -> Dict[str, Any]:
        """
        获取股票基本信息
        
        Args:
            ts_code: 股票代码
            
        Returns:
            股票信息字典
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM stock_list WHERE ts_code = ?", (ts_code,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                else:
                    logger.warning(f"未找到股票 {ts_code} 的基本信息")
                    return {}
                    
        except Exception as e:
            logger.error(f"查询股票信息失败: {str(e)}")
            return {}
    
    def get_latest_date(self, ts_code: str) -> Optional[str]:
        """
        获取股票最新数据日期
        
        Args:
            ts_code: 股票代码
            
        Returns:
            最新日期字符串 (YYYYMMDD)
        """
        try:
            result = self.db_manager.execute_query(
                "SELECT MAX(trade_date) as latest_date FROM stock_daily WHERE ts_code = ?",
                (ts_code,)
            )
            
            if result and result[0]['latest_date']:
                return result[0]['latest_date']
            else:
                logger.warning(f"未找到股票 {ts_code} 的数据")
                return None
                
        except Exception as e:
            logger.error(f"查询最新日期失败: {str(e)}")
            return None
    
    def get_earliest_date(self, ts_code: str) -> Optional[str]:
        """
        获取股票最早数据日期
        
        Args:
            ts_code: 股票代码
            
        Returns:
            最早日期字符串 (YYYYMMDD)
        """
        try:
            result = self.db_manager.execute_query(
                "SELECT MIN(trade_date) as earliest_date FROM stock_daily WHERE ts_code = ?",
                (ts_code,)
            )
            
            if result and result[0]['earliest_date']:
                return result[0]['earliest_date']
            else:
                logger.warning(f"未找到股票 {ts_code} 的数据")
                return None
                
        except Exception as e:
            logger.error(f"查询最早日期失败: {str(e)}")
            return None
    
    def get_data_count(self, ts_code: str = None) -> int:
        """
        获取数据记录数
        
        Args:
            ts_code: 股票代码（可选）
            
        Returns:
            记录数
        """
        try:
            if ts_code:
                result = self.db_manager.execute_query(
                    "SELECT COUNT(*) as count FROM stock_daily WHERE ts_code = ?",
                    (ts_code,)
                )
            else:
                result = self.db_manager.execute_query(
                    "SELECT COUNT(*) as count FROM stock_daily"
                )
            
            return result[0]['count'] if result else 0
            
        except Exception as e:
            logger.error(f"查询数据记录数失败: {str(e)}")
            return 0
    
    def get_stock_summary(self) -> pd.DataFrame:
        """
        获取所有股票的数据摘要
        
        Returns:
            股票数据摘要DataFrame
        """
        try:
            query = """
                SELECT 
                    s.ts_code,
                    l.name,
                    MIN(s.trade_date) as earliest_date,
                    MAX(s.trade_date) as latest_date,
                    COUNT(*) as record_count,
                    MIN(s.low) as lowest_price,
                    MAX(s.high) as highest_price,
                    s.close as latest_price
                FROM stock_daily s
                LEFT JOIN stock_list l ON s.ts_code = l.ts_code
                GROUP BY s.ts_code
                ORDER BY s.ts_code
            """
            
            with self.db_manager.get_connection() as conn:
                df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                logger.info(f"查询到 {len(df)} 只股票的数据摘要")
            else:
                logger.warning("未查询到股票数据摘要")
            
            return df
            
        except Exception as e:
            logger.error(f"查询股票数据摘要失败: {str(e)}")
            return pd.DataFrame()
    
    def search_stocks(self, keyword: str) -> pd.DataFrame:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词（股票代码或名称）
            
        Returns:
            匹配的股票列表DataFrame
        """
        try:
            query = """
                SELECT * FROM stock_list 
                WHERE ts_code LIKE ? OR symbol LIKE ? OR name LIKE ?
                ORDER BY ts_code
            """
            
            keyword_pattern = f"%{keyword}%"
            params = [keyword_pattern, keyword_pattern, keyword_pattern]
            
            with self.db_manager.get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                logger.info(f"搜索到 {len(df)} 只匹配的股票")
            else:
                logger.warning(f"未找到匹配 '{keyword}' 的股票")
            
            return df
            
        except Exception as e:
            logger.error(f"搜索股票失败: {str(e)}")
            return pd.DataFrame()