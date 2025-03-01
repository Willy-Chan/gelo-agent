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
    await message.channel.send(response)

@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")

# Start the bot
bot.run(token)