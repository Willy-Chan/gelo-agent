import os
import discord
import logging
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

    # Process the message with the agent
    response = await agent.run_with_history(message, message_history[message.channel.id])
    if "FILEPATH:" in response and "SPECIFIC_TRACK:" in response:
        # Parse the response
        lines = response.split('\n')
        print(lines)
        file_path = lines[0].split(": ")[1].strip()
        specific_track = lines[1].split(": ")[1].strip()
        want_midi = lines[2].split(": ")[1].strip().lower() == "true"
        want_musescore = lines[3].split(": ")[1].strip().lower() == "true"
        want_pdf = lines[4].split(": ")[1].strip().lower() == "true"
        print(file_path)
        print(specific_track)
        print(want_midi)
        print(want_musescore)
        print(want_pdf)

        # Determine if separation is needed
        if specific_track != "original":
            await message.channel.send("Separating audio...")
            separated_files = agent.separate_audio(file_path)
            track_file_path = separated_files.get(specific_track)
        else:
            track_file_path = file_path

        # Convert to MIDI if needed
        if want_midi:
            await message.channel.send("Converting to MIDI...")
            midi_file_path = agent.convert_to_midi(track_file_path)

        # Convert to MuseScore or PDF if needed
        if want_musescore or want_pdf:
            await message.channel.send("Converting to sheet music...")
            agent.convert_midi_to_musescore(midi_file_path)
    else:
        await message.channel.send(response)

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