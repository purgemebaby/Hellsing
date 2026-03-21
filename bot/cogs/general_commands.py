import logging
import urllib.request
import discord
from discord.ext import commands


logger = logging.getLogger("GENERAL")

class General(commands.Cog):
    """Commands that don't fit in any other category, like clean up channels, expand URLs, etc..."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(help="Clears messages in a channel. Default: 10 messages.")
    async def purge(self, ctx, amount = "10"):
        if not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("You do not have permission to use this command folk.")

        if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            return

        logger.info(f" Purging {amount} messages in {ctx.channel.name} \nUser: {ctx.author.name}\nServer: {ctx.guild.name}\nChannel: {ctx.channel.name}\n")

        if amount.isdigit():
            amount = int(amount)
            if amount < 1 or amount > 100:
                return await ctx.send("Please specify a number between 1 and 100.")
            await ctx.channel.purge(limit=amount)


async def setup(bot):
    await bot.add_cog(General(bot))