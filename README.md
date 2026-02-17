# Telegram Bot Manager & Message Sender

A comprehensive system for managing and automating Telegram message delivery. This project includes a **Bot Manager** for interactive configuration and a **Message Sender** that can post text and images to groups, channels, and users on a schedule.

## 🚀 Key Features

- **Interactive Bot Manager**: Manage your posts directly from Telegram with a simple button-driven interface.
- **Scheduled Posting**: Set up daily or weekly messages at specific times.
- **Media Support**: Send text messages with multiple images (as albums).
- **Smart Album Loading**: Group multiple photos into one confirmation message during upload.
- **Group Discovery**: Easily find IDs for groups, channels, and forum topics with built-in search.
- **Secure Authentication**: Built-in user session authorization with security bypass for chat-based login.
- **Automatic Cleanup**: Media files are automatically deleted from the disk when a message or the entire list is removed.
- **Improved File Naming**: Saved images use stable filenames based on message IDs, ignoring captions.

## 🛠 Setup & Installation

### 1. Requirements
- Python 3.10+
- A Telegram account and [API credentials](https://my.telegram.org/apps) (`API_ID`, `API_HASH`)
- A Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/Ealcmhar/tg_sheduled_msg_bot
cd tg_sheduled_msg_bot

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
1. Copy the example environment file:
   ```bash
   cp env.example .env
   ```
2. Fill in your credentials in the `.env` file:
   - `API_ID` & `API_HASH`: From my.telegram.org.
   - `PHONE_NUMBER`: Your account phone number.
   - `BOT_TOKEN`: From @BotFather.
   - `ADMIN_ID`: Your personal Telegram ID (use @userinfobot to find it).

## 🤖 Usage

### Running the Bot
```bash
python3 bot_manager.py
```

### Main Menu Commands
- **📋 List Messages**: View all configured messages, recipients, and schedules.
- **➕ Add Message**: Step-by-step flow to add text, photos, recipients, and schedule.
- **❌ Remove Message**: View message details and select specific ones or "Remove ALL" to clear the list and media folder.
- **🔍 Find ID**: Discover numeric IDs and topic IDs for your groups.
- **🚀 Send Now**: Choose a specific message or send all messages immediately.
- **🔑 Auth**: Start the user session authorization process.

### 🔑 User Authentication Tips
Telegram may block login attempts if codes are entered directly in a chat. 
1. Click **🔑 Auth** in the bot.
2. When prompted for the code, enter it **WITH SPACES** between digits (e.g., `1 2 3 4 5`).
3. If still blocked, run `python3 telegram_sender.py` once in your server console to establish the session manually.

## 📂 Project Structure
- `bot_manager.py`: Main entry point for the interactive management bot.
- `telegram_sender.py`: Core logic for message delivery using user sessions.
- `messages.yaml`: Local storage for message configurations and schedules.
- `media/`: Storage for images (auto-managed by the bot).

## 📄 License
MIT
