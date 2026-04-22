import os
import json
import sqlite3
import subprocess
import logging
from datetime import datetime
from logger import logger
from telegram_alerts import TelegramAlerts

WISDOM_PROMPT = """You are the "Master Brain" of an autonomous weather trading system. 
You are wise, strategic, and highly analytical. You think like a senior quantitative trader.

CURRENT PERFORMANCE:
- Bankroll: {balance}
- Total PnL: {total_pnl}
- Win Rate: {win_rate:.2%}
- Cycles Completed: {cycles}

TRADE HISTORY (Last 50):
{log_data}

PREVIOUS WISDOM JOURNAL:
{journal_data}

CURRENT CONFIGURATION (rules.json & config.json):
{current_config}

GOAL:
- Evolve your strategy to maximize growth while preserving capital.
- Identify hidden patterns (e.g., specific cities, time of day, price ranges).
- Adjust your risk parameters (edge_threshold, kelly_fraction, etc.).
- Update city-specific RMSE values to improve forecast probability accuracy.

TASK:
1. CRITICAL ANALYSIS: Why did we win or lose the recent trades? Is there a pattern?
2. STRATEGIC SHIFT: Should we be more aggressive or more defensive?
3. CONFIGURATION UPDATES: 
   - Suggest changes to rules.json (edge_threshold, kelly_fraction, max_total_exposure).
   - Suggest changes to config.json (RMSE for cities, or new city settings).
4. WISDOM INSIGHT: A profound realization for your journal.

CONSTRAINTS:
- 'edge_threshold' range: [0.02, 0.20]
- 'kelly_fraction' range: [0.02, 0.25]
- Output ONLY a JSON object with: "reasoning", "wisdom", "rules_update", "config_update".

Example:
{{
  "reasoning": "Analysis shows that Mumbai trades are consistently failing due to high volatility not captured by current RMSE...",
  "wisdom": "In periods of high volatility, the price of entry is less important than the margin of safety.",
  "rules_update": {{ "edge_threshold": 0.05, "kelly_fraction": 0.1 }},
  "config_update": {{ "cities": {{ "Mumbai": {{ "rmse": 4.5 }} }} }}
}}
"""

class WisdomManager:
    def __init__(self, db_path="trades.db", rules_path="config/rules.json", config_path="config/config.json", journal_path="logs/wisdom_journal.json"):
        self.db_path = db_path
        self.rules_path = rules_path
        self.config_path = config_path
        self.journal_path = journal_path
        self.gemini_path = os.getenv("GEMINI_PATH", "gemini")
        self.alerts = TelegramAlerts()

    def reflect_and_improve(self, cycles=0):
        logging.info("Starting Wisdom Reflection Cycle...")
        
        try:
            # Gather Data
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT city, amount, price, pnl, edge, is_morning, actual_value, min_temp, max_temp, question 
                FROM trades 
                WHERE status = 'CLOSED' 
                ORDER BY date DESC 
                LIMIT 50
            """)
            columns = [column[0] for column in cursor.description]
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            cursor.execute("SELECT SUM(pnl), COUNT(*), SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) FROM trades WHERE status = 'CLOSED'")
            total_pnl, total_closed, total_wins = cursor.fetchone()
            win_rate = total_wins / total_closed if total_closed > 0 else 0
            conn.close()

            from paper_trader import paper_trader
            balance = paper_trader.balance

            with open(self.rules_path) as f:
                rules = json.load(f)
            with open(self.config_path) as f:
                config = json.load(f)
            
            journal = []
            if os.path.exists(self.journal_path):
                with open(self.journal_path) as f:
                    journal = json.load(f)

            prompt = WISDOM_PROMPT.format(
                balance=f"${balance:.2f}",
                total_pnl=f"${total_pnl or 0:.2f}",
                win_rate=win_rate,
                cycles=cycles,
                log_data=json.dumps(trades, indent=2),
                journal_data=json.dumps(journal[-5:], indent=2),
                current_config=json.dumps({"rules": rules, "config": config}, indent=2)
            )

            result = subprocess.run(
                [self.gemini_path, "-p", prompt],
                capture_output=True, text=True, check=True
            )
            
            output = self.extract_json(result.stdout)
            if output:
                self.apply_wisdom(output)
            else:
                logging.error("Failed to extract JSON from Wisdom reflection.")

        except Exception as e:
            logging.error(f"Error in Wisdom reflection: {e}")

    def extract_json(self, text):
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
        except:
            return None

    def apply_wisdom(self, output):
        reasoning = output.get("reasoning", "")
        wisdom = output.get("wisdom", "")
        rules_update = output.get("rules_update", {})
        config_update = output.get("config_update", {})

        logging.info(f"Applying Wisdom: {wisdom}")
        logging.info(f"Reasoning: {reasoning}")

        # Update Rules
        if rules_update:
            with open(self.rules_path, "r") as f:
                current_rules = json.load(f)
            
            for k, v in rules_update.items():
                if k == "edge_threshold":
                    current_rules[k] = max(0.02, min(0.20, v))
                elif k == "kelly_fraction":
                    current_rules[k] = max(0.02, min(0.25, v))
                else:
                    current_rules[k] = v
            
            with open(self.rules_path, "w") as f:
                json.dump(current_rules, f, indent=4)
            logger.log_action("WISDOM_RULES_UPDATED", rules_update)

        # Update Config
        if config_update:
            with open(self.config_path, "r") as f:
                current_config = json.load(f)
            
            if "cities" in config_update:
                for city, updates in config_update["cities"].items():
                    if city in current_config.get("cities", {}):
                        current_config["cities"][city].update(updates)
            
            with open(self.config_path, "w") as f:
                json.dump(current_config, f, indent=4)
            logger.log_action("WISDOM_CONFIG_UPDATED", config_update)

        # Save to Journal
        self.save_to_journal(wisdom, reasoning)
        self.alerts.send_alert(f"🧠 <b>Deep Wisdom Attained</b>\n\n<b>Insight:</b> {wisdom}\n\n<b>Reasoning:</b> {reasoning[:300]}...")

    def save_to_journal(self, wisdom, reasoning):
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
        journal = []
        if os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, "r") as f:
                    journal = json.load(f)
            except:
                pass
        
        journal.append({
            "timestamp": datetime.now().isoformat(),
            "wisdom": wisdom,
            "reasoning": reasoning
        })
        
        with open(self.journal_path, "w") as f:
            json.dump(journal[-100:], f, indent=4)

wisdom_manager = WisdomManager()
