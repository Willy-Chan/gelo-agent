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
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
agent = MistralAgent()


# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")


@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Process the message with the agent you wrote
    # Open up the agent.py file to customize the agent
    logger.info(f"Processing message from {message.author}: {message.content}")
    response = await agent.run(message)


    print(response)

    # Send the response back to the channel
    await message.reply(response)


# Commands


# This example command is here to show you how to add commands to the bot.
# Run !ping with any number of arguments to see the command in action.
# Feel free to delete this if your project will not need commands.
@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")


# Start the bot, connecting it to the gateway
# bot.run(token)      # UNCOMMENT THIS TO INTEGRATE IT INTO DISCORD BOT

def main():
    while True:
        # Ask for the path to the song file
        file_path = input("Enter the path to the song file: ")

        # 1) Validate the file path, and when you do run the audio separation on the files
        if agent.validate_file_path(file_path):
            # If valid, proceed with audio separation
            proceed_audio = input("Do audio separation?")
            proceed_audio = (proceed_audio == "yes")
            if proceed_audio:
                print("Proceeding with audio separation...")
                agent.separate_audio(file_path)

            # 2) Ask the user which stem to convert to sheet music
            while True:
                if proceed_audio:
                    stem_choice = input("Which stem do you want to convert to sheet music? (bass, drums, vocals, other): ").strip().lower()
                    stem_file_path = os.path.join(os.path.dirname(file_path), f'separated_audio_{os.path.basename(file_path)}', f'{stem_choice}.wav')
                else:
                    stem_file_path = file_path

                if os.path.isfile(stem_file_path):
                    print(f"Converting {stem_file_path} to MIDI...")
                    # agent.convert_to_midi(stem_file_path)

                    # Confirm with the user to proceed to convert MIDI to MuseScore
                    confirm = input("Do you want to convert the MIDI to sheet music? (yes/no): ").strip().lower()
                    if confirm == "yes":
                        print(stem_file_path)


                        agent.convert_midi_to_musescore(stem_file_path.replace('.mp3', '_basic_pitch.mid'))
                        print("Conversion to sheet music completed.")
                    else:
                        print("Conversion to sheet music canceled.")
                    break
                else:
                    print(f"Invalid choice or file not found for {stem_file_path}. Please choose again.")
            break
        else:
            # If invalid, prompt again
            print("Please enter a valid file path.")


if __name__ == "__main__":
    main()
