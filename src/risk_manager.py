from __future__ import annotations
import sqlite3
import datetime
from typing import Dict, Any

class RiskManager:
    def __init__(self, db_path: str = "trades.db") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
        self.load_daily_metrics()
        
    def create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                date TEXT,
                market_id TEXT,
                city TEXT,
                amount REAL,
                price REAL,
                pnl REAL,
                edge REAL,
                is_morning INTEGER,
                type TEXT,
                status TEXT DEFAULT 'OPEN',
                actual_value REAL,
                min_temp REAL,
                max_temp REAL,
                target_date TEXT,
                question TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                day TEXT PRIMARY KEY,
                total_trades INTEGER,
                exposure REAL,
                daily_loss REAL,
                lost_trades INTEGER
            )
        """)
        # Migration: Add columns if they don't exist
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        if "city" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN city TEXT")
        if "price" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN price REAL")
        if "edge" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN edge REAL")
        if "is_morning" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN is_morning INTEGER DEFAULT 0")
        if "type" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN type TEXT")
        if "status" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN status TEXT DEFAULT 'OPEN'")
        if "actual_value" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN actual_value REAL")
        if "min_temp" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN min_temp REAL")
        if "max_temp" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN max_temp REAL")
        if "target_date" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN target_date TEXT")
        if "question" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN question TEXT")
            
        self.conn.commit()

    def load_daily_metrics(self) -> None:
        today = datetime.date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("SELECT total_trades, exposure, daily_loss, lost_trades FROM daily_metrics WHERE day = ?", (today,))
        row = cursor.fetchone()
        if row:
            self.total_trades_today, self.exposure, self.daily_loss, self.lost_trades = row
        else:
            self.total_trades_today = 0
            self.exposure = 0.0
            self.daily_loss = 0.0
            self.lost_trades = 0
            self.conn.execute("INSERT INTO daily_metrics VALUES (?, 0, 0.0, 0.0, 0)", (today,))
            self.conn.commit()

    def save_daily_metrics(self) -> None:
        today = datetime.date.today().isoformat()
        self.conn.execute("""
            UPDATE daily_metrics 
            SET total_trades = ?, exposure = ?, daily_loss = ?, lost_trades = ?
            WHERE day = ?
        """, (self.total_trades_today, self.exposure, self.daily_loss, self.lost_trades, today))
        self.conn.commit()
        
    def check_circuit_breaker(self, bankroll: float) -> bool:
        import config
        cfg = config.get_config()
        max_loss_pct = cfg.get("max_daily_loss_pct", 0.05)
        
        if self.lost_trades >= 12 and self.total_trades_today >= 20:
            return True
        if self.daily_loss > bankroll * max_loss_pct:
            return True
        return False
        
    def record_trade(self, market_id: str, city: str, amount: float, price: float, edge: float, trade_type: str = "REAL", 
                     min_temp: float = None, max_temp: float = None, target_date: str = None, question: str = None) -> None:
        now = datetime.datetime.now()
        date_str = now.isoformat()
        # Morning is defined as 04:00 to 11:59
        is_morning = 1 if 4 <= now.hour < 12 else 0
        
        self.conn.execute("""
            INSERT INTO trades (date, market_id, city, amount, price, pnl, edge, is_morning, type, min_temp, max_temp, target_date, question) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, market_id, city, amount, price, 0.0, edge, is_morning, trade_type, min_temp, max_temp, target_date, question))
        
        self.total_trades_today += 1
        self.exposure += amount
        self.save_daily_metrics()
        self.conn.commit()

    def get_total_trade_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        return cursor.fetchone()[0]

    def has_open_position(self, market_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE market_id = ? AND status = 'OPEN'", (market_id,))
        return cursor.fetchone() is not None
