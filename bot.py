import os
import discord
import logging
import aiohttp
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent

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
            if attachment.filename.endswith('.mp3'):
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
    if "FILEPATH:" in response and "SPECIFIC_TRACK:" in response:
        # Parse the response
        lines = response.split('\n')
        file_path = lines[0].split(": ")[1].strip()
        specific_track = lines[1].split(": ")[1].strip()
        want_midi = lines[2].split(": ")[1].strip().lower() == "true"
        want_musescore = lines[3].split(": ")[1].strip().lower() == "true"
        want_pdf = lines[4].split(": ")[1].strip().lower() == "true"

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
            loading_message = await message.channel.send("Converting to sheet music... 🎼")
            musicxml_output_path, pdf_file_path = agent.convert_midi_to_musescore(midi_file_path)
            await loading_message.edit(content="Sheet music conversion complete! ✅")
            files_to_send.append(musicxml_output_path)
            files_to_send.append(pdf_file_path)

        # Send all collected files
        for file_path in files_to_send:
            print(file_path)
            await message.channel.send(file=discord.File(file_path))
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