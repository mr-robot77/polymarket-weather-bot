import time
import json
import os
import pandas as pd
import sqlite3
from datetime import datetime
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align
import plotext as plt

BOT_NAME = "Polymarket Weather Bot"

def load_trades():
    if os.path.exists("trades.db"):
        try:
            conn = sqlite3.connect("trades.db")
            # Convert to DataFrame with same column names as expected
            df = pd.read_sql_query("SELECT date as timestamp, city, amount as size, pnl, edge, is_morning, type, status, price FROM trades", conn)
            conn.close()
            # Add extra columns expected by dashboard
            if not df.empty:
                df["market"] = df["city"] + " Temp"
                df["outcome"] = "Yes"
                # Ensure type exists for old rows
                if "type" not in df.columns:
                    df["type"] = "REAL"
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def load_balance():
    if os.path.exists("data/paper_balance.json"):
        try:
            with open("data/paper_balance.json") as f:
                return json.load(f).get("balance", 1000.0)
        except:
            return 1000.0
    return 1000.0

def load_actions():
    actions = []
    if os.path.exists("logs/actions.json"):
        try:
            with open("logs/actions.json") as f:
                for line in f:
                    if line.strip():
                        actions.append(json.loads(line))
        except:
            pass
    return actions

def get_header(df_trades, next_refresh_in):
    # Check if we are running in live mode by looking at sys.argv or env
    import sys
    is_live = "--live" in sys.argv or os.getenv("LIVE_MODE") == "true"
    
    badge = Text(" LIVE [REALTIME] ", style="bold white on green") if is_live else Text(" PAPER TRADING ", style="bold white on yellow")
    
    header = Table.grid(expand=True)
    header.add_column(justify="left", ratio=1)
    header.add_column(justify="center", ratio=1)
    header.add_column(justify="right", ratio=1)
    
    title = Text(f"🤖 {BOT_NAME} Dashboard", style="bold cyan")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    refresh_text = Text(f"Refresh in {next_refresh_in}s", style="dim")
    
    header.add_row(title, badge, f"{timestamp} | {refresh_text}")
    return Panel(header, style="green" if is_live else "yellow")

def get_live_stats(df_trades, balance):
    table = Table(box=box.ROUNDED, expand=True, style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    
    total_trades = len(df_trades)
    staked = 0.0
    pnl = 0.0
    win_rate = 0.0
    m_wr = 0.0
    e_wr = 0.0
    
    if not df_trades.empty:
        if "size" in df_trades.columns and "status" in df_trades.columns:
            open_trades = df_trades[df_trades["status"].astype(str).str.contains("OPEN", na=False)]
            staked = pd.to_numeric(open_trades["size"], errors="coerce").sum()
        if "pnl" in df_trades.columns:
            pnl = pd.to_numeric(df_trades["pnl"], errors="coerce").sum()
            
        closed_trades = df_trades[~df_trades["status"].astype(str).str.contains("OPEN", na=False)]
        if not closed_trades.empty and "pnl" in closed_trades.columns:
            wins = len(closed_trades[pd.to_numeric(closed_trades["pnl"], errors="coerce") > 0])
            total_closed = len(closed_trades)
            win_rate = (wins / total_closed) * 100 if total_closed > 0 else 0.0
            
            # M/E Split
            if "is_morning" in closed_trades.columns:
                m_closed = closed_trades[closed_trades["is_morning"] == 1]
                e_closed = closed_trades[closed_trades["is_morning"] == 0]
                m_wr = (len(m_closed[m_closed["pnl"] > 0]) / len(m_closed) * 100) if not m_closed.empty else 0.0
                e_wr = (len(e_closed[e_closed["pnl"] > 0]) / len(e_closed) * 100) if not e_closed.empty else 0.0
            
    table.add_row("🏦 Bankroll", f"${balance:,.2f}")
    table.add_row("📈 Total P&L", f"[green]+${pnl:,.2f}[/green]" if pnl >= 0 else f"[red]-${abs(pnl):,.2f}[/red]")
    table.add_row("🔒 Staked", f"${staked:,.2f}")
    table.add_row("🎯 Win Rate", f"{win_rate:.1f}%")
    table.add_row("☀️ Morning WR", f"{m_wr:.1f}%")
    table.add_row("🌙 Evening WR", f"{e_wr:.1f}%")
    table.add_row("🔄 Trades", str(total_trades))
    
    return Panel(table, title="📊 Live Stats", border_style="cyan")

def get_circuit_breaker(df_trades):
    # Mocking or calculating loss streak
    loss_streak = 0
    daily_loss = 0.0
    
    if not df_trades.empty and "pnl" in df_trades.columns and "timestamp" in df_trades.columns:
        df_trades_copy = df_trades.copy()
        df_trades_copy["timestamp"] = pd.to_datetime(df_trades_copy["timestamp"], errors="coerce")
        today = datetime.now().date()
        daily_trades = df_trades_copy[df_trades_copy["timestamp"].dt.date == today]
        
        if not daily_trades.empty:
            daily_loss = min(0, pd.to_numeric(daily_trades["pnl"], errors="coerce").sum())
        
        # Calculate loss streak
        pnls = pd.to_numeric(df_trades["pnl"], errors="coerce").fillna(0).tolist()
        for val in reversed(pnls):
            if val < 0:
                loss_streak += 1
            elif val > 0:
                break

    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column("Metric", style="bold yellow")
    table.add_column("Status", justify="right")
    
    streak_bar = "🟥" * min(5, loss_streak) + "🟩" * max(0, 5 - loss_streak)
    daily_loss_pct = min(100, (abs(daily_loss) / 100.0) * 100) # assuming max $100 daily loss limit
    loss_bar_len = int(daily_loss_pct / 10)
    loss_bar = "🟥" * loss_bar_len + "⬜" * (10 - loss_bar_len)
    
    status_text = "[green]NORMAL[/green]" if loss_streak < 3 and abs(daily_loss) < 50 else "[red]WARNING[/red]"
    
    table.add_row("System Status", status_text)
    table.add_row("Loss Streak", streak_bar)
    table.add_row("Daily Loss", f"{loss_bar} (${abs(daily_loss):.2f})")
    
    return Panel(table, title="⚡ Circuit Breaker", border_style="yellow")

def get_city_performance(df_trades):
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("City")
    table.add_column("Trades", justify="right")
    table.add_column("P&L", justify="right")
    
    if df_trades.empty or "city" not in df_trades.columns:
        table.add_row("No city data", "0", "$0.00")
    else:
        perf = df_trades.groupby("city")["pnl"].agg(["count", "sum"]).sort_values("sum", ascending=False)
        for city, row in perf.iterrows():
            pnl = row["sum"]
            style = "green" if pnl >= 0 else "red"
            table.add_row(city, str(int(row["count"])), f"[{style}]${pnl:.2f}[/]")
            
    return Panel(table, title="🏙 City Performance", border_style="cyan")

def get_recent_trades(df_trades):
    table = Table(box=box.SIMPLE, expand=True, style="blue")
    table.add_column("Date", style="dim")
    table.add_column("Market")
    table.add_column("Side")
    table.add_column("Entry")
    table.add_column("Edge")
    table.add_column("Status")
    
    if df_trades.empty:
        table.add_row("No trades yet", "", "", "", "", "")
    else:
        recent = df_trades.tail(10).iloc[::-1] # Last 10, newest first
        for _, row in recent.iterrows():
            ts = pd.to_datetime(row.get("timestamp", "")).strftime("%m-%d %H:%M") if pd.notna(row.get("timestamp")) else "N/A"
            market = str(row.get("market", ""))[:35] + "..." if len(str(row.get("market", ""))) > 35 else str(row.get("market", ""))
            side = str(row.get("outcome", ""))
            
            try:
                price = f"${float(row.get('price', 0)):.2f}"
            except:
                price = "$0.00"
                
            try:
                edge = f"{float(row.get('edge', 0)):.3f}"
            except:
                edge = "0.000"
                
            status = str(row.get("status", ""))
            
            status_style = "green" if "OPEN" in status else "dim"
            table.add_row(ts, market, side, price, edge, f"[{status_style}]{status}[/]")
            
    return Panel(table, title="📝 Recent Trades (Last 10)", border_style="blue")

def get_edge_scanner(actions):
    table = Table(box=box.SIMPLE, expand=True)
    table.add_column("Time", style="dim")
    table.add_column("Event")
    table.add_column("Details")
    
    # Filter for scan and edge events
    relevant_actions = [a for a in actions if a.get("action") in ["SCAN_COMPLETE", "EDGE_FOUND", "REAL_TRADE_ATTEMPT"]]
    recent_actions = relevant_actions[-7:] if relevant_actions else []
    
    if not recent_actions:
        table.add_row("No scan data", "", "")
    else:
        for action in reversed(recent_actions):
            try:
                ts = datetime.fromisoformat(action.get("timestamp", "")).strftime("%H:%M:%S")
            except:
                ts = ""
            event = action.get("action", "")
            details = str(action.get("details", {}))
            table.add_row(ts, f"[magenta]{event}[/]", details[:40] + "..." if len(details) > 40 else details)
            
    return Panel(table, title="📡 Edge Scanner Activity", border_style="magenta")

def get_equity_curve(df_trades):
    plt.clf()
    plt.plotsize(80, 15)
    plt.theme("dark")
    
    if df_trades.empty or "pnl" not in df_trades.columns:
        plt.plot([0, 1, 2], [0, 0, 0], color="green", marker="dot")
    else:
        pnls = pd.to_numeric(df_trades["pnl"], errors="coerce").fillna(0).tolist()
        cumulative = []
        current = 0
        for p in pnls:
            current += p
            cumulative.append(current)
            
        # Add initial point
        cumulative.insert(0, 0)
        plt.plot(cumulative, color="green", marker="dot")
        
    plt.title("Cumulative P&L")
    
    # Convert plotext plot to a rich Text object
    try:
        ansi_string = plt.build()
        text = Text.from_ansi(ansi_string)
    except Exception as e:
        text = Text(f"Error rendering plot: {e}", style="red")
        
    return Panel(text, title="📈 Equity Curve", border_style="green")

def generate_layout(next_refresh_in):
    df_trades = load_trades()
    balance = load_balance()
    actions = load_actions()

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
    )
    
    layout["main"].split_row(
        Layout(name="left_col", ratio=1),
        Layout(name="right_col", ratio=2)
    )
    
    layout["left_col"].split_column(
        Layout(name="live_stats", size=11),
        Layout(name="circuit_breaker", size=7),
        Layout(name="city_performance", size=8),
        Layout(name="edge_scanner")
    )
    
    layout["right_col"].split_column(
        Layout(name="recent_trades", ratio=1),
        Layout(name="equity_curve", size=19)
    )
    
    layout["header"].update(get_header(df_trades, next_refresh_in))
    layout["live_stats"].update(get_live_stats(df_trades, balance))
    layout["circuit_breaker"].update(get_circuit_breaker(df_trades))
    layout["city_performance"].update(get_city_performance(df_trades))
    layout["edge_scanner"].update(get_edge_scanner(actions))
    layout["recent_trades"].update(get_recent_trades(df_trades))
    layout["equity_curve"].update(get_equity_curve(df_trades))
    
    return layout

def main():
    refresh_interval = 30
    try:
        # Initial render
        layout = generate_layout(refresh_interval)
        with Live(layout, refresh_per_second=4, screen=True) as live:
            while True:
                for i in range(refresh_interval, 0, -1):
                    live.update(generate_layout(i))
                    time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
