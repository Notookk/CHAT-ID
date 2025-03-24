# main.py

from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from config import API_ID, API_HASH, PHONE_NUMBER
import asyncio
import logging
from datetime import datetime
import os
import getpass
OWNER_ID = 7875192045
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

async def main():
    await client.start(
        phone=PHONE_NUMBER,
        code_callback=lambda: input('Enter Telegram OTP: '),
        password=lambda: getpass.getpass('Enter 2FA password: ')
    )
    logger.info("Bot started successfully")

def is_inactive_user(user):
    """Check if user is deleted or inactive"""
    if user.deleted:
        return True
    if isinstance(user.status, (UserStatusEmpty, UserStatusLastMonth, UserStatusLastWeek)):
        return True
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
    status_msg = await event.reply("🔄 Starting smart tagging (skipping bots/deleted/inactive)...")

    try:
        # Get participants in batches
        offset = 0
        limit = 200
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

                # Skip conditions
                if user.bot:
                    logger.info(f"Skipping bot: {user.id}")
                    continue
                if is_inactive_user(user):
                    logger.info(f"Skipping inactive/deleted: {user.id}")
                    continue
                if getattr(user, 'admin', False):
                    logger.info(f"Skipping admin: {user.id}")
                    continue

                # Create mention
                if user.username:
                    mention = f"@{user.username}"
                else:
                    mention = f"[{user.first_name or 'User'}](tg://user?id={user.id})"

                try:
                    await event.respond(f"{mention} {message}")
                    logger.info(f"Tagged active user: {user.id}")
                except Exception as e:
                    logger.error(f"Failed to tag {user.id}: {str(e)}")

                # 2-second delay between tags
                await asyncio.sleep(2)

            offset += len(participants.users)

        if tagging_active:
            await status_msg.edit("✅ Smart tagging completed!")
        else:
            await status_msg.edit("⏹ Tagging stopped by owner")

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
