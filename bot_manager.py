import os
import asyncio
import yaml
import io
import qrcode
import re
from datetime import datetime
from telethon import TelegramClient, events, Button
from dotenv import load_dotenv
from telegram_sender import TelegramSender

# Load environment variables
load_dotenv()

# Load environment variables
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    print("Error: Missing required environment variables (API_ID, API_HASH, BOT_TOKEN, ADMIN_ID)")
    exit(1)

# Create the bot client
bot = TelegramClient('bot_session', int(API_ID), API_HASH)

# Main menu buttons
MAIN_MENU = [
    [Button.text("📋 List Messages", resize=True), Button.text("➕ Add Message", resize=True)],
    [Button.text("❌ Remove Message", resize=True), Button.text("🔍 Find ID", resize=True)],
    [Button.text("🚀 Send Now", resize=True), Button.text("🔑 Auth", resize=True)]
]

def admin_only(func):
    async def wrapper(event):
        if event.sender_id != ADMIN_ID:
            await event.respond("⛔ Access Denied.")
            return
        return await func(event)
    return wrapper

@bot.on(events.NewMessage(pattern='/start'))
@admin_only
async def start_handler(event):
    await event.respond("Welcome to **Bot Manager**!", buttons=MAIN_MENU)
    raise events.StopPropagation

CONFIG_PATH = 'messages.yaml'
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def normalize_time_str(time_str):
    """Accept H:MM or HH:MM and normalize to HH:MM."""
    if not time_str:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", time_str.strip())
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return f"{hour:02d}:{minute:02d}"


def get_weekly_days(schedule):
    """Backward compatible reader for weekly schedule days."""
    if not schedule or schedule.get('type') != 'weekly':
        return []

    days = schedule.get('days')
    if isinstance(days, list):
        return [d for d in days if d in DAYS_OF_WEEK]

    day = schedule.get('day')
    if isinstance(day, str) and day in DAYS_OF_WEEK:
        return [day]

    return []


def build_days_selection_buttons():
    return [
        [Button.text(d, resize=True) for d in DAYS_OF_WEEK[:4]],
        [Button.text(d, resize=True) for d in DAYS_OF_WEEK[4:]],
        [Button.text("✅ Done", resize=True)]
    ]

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {'messages': {}}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if not config or 'messages' not in config:
        return {'messages': {}}
    return config

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

@bot.on(events.NewMessage(pattern=r'/list_message|📋 List Messages'))
@admin_only
async def list_message_handler(event):
    config = load_config()
    messages = config.get('messages', {})
    
    if not messages:
        await event.respond("No messages configured.", buttons=MAIN_MENU)
        raise events.StopPropagation
    
    response = "**Configured Messages:**\n\n"
    for msg_id, data in messages.items():
        text = data.get('text', '(No text)')
        # Truncate text if too long
        display_text = (text[:100] + '...') if len(text) > 100 else text
        recipients = ", ".join(data.get('recipients', []))
        images_count = len(data.get('image_paths', []))
        schedule = data.get('schedule')
        
        sched_text = "🚫 Manual"
        if schedule:
            if schedule['type'] == 'daily':
                sched_text = f"⏰ Daily at {schedule['time']}"
            elif schedule['type'] == 'weekly':
                weekly_days = get_weekly_days(schedule)
                days_str = ", ".join(weekly_days) if weekly_days else "(no days selected)"
                sched_text = f"📅 {days_str} at {schedule['time']}"
        
        response += f"🆔 **{msg_id}**\n"
        response += f"📝 {display_text}\n"
        response += f"👥 Recipients: {recipients}\n"
        response += f"🖼 Images: {images_count} | 🕒 {sched_text}\n"
        response += f"{'-' * 20}\n"
    
    await event.respond(response, buttons=MAIN_MENU)
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern=r'/remove_message|❌ Remove Message'))
@admin_only
async def remove_message_handler(event):
    config = load_config()
    messages = config.get('messages', {})
    
    if not messages:
        await event.respond("No messages to remove.", buttons=MAIN_MENU)
        raise events.StopPropagation
    
    # Create a summary of messages
    summary = "**Select a message to remove:**\n\n"
    for msg_id, data in messages.items():
        text = data.get('text') or data.get('message', '(No text)')
        display_text = (text[:50] + '...') if len(text) > 50 else text
        summary += f"🆔 **{msg_id}**: {display_text}\n"

    buttons = [[Button.inline("❌ Remove ALL", data="rm_all")]]
    row = []
    for msg_id in messages.keys():
        row.append(Button.inline(f"❌ {msg_id}", data=f"rm_{msg_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    await event.respond(summary, buttons=buttons)
    raise events.StopPropagation

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b'rm_')))
@admin_only
async def callback_remove_handler(event):
    data_str = event.data.decode()
    msg_id = data_str.split('_', 1)[1]
    
    config = load_config()
    messages = config.get('messages', {})
    
    if msg_id == "all":
        # Remove everything
        total_deleted_files = 0
        for m_id, m_data in messages.items():
            image_paths = m_data.get('image_paths', [])
            for path in image_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        total_deleted_files += 1
                    except:
                        pass
        
        config['messages'] = {}
        save_config(config)
        
        status = "✅ All messages and media files removed."
        if total_deleted_files > 0:
            status += f"\n🗑 Deleted {total_deleted_files} media file(s)."
        await event.edit(status)
        return

    if msg_id in messages:
        # Get image paths and delete files
        data = messages[msg_id]
        image_paths = data.get('image_paths', [])
        deleted_files = 0
        for path in image_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted_files += 1
                except Exception as e:
                    print(f"Error deleting file {path}: {e}")

        del config['messages'][msg_id]
        save_config(config)
        
        status_text = f"✅ Message **{msg_id}** removed successfully."
        if deleted_files > 0:
            status_text += f"\n🗑 Deleted {deleted_files} media file(s)."
            
        await event.edit(status_text)
    else:
        await event.edit(f"❌ Message **{msg_id}** not found.")

user_states = {}

class State:
    IDLE = 0
    WAITING_TEXT = 1
    WAITING_IMAGES = 2
    WAITING_RECIPIENTS = 3
    WAITING_AUTH_CODE = 4
    WAITING_AUTH_PASSWORD = 5
    WAITING_SCHEDULE_TYPE = 6
    WAITING_SCHEDULE_TIME = 7
    WAITING_SCHEDULE_DAY = 8

@bot.on(events.NewMessage(pattern=r'/auth|🔑 Auth'))
@admin_only
async def auth_handler(event):
    PHONE_NUMBER = os.getenv('PHONE_NUMBER')
    if not PHONE_NUMBER:
        await event.respond("❌ PHONE_NUMBER not found in .env")
        raise events.StopPropagation

    user_client = TelegramClient('session', int(API_ID), API_HASH, device_model="Windows 11", system_version="10.0.22621", app_version="4.11.2")
    await user_client.connect()
    
    if await user_client.is_user_authorized():
        me = await user_client.get_me()
        await event.respond(f"✅ Already authenticated as {me.first_name} (@{me.username})", buttons=MAIN_MENU)
        await user_client.disconnect()
        raise events.StopPropagation

    try:
        # 1) Primary auth flow: QR login
        from telethon.errors import SessionPasswordNeededError

        await event.respond(
            "🔐 **Primary login method: QR**\n\n"
            "1) Open Telegram on your phone\n"
            "2) Settings → Devices → Link Desktop Device\n"
            "3) Scan the QR code I send below\n\n"
            "ℹ️ QR is auto-refreshed every ~25 seconds to avoid 'invalid QR code'.",
            buttons=Button.clear()
        )

        qr_authorized = False
        for attempt in range(1, 6):
            qr_login = await user_client.qr_login()

            qr_builder = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=14,
                border=4,
            )
            qr_builder.add_data(qr_login.url)
            qr_builder.make(fit=True)
            qr_image = qr_builder.make_image(fill_color="black", back_color="white")

            qr_buffer = io.BytesIO()
            qr_image.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            qr_buffer.name = f'telegram_qr_login_{attempt}.png'

            await event.respond(
                f"📷 QR attempt {attempt}/5 (valid for a short time). Scan now:",
                file=qr_buffer,
                force_document=True
            )

            try:
                await qr_login.wait(timeout=25)
                qr_authorized = True
                break
            except asyncio.TimeoutError:
                continue

        if qr_authorized:
            me = await user_client.get_me()
            await event.respond(f"✅ Successfully authenticated via QR as {me.first_name}!", buttons=MAIN_MENU)
            await user_client.disconnect()
            raise events.StopPropagation

        await event.respond("⌛ QR login was not completed in time. Switching to fallback code authentication...")

        # 2) Fallback flow: app/SMS/call code
        sent_code = await user_client.send_code_request(PHONE_NUMBER)

        from telethon.tl.types import auth
        delivery_type = "Unknown"
        if isinstance(sent_code.type, auth.SentCodeTypeApp):
            delivery_type = "Telegram App (official application)"
        elif isinstance(sent_code.type, auth.SentCodeTypeSms):
            delivery_type = "SMS"
        elif isinstance(sent_code.type, auth.SentCodeTypeCall):
            delivery_type = "Phone Call"
        elif isinstance(sent_code.type, auth.SentCodeTypeFlashCall):
            delivery_type = "Flash Call"
        elif isinstance(sent_code.type, auth.SentCodeTypeMissedCall):
            delivery_type = "Missed Call"

        user_states[event.sender_id] = {
            'state': State.WAITING_AUTH_CODE,
            'client': user_client,
            'phone': PHONE_NUMBER
        }
        await event.respond(
            f"📩 Verification code sent via **{delivery_type}**!\n\n"
            f"📍 Please check your {delivery_type}.\n\n"
            "⚠️ **IMPORTANT**: To bypass Telegram's security, please enter the code **WITH SPACES** between digits.\n"
            "Example: `1 2 3 4 5`",
            buttons=Button.clear()
        )
    except events.StopPropagation:
        raise
    except Exception as e:
        await event.respond(f"❌ Error: {str(e)}", buttons=MAIN_MENU)
        await user_client.disconnect()
    
    raise events.StopPropagation

@bot.on(events.NewMessage(pattern=r'/add_message|➕ Add Message'))
@admin_only
async def add_message_handler(event):
    user_states[event.sender_id] = {
        'state': State.WAITING_TEXT,
        'data': {'text': '', 'image_paths': [], 'recipients': [], 'schedule': None}
    }
    await event.respond("Step 1: Send me the **text** for the message.", buttons=Button.clear())
    raise events.StopPropagation

@bot.on(events.NewMessage())
@admin_only
async def conversation_handler(event):
    # Ignore commands or menu button text if NOT in a state
    if event.text.startswith('/') or event.text in ["📋 List Messages", "➕ Add Message", "❌ Remove Message", "🔍 Find ID", "❓ Help"]:
        if event.sender_id not in user_states:
            return

    user_id = event.sender_id
    if user_id not in user_states:
        return

    state_data = user_states[user_id]
    current_state = state_data['state']

    # --- Authorization Flow ---
    if current_state == State.WAITING_AUTH_CODE:
        # Clean the code: remove spaces and non-digit characters
        raw_code = event.text.strip()
        code = ''.join(filter(str.isdigit, raw_code))
        
        # Try to delete the message containing the code for security
        try:
            await event.delete()
        except:
            pass
            
        client = state_data['client']
        phone = state_data['phone']
        try:
            from telethon.errors import SessionPasswordNeededError
            await client.sign_in(phone, code)
            me = await client.get_me()
            await event.respond(f"✅ Successfully authenticated as {me.first_name}!", buttons=MAIN_MENU)
            await client.disconnect()
            del user_states[user_id]
        except SessionPasswordNeededError:
            state_data['state'] = State.WAITING_AUTH_PASSWORD
            await event.respond("🔐 2FA Password needed. Please enter your password:")
        except Exception as e:
            error_msg = str(e)
            if "previously shared" in error_msg or "expired" in error_msg:
                await event.respond("❌ Telegram blocked the login because the code was entered in a chat. \n\n**Tip:** Try to run `python3 setup_auth.py` in the server console once to establish the session.", buttons=MAIN_MENU)
            else:
                await event.respond(f"❌ Error: {error_msg}. Starting over...", buttons=MAIN_MENU)
            await client.disconnect()
            del user_states[user_id]
        return

    elif current_state == State.WAITING_AUTH_PASSWORD:
        password = event.text.strip()
        client = state_data['client']
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            await event.respond(f"✅ Successfully authenticated as {me.first_name}!", buttons=MAIN_MENU)
            await client.disconnect()
            del user_states[user_id]
        except Exception as e:
            error_msg = str(e)
            if "previously shared" in error_msg or "expired" in error_msg:
                await event.respond("❌ Telegram blocked the login because the code was entered in a chat. \n\n**Tip:** Try to run `python3 setup_auth.py` in the server console once to establish the session.", buttons=MAIN_MENU)
            else:
                await event.respond(f"❌ Error: {error_msg}. Starting over...", buttons=MAIN_MENU)
            await client.disconnect()
            del user_states[user_id]
        return

    # --- Add Message Flow ---
    if current_state == State.WAITING_TEXT:
        state_data['data']['text'] = event.text
        state_data['state'] = State.WAITING_IMAGES
        await event.respond(
            "Step 2: Send me one or more **images**, or click 'Skip' if you don't want any images.",
            buttons=[Button.inline("Skip / Done", data="skip_images")]
        )

    elif current_state == State.WAITING_IMAGES:
        if event.media:
            # Generate a stable filename based on message ID and sender
            ext = '.jpg' # default
            if hasattr(event.media, 'document') and event.media.document:
                from telethon.utils import get_extension
                ext = get_extension(event.media.document)
            elif hasattr(event.media, 'photo') and event.media.photo:
                ext = '.jpg'
            
            filename = f"media/{event.sender_id}_{event.id}{ext}"
            path = await event.download_media(file=filename)
            
            if path:
                state_data['data']['image_paths'].append(os.path.abspath(path))
                
                # If it's part of an album, wait a bit to group responses
                if event.grouped_id:
                    if 'group_count' not in state_data:
                        state_data['group_count'] = 0
                    state_data['group_count'] += 1
                    
                    await asyncio.sleep(1) # Wait for other images in album
                    state_data['group_count'] -= 1
                    
                    if state_data['group_count'] > 0:
                        return # Still processing other images
                
                count = len(state_data['data']['image_paths'])
                await event.respond(
                    f"✅ {count} media saved! You can send more files or click 'Done'.",
                    buttons=[Button.inline("Done", data="skip_images")]
                )
            else:
                await event.respond("Failed to download media. Try again or 'Skip'.",
                                   buttons=[Button.inline("Skip / Done", data="skip_images")])
        else:
            await event.respond("Please send an image/file or click 'Done' to proceed to recipients.", 
                               buttons=[Button.inline("Done", data="skip_images")])

    elif current_state == State.WAITING_RECIPIENTS:
        recipients = [r.strip() for r in event.text.split(',') if r.strip()]
        state_data['data']['recipients'] = recipients
        state_data['state'] = State.WAITING_SCHEDULE_TYPE
        
        buttons = [
            [Button.inline("⏰ Daily", data="sched_daily"), Button.inline("📅 Weekly", data="sched_weekly")],
            [Button.inline("🚫 No Schedule (Manual)", data="sched_none")]
        ]
        await event.respond("Step 4: Choose a **schedule** for this message:", buttons=buttons)

    elif current_state == State.WAITING_SCHEDULE_TIME:
        normalized_time = normalize_time_str(event.text)
        if normalized_time:
            state_data['data']['schedule']['time'] = normalized_time
            
            if state_data['data']['schedule']['type'] == 'weekly':
                state_data['state'] = State.WAITING_SCHEDULE_DAY
                await event.respond(
                    "Step 5: Choose one or more **days of the week**.\n"
                    "Tap day buttons to add them, then press **✅ Done**.",
                    buttons=build_days_selection_buttons()
                )
            else:
                await finalize_add_message(event, user_id, state_data)
        else:
            await event.respond("❌ Invalid time format. Please use **H:MM** or **HH:MM** (e.g., `9:00` or `09:00`):")

    elif current_state == State.WAITING_SCHEDULE_DAY:
        selected_day = event.text.strip()
        if selected_day == "✅ Done":
            selected_days = state_data['data']['schedule'].get('days', [])
            if not selected_days:
                await event.respond(
                    "❌ Please select at least one day before finishing.",
                    buttons=build_days_selection_buttons()
                )
                return
            await finalize_add_message(event, user_id, state_data)
            return

        if selected_day in DAYS_OF_WEEK:
            existing_days = state_data['data']['schedule'].get('days', [])
            if selected_day not in existing_days:
                existing_days.append(selected_day)
                state_data['data']['schedule']['days'] = existing_days
                await event.respond(
                    f"✅ Added: **{selected_day}**\n"
                    f"Current: {', '.join(existing_days)}\n\n"
                    "Add more days or press **✅ Done**.",
                    buttons=build_days_selection_buttons()
                )
            else:
                await event.respond(
                    f"ℹ️ **{selected_day}** is already selected.\n"
                    f"Current: {', '.join(existing_days)}\n\n"
                    "Add more days or press **✅ Done**.",
                    buttons=build_days_selection_buttons()
                )
        else:
            await event.respond(
                "❌ Please use day buttons and then press **✅ Done**.",
                buttons=build_days_selection_buttons()
            )

async def finalize_add_message(event, user_id, state_data):
    config = load_config()
    # Generate a new ID
    existing_ids = list(config['messages'].keys())
    new_id = f"MESSAGE_{len(existing_ids) + 1}"
    while new_id in existing_ids:
        new_id = f"MESSAGE_{int(new_id.split('_')[1]) + 1}"
        
    config['messages'][new_id] = state_data['data']
    save_config(config)
    
    del user_states[user_id]
    await event.respond(f"✅ Successfully added message **{new_id}**!", buttons=MAIN_MENU)

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b'sched_')))
@admin_only
async def schedule_type_handler(event):
    user_id = event.sender_id
    if user_id not in user_states or user_states[user_id]['state'] != State.WAITING_SCHEDULE_TYPE:
        await event.answer("Operation not valid anymore.")
        return

    data = event.data.decode()
    if data == "sched_none":
        user_states[user_id]['data']['schedule'] = None
        await finalize_add_message(event, user_id, user_states[user_id])
    elif data == "sched_daily":
        user_states[user_id]['data']['schedule'] = {'type': 'daily', 'time': ''}
        user_states[user_id]['state'] = State.WAITING_SCHEDULE_TIME
        await event.edit("Step 5: Send me the **time** for daily post (format **H:MM** or **HH:MM**, e.g., 9:00 or 09:00):")
    elif data == "sched_weekly":
        user_states[user_id]['data']['schedule'] = {'type': 'weekly', 'time': '', 'days': []}
        user_states[user_id]['state'] = State.WAITING_SCHEDULE_TIME
        await event.edit("Step 5: Send me the **time** for weekly post (format **H:MM** or **HH:MM**, e.g., 9:00 or 18:00):")

@bot.on(events.CallbackQuery(data="skip_images"))
@admin_only
async def skip_images_handler(event):
    user_id = event.sender_id
    if user_id in user_states and user_states[user_id]['state'] == State.WAITING_IMAGES:
        user_states[user_id]['state'] = State.WAITING_RECIPIENTS
        await event.edit("Step 3: Send me the **recipients** (comma-separated IDs or usernames).")
    else:
        await event.answer("Operation not valid anymore.")


@bot.on(events.NewMessage(pattern=r'/find_group_id|🔍 Find ID'))
@admin_only
async def find_group_id_handler(event):
    await event.respond("🔍 Finding your groups, channels, and chats... Please wait.")
    
    user_client = TelegramClient('session', int(API_ID), API_HASH)
    try:
        await user_client.connect()
        if not await user_client.is_user_authorized():
            await event.respond("❌ User session is not authorized. Please run `python setup_auth.py` on the server.")
            return

        # Get all dialogs without limit
        dialogs = await user_client.get_dialogs(limit=None)
        
        response = "**📊 Your Groups:**\n\n"
        
        for dialog in dialogs:
            entity = dialog.entity
            # Use dialog.id, it's already signed (-100... for supergroups/channels)
            signed_id = dialog.id
            
            # Filter: must be a group (negative ID) and NOT a broadcast channel
            is_group = False
            if signed_id < 0:
                if not getattr(entity, 'broadcast', False):
                    is_group = True
            
            if is_group:
                title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                display_id = str(signed_id).replace('-', '')
                line = f"• **{title}**\n  ID: `{display_id}`\n"
                
                # Check for topics if it's a forum
                if hasattr(entity, 'forum') and entity.forum:
                    line += "  📌 _Has Topics (Forum mode)_\n"
                    try:
                        # Try both possible locations for GetForumTopicsRequest
                        try:
                            from telethon.tl.functions.channels import GetForumTopicsRequest
                        except ImportError:
                            from telethon.tl.functions.messages import GetForumTopicsRequest
                            
                        result = await user_client(GetForumTopicsRequest(
                            channel=entity,
                            offset_date=0,
                            offset_id=0,
                            offset_topic=0,
                            limit=10
                        ))
                        for topic in result.topics:
                            topic_id = topic.id
                            topic_title = getattr(topic, 'title', f'Topic {topic_id}')
                            line += f"    • {topic_title}: `{display_id}:{topic_id}`\n"
                    except Exception as e:
                        line += f"    (Could not fetch topics: {str(e)})\n"
                
                response += line + "\n"
                
                # Telegram has message length limits
                if len(response) > 3500:
                    await event.respond(response)
                    response = ""

        if response:
            await event.respond(response)
        
        await event.respond("✅ Done! Use these IDs in `/add_message`.", buttons=MAIN_MENU)
        raise events.StopPropagation
        
    except Exception as e:
        if str(e):
            await event.respond(f"❌ Error: {str(e)}", buttons=MAIN_MENU)
    finally:
        await user_client.disconnect()

@bot.on(events.NewMessage(pattern=r'/send_now|🚀 Send Now'))
@admin_only
async def send_now_handler(event):
    config = load_config()
    messages = config.get('messages', {})
    
    if not messages:
        await event.respond("No messages configured.", buttons=MAIN_MENU)
        raise events.StopPropagation
    
    buttons = [[Button.inline("🚀 Send ALL", data="send_all")]]
    row = []
    for msg_id in messages.keys():
        row.append(Button.inline(f"🚀 {msg_id}", data=f"send_{msg_id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    await event.respond("Select a message to send now:", buttons=buttons)
    raise events.StopPropagation

@bot.on(events.CallbackQuery(data=lambda d: d.startswith(b'send_')))
@admin_only
async def callback_send_handler(event):
    data = event.data.decode()
    msg_id = data.split('_', 1)[1]
    
    config = load_config()
    messages = config.get('messages', {})
    
    target_config = None
    if msg_id != "all":
        target_config = messages.get(msg_id)
        if not target_config:
            await event.edit(f"❌ Message **{msg_id}** not found.")
            return

    status_msg = await event.edit(f"🚀 Starting delivery for: {'ALL' if msg_id == 'all' else msg_id}...")
    
    logs = []
    async def log_to_chat(text):
        logs.append(text)
        if len(logs) % 3 == 0 or "=" in text or "Total" in text:
            full_log = "\n".join(logs[-10:])
            try:
                await status_msg.edit(f"🚀 Delivery in progress ({msg_id})...\n\n```{full_log}```")
            except:
                pass

    try:
        sender = TelegramSender(log_func=log_to_chat)
        await sender.client.connect()
        if not await sender.client.is_user_authorized():
            await event.respond("❌ User session not authorized. Use **🔑 Auth** button.")
            await sender.client.disconnect()
            return

        await sender.send_messages(specific_config=target_config)
        await sender.client.disconnect()
        
        final_log = "\n".join(logs)
        if len(final_log) > 3000:
            await event.respond(f"✅ Delivery finished for {msg_id}. Full log:")
            for i in range(0, len(final_log), 3000):
                await event.respond(f"```{final_log[i:i+3000]}```")
        else:
            await status_msg.edit(f"✅ Delivery finished for **{msg_id}**!\n\n```{final_log}```")
            
    except Exception as e:
        await event.respond(f"❌ Error during delivery: {str(e)}")
    
    raise events.StopPropagation

async def scheduler_loop():
    print("Scheduler started...")
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_day = now.strftime("%A")
            
            config = load_config()
            messages = config.get('messages', {})
            
            for msg_id, data in messages.items():
                schedule = data.get('schedule')
                if not schedule:
                    continue
                
                should_send = False
                if schedule['type'] == 'daily' and schedule['time'] == current_time:
                    should_send = True
                elif schedule['type'] == 'weekly' and schedule['time'] == current_time:
                    weekly_days = get_weekly_days(schedule)
                    if current_day in weekly_days:
                        should_send = True
                
                if should_send:
                    print(f"⏰ Scheduler: Sending {msg_id}...")
                    # Small delay to avoid double sending in the same minute if processing is too fast
                    # although the loop waits 60s at the end
                    
                    try:
                        # We use a helper function to send so we can log to admin
                        await run_scheduled_task(msg_id, data)
                    except Exception as e:
                        print(f"❌ Scheduler error sending {msg_id}: {e}")
                        await bot.send_message(ADMIN_ID, f"❌ **Scheduled Post Failed**: {msg_id}\nError: {e}")
            
            # Wait for the next minute start
            await asyncio.sleep(60)
        except Exception as e:
            print(f"❌ Scheduler loop error: {e}")
            await asyncio.sleep(60)

async def run_scheduled_task(msg_id, data):
    logs = []
    def logger(text):
        print(f"[{msg_id}] {text}")
        logs.append(text)

    sender = TelegramSender(log_func=logger)
    await sender.client.connect()
    
    if await sender.client.is_user_authorized():
        # Double check it's a user session
        me = await sender.client.get_me()
        if getattr(me, 'bot', False):
            await bot.send_message(ADMIN_ID, f"⚠ **WARNING**: Scheduler is using a BOT account (@{me.username}) instead of user!")
        
        await sender.send_messages(specific_config=data)
        await sender.client.disconnect()
        
        # Notify admin with log summary
        log_summary = "\n".join(logs[-5:]) # Last 5 lines
        await bot.send_message(ADMIN_ID, f"⏰ **Scheduled Post Sent**: {msg_id}\n\n```{log_summary}```")
    else:
        await bot.send_message(ADMIN_ID, f"❌ **Scheduled Post Failed**: {msg_id}\nUser session not authorized! Please re-auth.")
        await sender.client.disconnect()

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("Bot Manager started...")
    # Start scheduler in background
    asyncio.create_task(scheduler_loop())
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
