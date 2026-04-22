import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import sqlite3
from reporter import reporter
import json
from datetime import datetime

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Weather Trading Bot active. Send /help for commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """🚀 <b>Weather Trading Bot Help</b>

/report - 📊 Enhanced P&L report(Last 24h & Weekly)
/status - 🤖 Detailed bot health and last scan info
/stats - 💰 Total bankroll and all-time trade statistics
/markets - 🔍 View currently active weather markets
/cities - 🏙 View monitored cities
/logs - 📡 View the last 10 market scans
/analyst - 🧠 View latest AI optimization insights
/rules - 📝 View the current AI-generated trading rules
/wisdom - 🧘 View the bot's strategic journal
/reflect - 🧠 Trigger self-improvement
/restart - 🔄 Restart the bot process
/help - 🚀 Show help and commands

You can also use numbers 1-12 for quick access."""
    await update.message.reply_html(help_text)

async def cmd_wisdom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        wisdom_path = "logs/wisdom_journal.json"
        if not os.path.exists(wisdom_path):
            await update.message.reply_text("The bot hasn't shared any wisdom yet. Wait for the first reflection cycle.")
            return
            
        with open(wisdom_path, "r") as f:
            journal = json.load(f)
            
        if not journal:
            await update.message.reply_text("The wisdom journal is empty.")
            return
            
        msg = "🧠 <b>The Bot's Wisdom Journal</b>\n\n"
        # Show last 5 insights
        for entry in reversed(journal[-5:]):
            ts = entry.get("timestamp", "Unknown")
            # Format timestamp if it's ISO
            if "T" in ts:
                ts = ts.split("T")[0]
            insight = entry.get("insight", "No insight recorded.")
            msg += f"📅 <b>{ts}</b>: {insight}\n\n"
            
        await update.message.reply_html(msg)
    except Exception as e:
        logger.error(f"Error in cmd_wisdom: {e}")
        await update.message.reply_text("Error reading wisdom journal.")

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Restarting bot... please wait a few seconds.")
    # Exit process; systemd will restart it
    os._exit(1)

async def cmd_markets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not os.path.exists("logs/found_markets.json"):
            await update.message.reply_text("No scanned markets found. Wait for the next scan cycle.")
            return
            
        with open("logs/found_markets.json", "r") as f:
            data = json.load(f)
            
        markets = data.get("markets", [])
        ts = data.get("timestamp", "Unknown")
        ts_str = datetime.fromisoformat(ts).strftime("%H:%M:%S") if "T" in ts else ts
        
        if not markets:
            await update.message.reply_text(f"Last scan ({ts_str}) found no active weather markets.")
            return
            
        msg = f"🔍 <b>Active Weather Markets</b> ({ts_str})\n\n"
        # Limit to top 15 to avoid telegram message size limits
        for m in markets[:15]:
            city = m.get("city", "Unknown")
            date = m.get("date", "Unknown")
            q = m.get("question", m.get("title", ""))
            
            # Use icons and better labels
            if city in ["Unknown", "Increase", "Decrease", "Global"]:
                header = "🌍 <b>Global</b>"
            else:
                header = f"🏙 <b>{city}</b>"
                
            if date != "Unknown":
                header += f" ({date})"
            
            # Extract simple title from question if it's too long
            title = q.split("?")[0] + "?" if "?" in q else q
            
            # Get current price if available
            price = "N/A"
            tokens = m.get("tokens")
            if tokens and isinstance(tokens, list) and len(tokens) > 0:
                try:
                    p_val = tokens[0].get("price")
                    if p_val is not None:
                        price = f"{float(p_val):.1%}"
                except (ValueError, TypeError):
                    pass
            
            msg += f"{header}:\n{title} | 💰 {price}\n\n"
            
        if len(markets) > 15:
            msg += f"<i>...and {len(markets) - 15} more markets.</i>"
            
        await update.message.reply_html(msg)
    except Exception as e:
        logger.error(f"Error in cmd_markets: {e}")
        await update.message.reply_text(f"Error reading markets: {e}")

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Generating report...")
    # Generate daily report manually
    # For a direct reply we can capture the message, but reporter sends an alert to the chat.
    # Let's temporarily override reporter's send_alert
    original_send = reporter.alerts.send_alert
    
    response_msg = []
    def custom_send(msg):
        response_msg.append(msg)
        
    reporter.alerts.send_alert = custom_send
    reporter.send_morning_report()
    reporter.alerts.send_alert = original_send
    
    if response_msg:
        await update.message.reply_html(response_msg[0])
    else:
        await update.message.reply_text("No trades found.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from paper_trader import paper_trader
        last_scan = "None"
        found_count = 0
        if os.path.exists("logs/actions.json"):
            with open("logs/actions.json", "r") as f:
                for line in f:
                    if "SCAN_COMPLETE" in line:
                        data = json.loads(line)
                        last_scan = data["timestamp"]
                        found_count = data["details"].get("found_count", 0)
        
        from config import CITIES, EDGE_THRESHOLD
        
        # Calculate staked
        conn = sqlite3.connect("trades.db")
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM trades WHERE status = 'OPEN'")
        staked = cursor.fetchone()[0] or 0.0
        conn.close()
        
        msg = "🤖 <b>Bot Operational Status</b>\n\n"
        msg += f"✅ <b>Mode:</b> {'Live' if '--live' in ' '.join(os.sys.argv) else 'Paper Trading'}\n"
        msg += f"🏦 <b>Bankroll:</b> ${paper_trader.balance:,.2f}\n"
        msg += f"🔒 <b>Staked:</b> ${staked:,.2f}\n"
        msg += f"🛰 <b>Last Scan:</b> {last_scan.split('T')[-1][:8] if 'T' in last_scan else last_scan}\n"
        msg += f"🔍 <b>Last Found:</b> {found_count} markets\n"
        msg += f"🎯 <b>Edge Threshold:</b> {EDGE_THRESHOLD:.2%}\n"
        msg += f"🌆 <b>Cities Monitored:</b> {len(CITIES)}\n"
        msg += f"💾 <b>DB Size:</b> {os.path.getsize('trades.db') // 1024} KB\n\n"
        msg += "Use /cities to see the full list of monitored locations."
        
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"Error checking status: {e}")

async def cmd_cities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from config import CITIES
    msg = "🏙 <b>Monitored Cities:</b>\n\n"
    for city, data in CITIES.items():
        msg += f"• <b>{city}</b>: Lat {data['lat']}, Lon {data['lon']} (RMSE: {data['rmse']})\n"
    await update.message.reply_html(msg)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        from reporter import reporter
        from paper_trader import paper_trader
        conn = sqlite3.connect("trades.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, date, market_id, city, amount, pnl, edge, is_morning FROM trades")
        all_rows = cursor.fetchall()
        
        # Calculate staked
        cursor.execute("SELECT SUM(amount) FROM trades WHERE status = 'OPEN'")
        staked = cursor.fetchone()[0] or 0.0
        conn.close()
        
        stats_msg = reporter.generate_enhanced_stats(all_rows, "Lifetime Performance")
        
        # Append Bankroll and Staked at the top or bottom
        msg = f"💰 <b>Financial Summary</b>\n"
        msg += f"🏦 Bankroll: ${paper_trader.balance:,.2f}\n"
        msg += f"🔒 Staked: ${staked:,.2f}\n\n"
        msg += stats_msg
        
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"Error reading stats: {e}")

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        events = []
        if os.path.exists("logs/actions.json"):
            with open("logs/actions.json", "r") as f:
                for line in f:
                    data = json.loads(line)
                    if data.get("action") in ["SCAN_COMPLETE", "TRADE_EXECUTED", "EDGE_FOUND"]:
                        events.append(data)
        
        recent_events = events[-15:]
        if not recent_events:
            await update.message.reply_text("No activity logs found.")
            return
            
        msg = "📡 <b>Recent Bot Activity</b>\n\n"
        for ev in reversed(recent_events):
            ts = datetime.fromisoformat(ev["timestamp"]).strftime("%H:%M:%S")
            action = ev["action"]
            details = ev.get("details", {})
            
            if action == "SCAN_COMPLETE":
                weather = details.get("weather_count", 0)
                total = details.get("total_scanned", 0)
                msg += f"<code>{ts}</code> 🔍 Scanned {total}, Found {weather} weather markets\n"
            elif action == "TRADE_EXECUTED":
                city = details.get("city", "Unknown")
                edge = details.get("edge", 0.0)
                msg += f"<code>{ts}</code> 💰 <b>TRADE:</b> {city} (Edge: {edge:.1%})\n"
            elif action == "EDGE_FOUND":
                city = details.get("city", "Unknown")
                msg += f"<code>{ts}</code> 🎯 <b>EDGE:</b> {city}\n"
            
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"Error reading logs: {e}")

async def cmd_analyst(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        with open("config/rules.json", "r") as f:
            rules = json.load(f)
        
        last_update = rules.get("last_analyst_update", "Never")
        blacklist = ", ".join(rules.get("blacklist", ["None"]))
        threshold = rules.get("edge_threshold", 0.0)
        
        msg = "🧠 <b>Latest Analyst Insights</b>\n\n"
        msg += f"📅 Last Optimization: {last_update}\n"
        msg += f"🎯 Edge Threshold: {threshold:.2%}\n"
        msg += f"🚫 Blacklisted Cities: {blacklist}\n\n"
        msg += "<i>The Analyst Bot automatically optimizes these parameters every 200 trades.</i>"
        
        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"Error reading analyst rules: {e}")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        with open("config/rules.json", "r") as f:
            rules = json.load(f)
        msg = "📝 <b>Current Trading Rules:</b>\n<pre>" + json.dumps(rules, indent=2) + "</pre>"
        await update.message.reply_html(msg)
    except FileNotFoundError:
        await update.message.reply_text("No custom rules found (config/rules.json).")
    except Exception as e:
        await update.message.reply_text(f"Error reading rules: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("❌ An internal error occurred while processing your command.")

async def cmd_reflect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🧠 Starting self-reflection and improvement cycle... this may take a moment.")
    from wisdom import wisdom_manager
    from settler import settler
    
    # Run settlement first
    settled = settler.settle_trades()
    await update.message.reply_text(f"✅ Settlement complete ({settled} trades settled). Now analyzing performance...")
    
    # Run improvement
    wisdom_manager.reflect_and_improve()
    await update.message.reply_text("✨ Reflection complete. Check /wisdom or /rules for updates.")

async def post_init(application: Application) -> None:
    from telegram import BotCommand
    logger.info("Setting bot commands in post_init...")
    commands = [
        BotCommand("help", "🚀 Show help and commands"),
        BotCommand("report", "📊 Enhanced P&L report(Last 24h & Weekly)"),
        BotCommand("status", "🤖 Detailed bot health and last scan info"),
        BotCommand("stats", "💰 Total bankroll and all-time trade statistics"),
        BotCommand("markets", "🔍 View currently active weather markets"),
        BotCommand("cities", "🏙 View monitored cities"),
        BotCommand("logs", "📡 View the last 10 market scans"),
        BotCommand("analyst", "🧠 View latest AI optimization insights"),
        BotCommand("rules", "📝 View the current AI-generated trading rules"),
        BotCommand("wisdom", "🧘 View the bot's strategic journal"),
        BotCommand("reflect", "🧠 Trigger self-improvement"),
        BotCommand("restart", "🔄 Restart the bot process")
    ]
    try:
        success = await application.bot.set_my_commands(commands)
        logger.info(f"Set commands success: {success}")
    except Exception as e:
        logger.error(f"Failed to set commands: {e}")

def run_telegram_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found.")
        return

    application = Application.builder().token(token).post_init(post_init).build()
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("1", cmd_report))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("2", cmd_status))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("3", cmd_stats))
    application.add_handler(CommandHandler("markets", cmd_markets))
    application.add_handler(CommandHandler("4", cmd_markets))
    application.add_handler(CommandHandler("cities", cmd_cities))
    application.add_handler(CommandHandler("5", cmd_cities))
    application.add_handler(CommandHandler("logs", cmd_logs))
    application.add_handler(CommandHandler("6", cmd_logs))
    application.add_handler(CommandHandler("analyst", cmd_analyst))
    application.add_handler(CommandHandler("7", cmd_analyst))
    application.add_handler(CommandHandler("rules", cmd_rules))
    application.add_handler(CommandHandler("8", cmd_rules))
    application.add_handler(CommandHandler("wisdom", cmd_wisdom))
    application.add_handler(CommandHandler("9", cmd_wisdom))
    application.add_handler(CommandHandler("reflect", cmd_reflect))
    application.add_handler(CommandHandler("10", cmd_reflect))
    application.add_handler(CommandHandler("restart", cmd_restart))
    application.add_handler(CommandHandler("11", cmd_restart))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("12", help_command))

    # Run the bot until the user presses Ctrl-C
    # Since we are running in a thread, we'll use run_polling with empty stop_signals
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=())

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    run_telegram_bot()