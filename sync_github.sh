#!/bin/bash
cd /root/polymarket-weather-bot
git add .
git commit -m "Auto-sync: $(date)"
git push origin main
