import subprocess
import json
import os
from logger import logger

IMPROVEMENT_PROMPT = """You are an elite quant trading coach. Here is the last 24h trade log (JSON) and current rules.json.

Trade log: {log_data}
Current rules: {current_rules}

1. Calculate overall P&L, win rate, biggest losses.
2. Identify repeating mistakes (e.g. ignored liquidity, bad thresholds, over-trading low-volume markets).
3. Output NEW rules.json (same format) with improved thresholds, new filters, new risk rules.
4. Suggest 1-2 small code improvements if needed.
5. Confidence score for each change.

Output ONLY the new rules.json content and a short summary."""

class SelfImprover:
    def __init__(self, rules_path="config/rules.json", history_path="logs/trades.csv"):
        self.rules_path = rules_path
        self.history_path = history_path
        self.gemini_path = os.getenv("GEMINI_PATH", "gemini")

    def improve(self):
        logger.log_action("SELF_IMPROVEMENT_START", {})
        
        if not os.path.exists(self.history_path):
            logger.log_action("IMPROVE_SKIP", {"msg": "No trade history yet"})
            return

        with open(self.rules_path) as f:
            current_rules = f.read()
        
        with open(self.history_path) as f:
            history = f.readlines()[-20:] # Last 20 trades
            
        prompt = IMPROVEMENT_PROMPT.format(
            log_data=''.join(history),
            current_rules=current_rules
        )
        
        try:
            # Using Gemini CLI to process the prompt
            result = subprocess.run(
                [self.gemini_path, "ask", prompt], 
                capture_output=True, text=True, check=True
            )
            
            new_rules_json = self.extract_json(result.stdout)
            if new_rules_json:
                with open(self.rules_path, "w") as f:
                    f.write(new_rules_json)
                logger.log_action("RULES_UPDATED", {"new_rules": new_rules_json})
                
        except Exception as e:
            logger.log_action("IMPROVE_EXCEPTION", {"error": str(e)})

    def extract_json(self, text):
        # Basic extraction logic for JSON from LLM output
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                return text[start:end]
        except:
            return None

self_improver = SelfImprover()
