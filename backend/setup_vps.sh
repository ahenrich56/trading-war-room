#!/bin/bash
set -e

echo "====================================="
echo " Setting up War Room API on VPS... "
echo "====================================="

# 1. Install prerequisites
echo "[1/4] Checking python3-venv..."
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip

# 2. Virtual Environment
echo "[2/4] Setting up Virtual Environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure Systemd Service
echo "[3/4] Installing systemd background service..."
# Get the absolute path of the backend directory
BACKEND_DIR=$(pwd)
sed -i "s|/root/trading-war-room/backend|$BACKEND_DIR|g" war-room.service

sudo cp war-room.service /etc/systemd/system/war-room.service
sudo systemctl daemon-reload
sudo systemctl enable war-room
sudo systemctl restart war-room

echo "[4/4] Complete! War Room API is now live."
echo "Check logs with: journalctl -u war-room -f"
