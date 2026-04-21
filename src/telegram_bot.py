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

/report - 📊 Enhanced P&L report (City/Time breakdown)
/status - 🤖 Check bot status and active markets
/stats - 💰 Detailed bankroll and trade statistics
/logs - 📡 View the last 10 market scans
/analyst - 🧠 View latest AI optimization insights
/rules - 📝 View the current trading rules
/restart - 🔄 Restart the bot process

You can also use numbers 1-6 for quick access."""
    await update.message.reply_html(help_text)

async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Restarting bot... please wait a few seconds.")
    # Exit process; systemd will restart it
    os._exit(1)

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
    await update.message.reply_text("Bot is running in 24/7 autonomous mode. Check logs for recent scans.")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        conn = sqlite3.connect("trades.db")
        cursor = conn.cursor()
        
        # Total stats
        cursor.execute("SELECT COUNT(*), SUM(pnl) FROM trades")
        count, pnl = cursor.fetchone()
        pnl = pnl if pnl is not None else 0.0
        
        # Morning vs Evening
        cursor.execute("SELECT is_morning, COUNT(*), SUM(pnl) FROM trades GROUP BY is_morning")
        time_stats = cursor.fetchall()
        
        # Top city
        cursor.execute("SELECT city, SUM(pnl) as total_pnl FROM trades WHERE city IS NOT NULL AND city != 'Unknown' GROUP BY city ORDER BY total_pnl DESC LIMIT 1")
        top_city_row = cursor.fetchone()
        
        conn.close()
        
        msg = f"📊 <b>Advanced Bot Stats</b>\n"
        msg += f"Total Trades: {count}\n"
        msg += f"Net P&L: ${pnl:.2f}\n\n"
        
        if top_city_row:
            msg += f"🏙 <b>Best City:</b> {top_city_row[0]} (${top_city_row[1]:.2f})\n"
            
        for is_m, c, p in time_stats:
            label = "☀️ Morning" if is_m else "🌙 Evening"
            msg += f"{label}: {c} trades, ${p if p else 0:.2f} P&L\n"

        await update.message.reply_html(msg)
    except Exception as e:
        await update.message.reply_text(f"Error reading stats: {e}")

async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        scans = []
        if os.path.exists("logs/actions.json"):
            with open("logs/actions.json", "r") as f:
                for line in f:
                    if "SCAN_COMPLETE" in line:
                        scans.append(json.loads(line))
        
        recent_scans = scans[-10:]
        if not recent_scans:
            await update.message.reply_text("No scan logs found.")
            return
            
        msg = "📡 <b>Recent Market Scans</b>\n\n"
        for scan in reversed(recent_scans):
            ts = datetime.fromisoformat(scan["timestamp"]).strftime("%H:%M:%S")
            count = scan["details"].get("found_count", 0)
            msg += f"<code>{ts}</code> - Found {count} markets\n"
            
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

def run_telegram_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found.")
        return

    application = Application.builder().token(token).build()
    application.add_error_handler(error_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", cmd_report))
    application.add_handler(CommandHandler("1", cmd_report))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("2", cmd_status))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("3", cmd_stats))
    application.add_handler(CommandHandler("rules", cmd_rules))
    application.add_handler(CommandHandler("4", cmd_rules))
    application.add_handler(CommandHandler("analyst", cmd_analyst))
    application.add_handler(CommandHandler("5", cmd_analyst))
    application.add_handler(CommandHandler("logs", cmd_logs))
    application.add_handler(CommandHandler("6", cmd_logs))
    application.add_handler(CommandHandler("restart", cmd_restart))

    # Run the bot until the user presses Ctrl-C
    # Since we are running in a thread, we'll use run_polling with empty stop_signals
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=())

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    run_telegram_bot()