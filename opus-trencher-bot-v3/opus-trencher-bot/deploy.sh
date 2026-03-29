#!/bin/bash
# ============================================================
# OPUS Trencher Bot — VPS Deployment Script
# Deploys to Ubuntu VPS with systemd service management
# ============================================================

set -e

echo "=========================================="
echo "  OPUS Trencher Bot — VPS Deployment"
echo "=========================================="

# Config
APP_DIR="/opt/opus-trencher-bot"
APP_USER="opus-bot"
PYTHON_BIN="python3"
VENV_DIR="$APP_DIR/venv"

# 1. System dependencies
echo "[1/7] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git curl

# 2. Create app user (if not exists)
echo "[2/7] Setting up app user..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -r -m -s /bin/bash "$APP_USER"
fi

# 3. Create app directory
echo "[3/7] Setting up app directory..."
sudo mkdir -p "$APP_DIR"
sudo cp -r ./* "$APP_DIR/"
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# 4. Create Python virtual environment
echo "[4/7] Creating Python virtual environment..."
sudo -u "$APP_USER" $PYTHON_BIN -m venv "$VENV_DIR"
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt" -q

# 5. Create .env if not exists
if [ ! -f "$APP_DIR/.env" ]; then
    echo "[5/7] Creating .env template..."
    sudo -u "$APP_USER" cp "$APP_DIR/.env.example" "$APP_DIR/.env" 2>/dev/null || true
    echo ">>> IMPORTANT: Edit $APP_DIR/.env with your credentials!"
else
    echo "[5/7] .env already exists, skipping..."
fi

# 6. Create systemd service
echo "[6/7] Creating systemd service..."
sudo tee /etc/systemd/system/opus-bot.service > /dev/null << 'EOF'
[Unit]
Description=OPUS Trencher Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=opus-bot
Group=opus-bot
WorkingDirectory=/opt/opus-trencher-bot
ExecStart=/opt/opus-trencher-bot/venv/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/opus-bot.log
StandardError=append:/var/log/opus-bot-error.log

# Environment
EnvironmentFile=/opt/opus-trencher-bot/.env

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/opt/opus-trencher-bot
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# 7. Create log rotation
sudo tee /etc/logrotate.d/opus-bot > /dev/null << 'EOF'
/var/log/opus-bot*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 opus-bot opus-bot
}
EOF

# Enable and start
echo "[7/7] Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable opus-bot
sudo systemctl restart opus-bot

echo ""
echo "=========================================="
echo "  Deployment complete!"
echo "=========================================="
echo ""
echo "Commands:"
echo "  sudo systemctl status opus-bot     — Check status"
echo "  sudo systemctl restart opus-bot    — Restart bot"
echo "  sudo systemctl stop opus-bot       — Stop bot"
echo "  sudo journalctl -u opus-bot -f     — View live logs"
echo "  sudo tail -f /var/log/opus-bot.log — View log file"
echo ""
echo "Config: $APP_DIR/.env"
echo "Logs:   /var/log/opus-bot.log"
echo ""
