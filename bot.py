import os
import discord
import logging
import aiohttp
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent
import shutil

PREFIX = "!"

# Setup logging
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = MistralAgent()

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")

# Store message history
message_history = {}

@bot.event
async def on_ready():
    logger.info(f"{bot.user} has connected to Discord!")

@bot.event
async def on_message(message: discord.Message):
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith(PREFIX):
        return

    # Add message to history
    if message.channel.id not in message_history:
        message_history[message.channel.id] = []
    message_history[message.channel.id].append(message.content)

    # Limit history to the last 10 messages for context
    if len(message_history[message.channel.id]) > 10:
        message_history[message.channel.id].pop(0)

    # Check for MP3 file attachment
    if message.attachments:
        for attachment in message.attachments:
            if not attachment.filename.endswith('.mp3'):
                await message.channel.send(f"Sorry, I can only process MP3 files. The file you uploaded is not an MP3.")
                return

            # Check file size (1 MB = 1,048,576 bytes)
            if attachment.size > 1_048_576:
                file_size_mb = attachment.size / 1_048_576
                await message.channel.send(f"Sorry, the file is too large to process. It is {file_size_mb:.2f} MB, which exceeds the 1 MB limit.")
                return

            # Download the MP3 file
            file_path = await download_file(attachment)
            await message.channel.send(f"MP3 file received and saved as {file_path}")

            # Add the file path to the message history for context
            message_history[message.channel.id].append(f"FILEPATH: {file_path}")

            # Process the message with the agent
            response = await agent.run_with_history(message, message_history[message.channel.id])
            await message.channel.send(response)
            return

    # Process the message with the agent
    response = await agent.run_with_history(message, message_history[message.channel.id])

    # Check for all required categories in the response
    required_categories = ["FILEPATH:", "SPECIFIC_TRACK:", "WANT_MIDI_FILE:", "WANT_MUSESCORE_FILE:", "WANT_SHEET_MUSIC_PDF:"]
    if all(category in response for category in required_categories):
        # Parse the response
        lines = response.split('\n')
        response_data = {}

        for line in lines:
            for category in required_categories:
                if line.startswith(category):
                    response_data[category] = line.split(": ")[1].strip()

        file_path = response_data["FILEPATH:"]
        specific_track = response_data["SPECIFIC_TRACK:"]
        want_midi = response_data["WANT_MIDI_FILE:"].lower() == "true"
        want_musescore = response_data["WANT_MUSESCORE_FILE:"].lower() == "true"
        want_pdf = response_data["WANT_SHEET_MUSIC_PDF:"].lower() == "true"

        # List to collect file paths to send
        files_to_send = []

        # Determine if separation is needed
        if specific_track != "original":
            loading_message = await message.channel.send("Separating audio... 🔄")
            separated_files = agent.separate_audio(file_path)
            track_file_path = separated_files.get(specific_track)
            await loading_message.edit(content="Audio separated! ✅")
            files_to_send.append(track_file_path)
        else:
            track_file_path = file_path

        # Convert to MIDI if needed
        if want_midi:
            loading_message = await message.channel.send("Converting to MIDI... 🎶")
            midi_file_path = agent.convert_to_midi(track_file_path)
            await loading_message.edit(content="MIDI conversion complete! ✅")
            files_to_send.append(midi_file_path)

        # Convert to MuseScore or PDF if needed
        if want_musescore or want_pdf:
            loading_message = await message.channel.send("Converting to Musescore... 🎼")
            musicxml_output_path, pdf_file_path = agent.convert_midi_to_musescore(midi_file_path)
            await loading_message.edit(content="Musescore conversion complete! ✅")
            files_to_send.append(musicxml_output_path)
            files_to_send.append(pdf_file_path)

        # Send all collected files
        for f in files_to_send:
            await message.channel.send(file=discord.File(f))
            # Delete the file after sending
            try:
                os.remove(f)
                logger.info(f"Deleted file: {f}")
            except Exception as e:
                logger.error(f"Error deleting file {f}: {e}")
        
        # Delete all folders in the ./downloads directory
        downloads_dir = "./downloads"

        for item in os.listdir(downloads_dir):
            item_path = os.path.join(downloads_dir, item)
            if os.path.isdir(item_path):  # Check if it's a folder
                try:
                    shutil.rmtree(item_path)  # Delete the folder and its contents
                    logger.info(f"Deleted folder: {item_path}")
                except Exception as e:
                    logger.error(f"Error deleting folder {item_path}: {e}")
        
    else:
        await message.channel.send(response)

async def download_file(attachment: discord.Attachment) -> str:
    """
    Downloads a file from a Discord attachment and returns the local file path.
    """
    file_path = os.path.join("downloads", attachment.filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(attachment.url) as resp:
            if resp.status == 200:
                with open(file_path, 'wb') as f:
                    f.write(await resp.read())
    return file_path

@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")

# Start the bot
bot.run(token)

# if __name__ == '__main__':
#     agent = MistralAgent()
#     filepathh = "/home/willy/Desktop/projects/gelo_agent/gelo-agent/songs/separated_audio_tweak.mp3/htdemucs/tweak/vocals_basic_pitch.mid"
#     agent.convert_midi_to_musescore(filepathh)