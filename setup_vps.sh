#!/bin/bash

# Automation script for Telegram Bot VPS Setup
# This script handles environment setup and systemd service creation

echo "🚀 Starting VPS Setup..."

# 1. Detect Username and Path
USER_NAME=$(whoami)
BOT_PATH=$(pwd)

echo "👤 User detected: $USER_NAME"
echo "📂 Path detected: $BOT_PATH"

# 2. Update and Install System Dependencies
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y

# 3. Setup Virtual Environment
echo "🐍 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Requirements
echo "📥 Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "❌ requirements.txt not found!"
    exit 1
fi

# 5. Prepare .env
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from template..."
    cp env.example .env
    echo "⚠️  Please edit your .env file after this script finishes!"
fi

# 6. Create Systemd Service
echo "⚙️  Creating systemd service..."
SERVICE_FILE="/etc/systemd/system/tgbot.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Telegram Message Bot Manager
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$BOT_PATH
ExecStart=$BOT_PATH/venv/bin/python3 $BOT_PATH/bot_manager.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable and Start Service
echo "🔄 Reloading systemd and enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable tgbot

echo ""
echo "✅ Setup Complete!"
echo "----------------------------------------------------"
echo "1. Run 'nano .env' to fill in your credentials."
echo "2. Run 'sudo systemctl start tgbot' to start the bot."
echo "3. Run 'journalctl -u tgbot -f' to check logs."
echo "----------------------------------------------------"
