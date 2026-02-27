"""
数据存储类
负责将处理后的数据存储到SQLite数据库
"""

import pandas as pd
from typing import Optional, List
from pathlib import Path
from loguru import logger

from ..common.database import DatabaseManager


class DataStorage:
    """数据存储类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据存储
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_manager = DatabaseManager(db_path)
        logger.info(f"数据存储初始化完成，数据库路径: {db_path}")
    
    def save_stock_daily(self, df: pd.DataFrame) -> int:
        """
        保存股票日线数据
        
        Args:
            df: 股票日线数据DataFrame
            
        Returns:
            保存的记录数
        """
        if df.empty:
            logger.warning("数据为空，跳过保存")
            return 0
        
        # 检查必要的列
        required_columns = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"数据缺少必要的列: {missing_columns}")
            return 0
        
        try:
            # 获取保存前的记录数
            ts_code = df['ts_code'].iloc[0]
            start_date = df['trade_date'].min()
            end_date = df['trade_date'].max()
            
            existing_count = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ?",
                (ts_code, start_date, end_date)
            )[0]['count']
            
            # 使用REPLACE策略，如果记录已存在则替换
            with self.db_manager.get_connection() as conn:
                # 先删除已存在的记录
                conn.execute("DELETE FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ?",
                           (ts_code, start_date, end_date))
                
                # 然后插入新记录
                df.to_sql('stock_daily', conn, if_exists='append', index=False)
            
            # 获取保存后的记录数
            total_count = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ?",
                (ts_code, start_date, end_date)
            )[0]['count']
            
            saved_count = total_count - existing_count
            logger.info(f"成功保存股票 {ts_code} 从 {start_date} 到 {end_date} 的数据，新增 {saved_count} 条记录")
            
            return saved_count
            
        except Exception as e:
            logger.error(f"保存股票日线数据失败: {str(e)}")
            return 0
    
    def save_stock_list(self, df: pd.DataFrame) -> int:
        """
        保存股票列表
        
        Args:
            df: 股票列表DataFrame
            
        Returns:
            保存的记录数
        """
        if df.empty:
            logger.warning("股票列表为空，跳过保存")
            return 0
        
        try:
            # 创建股票列表表（如果不存在）
            with self.db_manager.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS stock_list (
                        ts_code TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        name TEXT NOT NULL,
                        update_time TEXT NOT NULL
                    )
                """)
                
                # 添加更新时间
                df['update_time'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 使用REPLACE INTO语句逐条插入
                for _, row in df.iterrows():
                    conn.execute(
                        "REPLACE INTO stock_list (ts_code, symbol, name, update_time) VALUES (?, ?, ?, ?)",
                        (row['ts_code'], row['symbol'], row['name'], row['update_time'])
                    )
                
                conn.commit()
            
            logger.info(f"成功保存股票列表，共 {len(df)} 条记录")
            return len(df)
            
        except Exception as e:
            logger.error(f"保存股票列表失败: {str(e)}")
            return 0
    
    def check_data_exists(self, ts_code: str, start_date: str, end_date: str) -> bool:
        """
        检查指定日期范围的数据是否已存在
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            数据是否存在
        """
        try:
            result = self.db_manager.execute_query(
                "SELECT COUNT(*) as count FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ?",
                (ts_code, start_date, end_date)
            )
            
            count = result[0]['count'] if result else 0
            expected_days = len(pd.date_range(start=start_date, end=end_date, freq='D'))
            
            # 考虑到非交易日，如果存在超过一半的日期，认为数据存在
            return count > expected_days * 0.4
            
        except Exception as e:
            logger.error(f"检查数据存在性失败: {str(e)}")
            return False
    
    def get_missing_dates(self, ts_code: str, start_date: str, end_date: str) -> List[str]:
        """
        获取缺失的日期列表
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            缺失的日期列表
        """
        try:
            # 获取已有的日期
            result = self.db_manager.execute_query(
                "SELECT trade_date FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
                (ts_code, start_date, end_date)
            )
            
            existing_dates = {row['trade_date'] for row in result}
            
            # 生成所有日期
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            all_dates_str = [date.strftime('%Y%m%d') for date in all_dates]
            
            # 找出缺失的日期
            missing_dates = [date for date in all_dates_str if date not in existing_dates]
            
            return missing_dates
            
        except Exception as e:
            logger.error(f"获取缺失日期失败: {str(e)}")
            return []
    
    def delete_data(self, ts_code: str, start_date: str = None, end_date: str = None) -> int:
        """
        删除指定股票的数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            
        Returns:
            删除的记录数
        """
        try:
            if start_date and end_date:
                # 删除指定日期范围的数据
                affected_rows = self.db_manager.execute_update(
                    "DELETE FROM stock_daily WHERE ts_code = ? AND trade_date BETWEEN ? AND ?",
                    (ts_code, start_date, end_date)
                )
                logger.info(f"删除股票 {ts_code} 从 {start_date} 到 {end_date} 的数据，共 {affected_rows} 条记录")
            else:
                # 删除所有数据
                affected_rows = self.db_manager.execute_update(
                    "DELETE FROM stock_daily WHERE ts_code = ?",
                    (ts_code,)
                )
                logger.info(f"删除股票 {ts_code} 的所有数据，共 {affected_rows} 条记录")
            
            return affected_rows
            
        except Exception as e:
            logger.error(f"删除数据失败: {str(e)}")
            return 0