import os
import asyncio
import logging
import discord
from discord.ext import commands
from discord import Intents
from dotenv import load_dotenv
from pretty_help import AppMenu, PrettyHelp, AppNav

load_dotenv(os.path.join(os.getcwd(), ".env"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HELLSING-OPS")

if DISCORD_TOKEN is None:
    logger.error("No Discord token found, bot will not start. Please create a .env file with the DISCORD_TOKEN variable.")


# Permissions for the bot
intents = Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
permissions = discord.Permissions(2260992654961904)

bot = commands.Bot(command_prefix="$",
                   intents=intents,
                   permissions=permissions,
                   case_insensitive=True,
                   max_messages=100,
                   heartbeat_timeout=150.0)


@bot.event
async def on_connect():
    logger.warning(f" {bot.user} has connected to Discord!\n")
    for guild in bot.guilds:
        logger.warning(f" Connected to {guild.name}")

@bot.event
async def on_ready():
    """Ready to interact with Discord."""
    logger.warning(f" {bot.user} starting monitoring!\n")
    logger.info(f" Environment variables\nDISCORD_TOKEN: {DISCORD_TOKEN}\n")
    await bot.change_presence(activity=discord.Game(name="In nomine Patris ⛪"))


# Help Menu
ending_note = "To list available commands from a specific group, type {help.clean_prefix}{help.invoked_with} <group>. To show a specific command's syntax, type {help.clean_prefix}{help.invoked_with} <command>."
menu = AppMenu(timeout=120)
bot.help_command = PrettyHelp(menu=menu, ending_note=ending_note,
                            show_index=True,
                            no_category="General",
                            thumbnail_url="https://i.pinimg.com/originals/a5/39/fd/a539fd7828c02d2872c5c5eb1af3b97d.gif",
                            index_title="Commands' Groups",
                            case_insensitive=True,
                            color=discord.Colour.from_rgb(21, 214, 18))


cogs = [
    "cogs.general_commands",
    "cogs.domain_monitor"
]

async def load_cogs(bot):
    for cog in cogs:
        await bot.load_extension(cog)

async def main():
    async with bot:
        bot.add_view(AppNav())
        await load_cogs(bot)
        await bot.start(str(DISCORD_TOKEN))

if __name__ == "__main__":
    asyncio.run(main())