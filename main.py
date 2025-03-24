# main.py

from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetParticipants
from telethon.tl.types import ChannelParticipantsSearch
from config import API_ID, API_HASH, PHONE_NUMBER
import asyncio
import logging
from datetime import datetime
import os
import getpass

# Ensure logs directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tagging_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize the Telegram client
client = TelegramClient('session_name', API_ID, API_HASH)

# Global variables
tagging_active = False
skip_bots = True  # Set to False if you want to tag bots
skip_admins = False  # Set to True if you want to skip admins
skip_users = []  # Add user IDs or usernames to skip (e.g., [123456789, 'username'])

async def main():
    # Start the client
    await client.start(
        phone=PHONE_NUMBER,
        code_callback=lambda: input('Enter the OTP sent to your Telegram app: '),
        password=lambda: getpass.getpass('Enter your Two-Step Verification password: ')
    )
    logger.info("Client created and connected!")

@client.on(events.NewMessage(pattern='/utag'))
async def tag_all(event):
    global tagging_active

    # Check if the command is used in a group
    if not event.is_group:
        await event.reply("This command can only be used in a group.")
        return

    # Extract the message to tag with
    message = event.message.message[len('/utag '):].strip()
    if not message:
        await event.reply("Please provide a message to tag with. Example: `/utag GOOD MORNING`")
        return

    # Start tagging process
    tagging_active = True
    await event.reply("Starting tagging process...")

    # Get all participants in the group
    all_participants = await client(GetParticipants(
        event.chat_id, ChannelParticipantsSearch(''), offset=0, limit=1000, hash=0
    ))

    # Tag each participant
    for user in all_participants.users:
        if not tagging_active:
            break  # Stop tagging if canceled

        # Skip bots if enabled
        if skip_bots and user.bot:
            logger.info(f"Skipping bot: {user.username or user.first_name}")
            continue

        # Skip admins if enabled
        if skip_admins and user.admin:
            logger.info(f"Skipping admin: {user.username or user.first_name}")
            continue

        # Skip specific users
        if user.id in skip_users or (user.username and user.username in skip_users):
            logger.info(f"Skipping user: {user.username or user.first_name}")
            continue

        # Tag the user
        if user.username:
            tag = f"@{user.username}"
        else:
            tag = f"[{user.first_name}](tg://user?id={user.id})"

        try:
            await event.respond(f"{tag} {message}")
            logger.info(f"Tagged: {user.username or user.first_name}")
        except Exception as e:
            logger.error(f"Failed to tag {user.username or user.first_name}: {e}")

        # Add a 2-second delay to avoid rate limits
        await asyncio.sleep(2)

    if tagging_active:
        await event.reply("Tagging process completed!")
    else:
        await event.reply("Tagging process canceled.")

@client.on(events.NewMessage(pattern='/cancel_tag'))
async def cancel_tag(event):
    global tagging_active
    tagging_active = False
    await event.reply("Tagging process canceled.")

# Run the client
with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
