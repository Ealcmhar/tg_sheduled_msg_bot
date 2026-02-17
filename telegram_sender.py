"""
Telegram message sender for daily posts to groups and users.
Uses Telethon to send messages from a user account.
Supports sending to groups, channels, and individual users.
Supports sending text messages and images.
"""
import os
import asyncio
import yaml
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class TelegramSender:
    def __init__(self, log_func=print):
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.phone_number = os.getenv('PHONE_NUMBER')
        self.log = log_func
        
        # Validate required environment variables
        if not all([self.api_id, self.api_hash, self.phone_number]):
            raise ValueError("Missing required environment variables: API_ID, API_HASH, PHONE_NUMBER")
        
        # Load messages configuration
        # Support both old format (single message) and new format (multiple messages)
        self.messages_config = self._load_messages_config()
        
        # Create client
        self.client = TelegramClient('session', int(self.api_id), self.api_hash)
    
    def _load_messages_config(self):
        """Load messages configuration from YAML file or environment variables"""
        configs = []
        
        # Try to load from YAML file first
        yaml_path = os.getenv('MESSAGES_YAML', 'messages.yaml')
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                    
                if yaml_config and 'messages' in yaml_config:
                    for msg_key, msg_config in yaml_config['messages'].items():
                        recipients = msg_config.get('recipients', [])
                        image_paths = msg_config.get('image_paths', [])
                        text = msg_config.get('text', '')
                        
                        # Convert recipients to list if it's a string
                        if isinstance(recipients, str):
                            recipients = [r.strip() for r in recipients.split(',') if r.strip()]
                        
                        # Convert image_paths to list if it's a string
                        if isinstance(image_paths, str):
                            image_paths = [p.strip() for p in image_paths.split(',') if p.strip()]
                        
                        if recipients or text:
                            configs.append({
                                'message': text,
                                'recipients': recipients,
                                'image_paths': image_paths
                            })
                    
                    if configs:
                        return configs
            except Exception as e:
                self.log(f"⚠ Warning: Could not load YAML config: {e}")
                self.log("   Falling back to environment variables")
        
        # Fallback to environment variables format
        # Check for new format: MESSAGE_1, RECIPIENTS_1, IMAGE_PATHS_1, etc.
        i = 1
        while True:
            message_key = f'MESSAGE_{i}'
            recipients_key = f'RECIPIENTS_{i}'
            image_paths_key = f'IMAGE_PATHS_{i}'
            
            message = os.getenv(message_key)
            recipients = os.getenv(recipients_key)
            image_paths_str = os.getenv(image_paths_key)
            
            # If no MESSAGE_X found, stop
            if not message and not recipients:
                break
            
            # Parse recipients
            if recipients:
                recipients_list = [r.strip() for r in recipients.split(',') if r.strip()]
            else:
                # Fallback to old format
                recipients_list = os.getenv('RECIPIENTS', os.getenv('GROUP_IDS', '')).split(',')
                recipients_list = [r.strip() for r in recipients_list if r.strip()]
            
            # Parse image paths
            if image_paths_str:
                image_paths = [path.strip() for path in image_paths_str.split(',') if path.strip()]
            else:
                image_paths = []
            
            if message or recipients_list:
                configs.append({
                    'message': message or '',
                    'recipients': recipients_list,
                    'image_paths': image_paths
                })
            
            i += 1
        
        # If no numbered messages found, use old format (backward compatibility)
        if not configs:
            recipients = os.getenv('RECIPIENTS', os.getenv('GROUP_IDS', ''))
            recipients_list = [r.strip() for r in recipients.split(',') if r.strip()] if recipients else []
            
            message = os.getenv('MESSAGE', 'Hello from automated daily message!')
            
            image_paths_str = os.getenv('IMAGE_PATHS', os.getenv('IMAGE_PATH', ''))
            if image_paths_str:
                image_paths = [path.strip() for path in image_paths_str.split(',') if path.strip()]
            else:
                image_paths = []
            
            if recipients_list or message:
                configs.append({
                    'message': message,
                    'recipients': recipients_list,
                    'image_paths': image_paths
                })
        
        return configs
    
    async def authenticate(self):
        """
        Authenticate with Telegram.
        
        This only prompts for verification code/password if not already authenticated.
        Once authenticated, the session file is saved and reused for future runs.
        You only need to authenticate ONCE (or if the session expires).
        """
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            self.log("Not authenticated. Starting authentication process...")
            await self.client.send_code_request(self.phone_number)
            try:
                code = input('Enter the code you received: ')
                await self.client.sign_in(self.phone_number, code)
            except SessionPasswordNeededError:
                password = input('Enter your 2FA password: ')
                await self.client.sign_in(password=password)
            self.log("✓ Successfully authenticated! Session saved for future use.")
        else:
            self.log("✓ Already authenticated (using saved session)")
    
    async def send_messages(self, specific_config=None):
        """
        Send messages. If specific_config is provided, only sends that one.
        Otherwise sends all from messages_config.
        """
        try:
            me = await self.client.get_me()
            self.log(f"👤 Sending as: {me.first_name} (@{me.username})")
        except Exception as e:
            self.log(f"⚠ Could not get sender info: {e}")

        configs_to_send = [specific_config] if specific_config else self.messages_config
        
        if not configs_to_send:
            self.log("No messages to send.")
            return
        
        total_sent = 0
        total_failed = 0
        
        if not specific_config:
            self.log(f"Found {len(self.messages_config)} message configuration(s)\n")
        
        for config_idx, config in enumerate(configs_to_send, 1):
            # Check both keys for compatibility
            message = config.get('message') or config.get('text', '')
            recipients = config.get('recipients', [])
            image_paths = config.get('image_paths', [])
            
            if not recipients:
                self.log(f"⚠ Message {config_idx}: No recipients configured, skipping")
                continue
            
            self.log(f"📨 Message {config_idx}: Sending to {len(recipients)} recipient(s)...")
            if image_paths:
                self.log(f"   Images: {len(image_paths)} file(s)")
            
            sent_count = 0
            failed_count = 0
            
            for recipient in recipients:
                recipient = recipient.strip()
                if not recipient:
                    continue
                
                try:
                    # Check if this is a topic format: group_id:topic_id
                    if ':' in recipient and not recipient.startswith('@'):
                        # Format: group_id:topic_id (e.g., -1001234567890:123)
                        parts = recipient.split(':', 1)
                        if len(parts) == 2:
                            group_id_str, topic_id_str = parts
                            try:
                                group_entity = await self.client.get_entity(int(group_id_str))
                                topic_id = int(topic_id_str)
                                
                                # Get a message from the topic to reply to
                                try:
                                    from telethon.tl.functions.channels import GetForumTopicsRequest
                                except ImportError:
                                    from telethon.tl.functions.messages import GetForumTopicsRequest
                                
                                result = await self.client(GetForumTopicsRequest(
                                    channel=group_entity,
                                    offset_date=0,
                                    offset_id=0,
                                    offset_topic=0,
                                    limit=100
                                ))
                                
                                # Find the topic
                                topic = None
                                for t in result.topics:
                                    if t.id == topic_id:
                                        topic = t
                                        break
                                
                                if topic and hasattr(topic, 'top_message') and topic.top_message:
                                    # Send message to the topic
                                    await self._send_message_with_images(
                                        group_entity,
                                        message,
                                        image_paths,
                                        reply_to=topic.top_message
                                    )
                                    self.log(f"✓ Message sent to topic {topic_id} in group {group_id_str}")
                                else:
                                    raise ValueError(f"Topic {topic_id} not found or has no messages")
                                
                                sent_count += 1
                                continue
                            except ValueError as ve:
                                # If parsing fails, treat as regular recipient
                                pass
                    
                    # Regular recipient (group, channel, or user)
                    # Try to parse as integer (for numeric IDs like group/channel IDs)
                    try:
                        recipient_int = int(recipient)
                        entity = await self.client.get_entity(recipient_int)
                    except ValueError:
                        # If not an integer, treat as username (groups, channels, or users)
                        # Examples: @mygroup, @channel, @username
                        entity = await self.client.get_entity(recipient)
                    
                    # Send message with images
                    await self._send_message_with_images(entity, message, image_paths)
                    self.log(f"✓ Message sent to {recipient}")
                    sent_count += 1
                    
                except Exception as e:
                    self.log(f"✗ Failed to send message to {recipient}: {str(e)}")
                    failed_count += 1
            
            self.log(f"   Summary: {sent_count} sent, {failed_count} failed\n")
            total_sent += sent_count
            total_failed += failed_count
        
        self.log(f"="*60)
        self.log(f"Total: {total_sent} sent, {total_failed} failed")
    
    async def _send_message_with_images(self, entity, message, image_paths, reply_to=None):
        """
        Send message with images. All images are sent in one message with text as caption.
        """
        # Filter valid image files
        valid_images = [img for img in image_paths if os.path.exists(img)]
        
        if valid_images:
            # Check for missing files
            for img_path in image_paths:
                if img_path not in valid_images:
                    self.log(f"⚠ Warning: Image file not found: {img_path}")
            
            # Send all images. If multiple, Telethon treats them as an album.
            # For albums, the caption is attached to the FIRST file.
            try:
                await self.client.send_file(
                    entity,
                    valid_images,
                    caption=message if message else None,
                    reply_to=reply_to
                )
            except Exception as e:
                # Fallback: if sending album with caption fails, try sending text separately
                self.log(f"⚠ Failed to send with caption, trying separate: {e}")
                await self.client.send_file(entity, valid_images, reply_to=reply_to)
                if message:
                    await self.client.send_message(entity, message)
        else:
            # No valid images, send text only
            if message:
                await self.client.send_message(
                    entity,
                    message,
                    reply_to=reply_to
                )
    
    async def run(self):
        """Main execution method"""
        try:
            await self.authenticate()
            await self.send_messages()
        finally:
            await self.client.disconnect()


async def main():
    """Entry point for the script"""
    sender = TelegramSender()
    await sender.run()


if __name__ == '__main__':
    asyncio.run(main())
