"""
数据库管理模块
"""

import sqlite3
import json
import pandas as pd
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager


class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_db()
    
    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            # 创建股票日线数据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_daily (
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    amount REAL,
                    PRIMARY KEY (ts_code, trade_date)
                )
            """)
            
            # 创建交易记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    direction TEXT NOT NULL,  -- BUY/SELL
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    trade_time TEXT NOT NULL,
                    strategy_id TEXT,
                    commission REAL DEFAULT 0,
                    notes TEXT
                )
            """)
            
            # 创建持仓表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    ts_code TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    market_value REAL,
                    last_update TEXT NOT NULL
                )
            """)
            
            # 创建账户信息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_assets REAL NOT NULL,
                    available_cash REAL NOT NULL,
                    position_value REAL NOT NULL,
                    total_profit REAL DEFAULT 0,
                    update_time TEXT NOT NULL
                )
            """)
            
            # 创建策略表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    parameters TEXT,  -- JSON格式的参数
                    is_active INTEGER DEFAULT 1,
                    created_time TEXT NOT NULL,
                    updated_time TEXT NOT NULL
                )
            """)
            
            # 初始化账户信息
            conn.execute("""
                INSERT OR IGNORE INTO account (id, total_assets, available_cash, position_value, update_time)
                VALUES (1, 100000, 100000, 0, datetime('now'))
            """)

            # Add composite index for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_daily_code_date 
                ON stock_daily (ts_code, trade_date)
            """)

            # Backtest results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    initial_cash REAL NOT NULL,
                    final_value REAL,
                    total_return REAL,
                    annual_return REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    total_trades INTEGER,
                    win_rate REAL,
                    config_json TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        执行查询语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        执行更新语句
        
        Args:
            query: SQL更新语句
            params: 更新参数
            
        Returns:
            受影响的行数
        """
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def insert_dataframe(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append') -> None:
        """
        将DataFrame插入数据库表
        
        Args:
            df: 要插入的DataFrame
            table_name: 目标表名
            if_exists: 如果表已存在的处理方式: 'fail', 'replace', 'append'
        """
        with self.get_connection() as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
    
    def save_backtest_result(
        self,
        strategy_name: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_cash: float,
        final_value: float,
        metrics: Dict[str, Any],
        config_json: Optional[Dict[str, Any]] = None,
    ) -> int:
        """将单只股票的回测结果写入 backtest_results 表

        Args:
            strategy_name: 策略名称
            symbol: 股票代码
            start_date: 回测开始日期 (YYYYMMDD)
            end_date: 回测结束日期 (YYYYMMDD)
            initial_cash: 初始资金
            final_value: 最终资产价值
            metrics: PerformanceMetrics.to_dict() 的结果
            config_json: 可选的配置 JSON 字典

        Returns:
            新插入行的 rowid
        """
        import json

        config_str = json.dumps(config_json, ensure_ascii=False) if config_json else None

        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO backtest_results
                    (strategy_name, symbol, start_date, end_date,
                     initial_cash, final_value,
                     total_return, annual_return, max_drawdown,
                     sharpe_ratio, total_trades, win_rate, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    strategy_name,
                    symbol,
                    start_date,
                    end_date,
                    initial_cash,
                    final_value,
                    metrics.get("total_return"),
                    metrics.get("annual_return"),
                    metrics.get("max_drawdown"),
                    metrics.get("sharpe_ratio"),
                    metrics.get("total_trades"),
                    metrics.get("win_rate"),
                    config_str,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_stock_data(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            股票数据DataFrame
        """
        query = "SELECT * FROM stock_daily WHERE ts_code = ?"
        params = [ts_code]
        
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY trade_date"
        
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)

    def search_backtest_results(
        self,
        strategy_name_keyword: Optional[str] = None,
        created_start: Optional[str] = None,
        created_end: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """按策略名和创建时间检索历史回测结果。"""
        query = """
            SELECT id, strategy_name, symbol, start_date, end_date,
                   total_return, annual_return, max_drawdown, sharpe_ratio,
                   total_trades, win_rate, created_at
            FROM backtest_results
            WHERE 1=1
        """
        params: List[Any] = []

        if strategy_name_keyword:
            query += " AND strategy_name LIKE ?"
            params.append(f"%{strategy_name_keyword}%")

        if created_start:
            query += " AND created_at >= ?"
            params.append(created_start)

        if created_end:
            query += " AND created_at <= ?"
            params.append(created_end)

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(int(limit))

        return self.execute_query(query, tuple(params))

    def compare_backtest_results(self, result_id_a: int, result_id_b: int) -> Dict[str, Any]:
        """比较两次实验结果，返回关键指标差异和差异来源说明。"""
        rows = self.execute_query(
            """
            SELECT * FROM backtest_results
            WHERE id IN (?, ?)
            ORDER BY id ASC
            """,
            (result_id_a, result_id_b),
        )

        if len(rows) != 2:
            raise ValueError("待比较实验不存在或数量不足")

        row_a, row_b = rows[0], rows[1]

        metric_keys = [
            "final_value",
            "total_return",
            "annual_return",
            "max_drawdown",
            "sharpe_ratio",
            "total_trades",
            "win_rate",
        ]

        metric_diff: Dict[str, Dict[str, Any]] = {}
        for key in metric_keys:
            va = row_a.get(key)
            vb = row_b.get(key)
            if va is None or vb is None:
                delta = None
            else:
                delta = vb - va
            metric_diff[key] = {
                "a": va,
                "b": vb,
                "delta_b_minus_a": delta,
            }

        config_a = self._safe_load_json(row_a.get("config_json"))
        config_b = self._safe_load_json(row_b.get("config_json"))
        source_diff = self._build_comparison_sources(row_a, row_b, config_a, config_b)

        return {
            "result_id_a": row_a["id"],
            "result_id_b": row_b["id"],
            "strategy_name_a": row_a["strategy_name"],
            "strategy_name_b": row_b["strategy_name"],
            "metric_diff": metric_diff,
            "source_diff": source_diff,
        }

    @staticmethod
    def _safe_load_json(payload: Any) -> Dict[str, Any]:
        if not payload:
            return {}
        try:
            if isinstance(payload, str):
                return json.loads(payload)
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
        return {}

    def _build_comparison_sources(
        self,
        row_a: Dict[str, Any],
        row_b: Dict[str, Any],
        config_a: Dict[str, Any],
        config_b: Dict[str, Any],
    ) -> List[str]:
        source_diff: List[str] = []

        if row_a.get("strategy_name") != row_b.get("strategy_name"):
            source_diff.append("策略名称不同")

        if row_a.get("symbol") != row_b.get("symbol"):
            source_diff.append("标的不同")

        period_a = (row_a.get("start_date"), row_a.get("end_date"))
        period_b = (row_b.get("start_date"), row_b.get("end_date"))
        if period_a != period_b:
            source_diff.append("回测区间不同")

        if config_a.get("commission_rate") != config_b.get("commission_rate"):
            source_diff.append("手续费率不同")
        if config_a.get("slippage_rate") != config_b.get("slippage_rate"):
            source_diff.append("滑点率不同")

        snapshot_a = config_a.get("experiment_snapshot", {})
        snapshot_b = config_b.get("experiment_snapshot", {})

        params_a = snapshot_a.get("strategy_snapshot", {}).get("strategy_params", {})
        params_b = snapshot_b.get("strategy_snapshot", {}).get("strategy_params", {})
        if params_a != params_b:
            source_diff.append("策略参数不同")

        pool_a = snapshot_a.get("ts_codes_snapshot", [])
        pool_b = snapshot_b.get("ts_codes_snapshot", [])
        if pool_a != pool_b:
            source_diff.append("股票池快照不同")

        data_scope_a = snapshot_a.get("data_scope", {})
        data_scope_b = snapshot_b.get("data_scope", {})
        if data_scope_a != data_scope_b:
            source_diff.append("数据口径不同")

        if not source_diff:
            source_diff.append("未检测到显式配置差异，可能来自数据更新或随机性")

        return source_diff