# Deployment Guide (Google Cloud Platform)

This guide explains how to deploy your Telegram Bot to a free Google Cloud Platform (GCP) Virtual Private Server (VPS).

## 1. Create a Free VPS on GCP

1.  Go to [Google Cloud Console](https://console.cloud.google.com/).
2.  **Create a Project**: Click the project selection dropdown at the top and click **New Project**.
3.  **Enable Compute Engine API**: Go to the [API Activation page](https://console.cloud.google.com/marketplace/product/google/compute.googleapis.com) and click **Enable**.
4.  **Create VM Instance**: Go to the [Create Instance page](https://console.cloud.google.com/compute/instancesAdd).
5.  **Machine configuration**:
    - **Region**: Choose `us-west1` (Oregon), `us-central1` (Iowa), or `us-east1` (South Carolina).
    - **Machine type**: Select `e2-micro` (This is part of the Free Tier).
6.  **OS and Storage**:
    - Click **Change**.
    - **Operating System**: Select `Ubuntu`.
    - **Version**: Select `Ubuntu 22.04 LTS` (x86/64).
    - **Boot disk type**: Select **Standard persistent disk** (up to 30 GB is free).
    - Click **Select**.
8.  **Data protection**:
    - Set to **No backups**.
9.  **Observability**:
    - **Uncheck** "Install Ops Agent for Monitoring and Logging".
10. Click **Create**.
11. Once created, click the **SSH** button next to your instance to open the terminal.

## 2. Clone the Repository

In the SSH terminal, run the following commands to install git, nano and get the code (this will skip interactive restart prompts):

```bash
sudo DEBIAN_FRONTEND=noninteractive apt update && sudo DEBIAN_FRONTEND=noninteractive apt install git nano -y
git clone https://github.com/Ealcmhar/tg_sheduled_msg_bot
cd tg_sheduled_msg_bot
```

## 3. Preparation (Collect your data)

Before starting the setup, make sure you have:
- **API_ID** and **API_HASH**: From [my.telegram.org](https://my.telegram.org/apps).
- **PHONE_NUMBER**: Your account number (international format, e.g., +1234567890).
- **BOT_TOKEN**: From [@BotFather](https://t.me/BotFather).
- **ADMIN_ID**: Your Telegram ID (get it from [@userinfobot](https://t.me/userinfobot)).

### How to use the editor (nano)
When asked to edit a file, follow these steps:
1.  Run `nano <filename>` (e.g., `nano env.example`).
2.  Use arrow keys to move the cursor.
3.  Type or paste your information.
4.  **Save and Exit**: Press `Ctrl+O`, then `Enter` (to save), then `Ctrl+X` (to exit).

---

## 4. Automated Setup (Recommended)

Once you've cloned the repository and entered the directory, simply run:

```bash
chmod +x setup_vps.sh
./setup_vps.sh
```

This script will:
- Install Python and required system packages.
- Create a virtual environment and install project dependencies.
- Create a `.env` file from the template.
- **Automatically create and enable a systemd service** with correct paths and your current username.

After the script finishes, just edit your `.env` and start the service:
```bash
nano .env
sudo systemctl start tgbot
```

---

## 5. Manual Setup (Alternative)

To ensure the bot runs 24/7 and restarts automatically after a server reboot or crash, create a systemd service.

1.  **Create the service file:**
    ```bash
    sudo nano /etc/systemd/system/tgbot.service
    ```

2.  **Paste the following configuration** (Replace `YOUR_USER` with your Linux username):
    ```ini
    [Unit]
    Description=Telegram Message Bot Manager
    After=network.target

    [Service]
    Type=simple
    User=YOUR_USER
    WorkingDirectory=/home/YOUR_USER/bot
    ExecStart=/home/YOUR_USER/bot/venv/bin/python3 /home/YOUR_USER/bot/bot_manager.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Start and Enable the service:**
    ```bash
    # Reload systemd
    sudo systemctl daemon-reload

    # Enable auto-start on boot
    sudo systemctl enable tgbot

    # Start the bot
    sudo systemctl start tgbot

    # Check status
    sudo systemctl status tgbot
    ```

## 6. Maintenance

- **View logs:** `journalctl -u tgbot -f`
- **Restart bot:** `sudo systemctl restart tgbot`
- **Stop bot:** `sudo systemctl stop tgbot`
- **Update code:**
    ```bash
    cd /home/YOUR_USER/bot
    git pull
    sudo systemctl restart tgbot
    ```
