from __future__ import annotations
import sqlite3
import datetime
from typing import Dict, Any

class RiskManager:
    def __init__(self, db_path: str = "trades.db") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()
        self.daily_loss = 0.0
        self.lost_trades = 0
        self.total_trades_today = 0
        self.exposure = 0.0
        
    def create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                date TEXT,
                market_id TEXT,
                city TEXT,
                amount REAL,
                pnl REAL,
                edge REAL,
                is_morning INTEGER
            )
        """)
        # Migration: Add columns if they don't exist
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        if "city" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN city TEXT")
        if "edge" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN edge REAL")
        if "is_morning" not in columns:
            self.conn.execute("ALTER TABLE trades ADD COLUMN is_morning INTEGER DEFAULT 0")
            
        self.conn.commit()
        
    def check_circuit_breaker(self, bankroll: float) -> bool:
        if self.lost_trades >= 12 and self.total_trades_today >= 20:
            return True
        if self.daily_loss > bankroll * 0.10:
            return True
        return False
        
    def record_trade(self, market_id: str, city: str, amount: float, edge: float) -> None:
        now = datetime.datetime.now()
        date_str = now.isoformat()
        # Morning is defined as 04:00 to 11:59
        is_morning = 1 if 4 <= now.hour < 12 else 0
        
        self.conn.execute("""
            INSERT INTO trades (date, market_id, city, amount, pnl, edge, is_morning) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_str, market_id, city, amount, 0.0, edge, is_morning))
        self.conn.commit()
        self.total_trades_today += 1
        self.exposure += amount

    def get_total_trade_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        return cursor.fetchone()[0]
