import sqlite3
import datetime
from src.settler import TradeSettler

def test_settlement():
    # Insert a fake trade for London on April 20, 2026
    conn = sqlite3.connect("trades.db")
    cursor = conn.cursor()
    
    # Clean up old tests
    cursor.execute("DELETE FROM trades WHERE market_id = 'test_market_1'")
    
    # London coord: 51.5, -0.1
    # Market: Temp in London on April 20 be between 40 and 100 F
    cursor.execute("""
        INSERT INTO trades (date, market_id, city, amount, pnl, edge, is_morning, type, status, min_temp, max_temp, target_date, question)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.datetime.now().isoformat(),
        "test_market_1",
        "London",
        10.0,
        0.0,
        0.1,
        1,
        "PAPER",
        "OPEN",
        40.0,
        100.0,
        "April 20",
        "Will the temperature in London be between 40 and 100°F on April 20?"
    ))
    conn.commit()
    conn.close()
    
    print("Inserted test trade.")
    
    settler = TradeSettler()
    settled = settler.settle_trades()
    print(f"Settled {settled} trades.")
    
    conn = sqlite3.connect("trades.db")
    cursor = conn.cursor()
    cursor.execute("SELECT pnl, status, actual_value FROM trades WHERE market_id = 'test_market_1'")
    row = cursor.fetchone()
    print(f"Result: pnl={row[0]}, status={row[1]}, actual_value={row[2]}")
    conn.close()

if __name__ == "__main__":
    test_settlement()
