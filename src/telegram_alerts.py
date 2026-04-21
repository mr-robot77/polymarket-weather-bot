from __future__ import annotations
import requests
import os
import logging
from typing import Optional

class TelegramAlerts:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else ""
        
    def send_alert(self, message: str) -> None:
        if not self.token or not self.chat_id:
            logging.info(f"Telegram alert not sent (no token/chat_id): {message}")
            return
            
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            requests.post(self.base_url, json=payload, timeout=5)
        except requests.RequestException as e:
            logging.error(f"Failed to send Telegram alert: {e}")
