# main.py (Updated with Rate Limit Handling)

from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.errors import FloodWaitError
from config import API_ID, API_HASH, PHONE_NUMBER, OWNER_ID
import asyncio
import logging
import os
import getpass
import time

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tagging_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize client
client = TelegramClient('session_name', API_ID, API_HASH)

# Global variables
tagging_active = False
last_message_time = 0  # For rate limiting

async def main():
    await client.start(
        phone=PHONE_NUMBER,
        code_callback=lambda: input('Enter Telegram OTP: '),
        password=lambda: getpass.getpass('Enter 2FA password: ')
    )
    logger.info("Bot started successfully")

def should_skip_user(user):
    """Determine if user should be skipped"""
    if not hasattr(user, 'id'):
        return True
    if getattr(user, 'deleted', False):
        return True
    if getattr(user, 'bot', False):
        return True
    return False

async def safe_send_message(event, user, message):
    """Handle message sending with rate limits"""
    global last_message_time
    
    # Minimum delay between messages (in seconds)
    MIN_DELAY = 30  # Increased from 2 to 30 seconds
    
    # Calculate required delay
    current_time = time.time()
    elapsed = current_time - last_message_time
    wait_time = max(0, MIN_DELAY - elapsed)
    
    if wait_time > 0:
        logger.info(f"Waiting {wait_time:.1f}s to avoid rate limits")
        await asyncio.sleep(wait_time)
    
    try:
        if user.username:
            mention = f"@{user.username}"
        else:
            mention = f"[{user.first_name or 'User'}](tg://user?id={user.id})"
        
        await event.respond(f"{mention} {message}")
        last_message_time = time.time()
        return True
    except FloodWaitError as e:
        wait = e.seconds
        logger.warning(f"Flood wait required: {wait} seconds")
        await asyncio.sleep(wait)
        return await safe_send_message(event, user, message)
    except Exception as e:
        logger.error(f"Failed to tag {getattr(user, 'id', 'unknown')}: {str(e)}")
        return False

@client.on(events.NewMessage(pattern='/idtag'))
async def tag_all(event):
    global tagging_active

    # Owner verification
    if event.sender_id != OWNER_ID:
        await event.delete()
        reply = await event.reply("⚠️ Owner only command!")
        await asyncio.sleep(3)
        await reply.delete()
        return

    # Group check
    if not event.is_group:
        await event.reply("❌ Command works in groups only!")
        return

    # Extract message
    message = event.message.message[len('/idtag '):].strip()
    if not message:
        await event.reply("ℹ️ Usage: /idtag [your message]")
        return

    tagging_active = True
    status_msg = await event.reply("🔄 Starting smart tagging with rate limit protection...")
    stats = {'tagged': 0, 'skipped': 0, 'errors': 0}

    try:
        # Get participants in batches
        offset = 0
        limit = 100  # Reduced batch size
        while tagging_active:
            participants = await client(GetParticipantsRequest(
                event.chat_id, 
                ChannelParticipantsSearch(''), 
                offset, 
                limit, 
                hash=0
            ))
            
            if not participants.users:
                break

            # Process current batch
            for user in participants.users:
                if not tagging_active:
                    break

                if should_skip_user(user):
                    stats['skipped'] += 1
                    continue

                success = await safe_send_message(event, user, message)
                if success:
                    stats['tagged'] += 1
                else:
                    stats['errors'] += 1

            offset += len(participants.users)
            if offset % 300 == 0:  # Update status every 300 users
                await status_msg.edit(
                    f"🔄 Processing...\n"
                    f"• Tagged: {stats['tagged']}\n"
                    f"• Skipped: {stats['skipped']}\n"
                    f"• Errors: {stats['errors']}"
                )

        completion_msg = (
            f"✅ Tagging completed!\n"
            f"• Tagged: {stats['tagged']}\n"
            f"• Skipped: {stats['skipped']}\n"
            f"• Errors: {stats['errors']}"
        )
        await status_msg.edit(completion_msg)

    except Exception as e:
        logger.error(f"Tagging error: {str(e)}")
        await status_msg.edit(f"❌ Error: {str(e)}")
    finally:
        tagging_active = False

@client.on(events.NewMessage(pattern='/stoptag'))
async def stop_tagging(event):
    global tagging_active

    # Owner verification
    if event.sender_id != OWNER_ID:
        await event.delete()
        reply = await event.reply("⚠️ Only owner can stop tagging!")
        await asyncio.sleep(3)
        await reply.delete()
        return

    if tagging_active:
        tagging_active = False
        await event.reply("🛑 Stopped tagging process")
    else:
        await event.reply("ℹ️ No active tagging to stop")

# Run client
with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
