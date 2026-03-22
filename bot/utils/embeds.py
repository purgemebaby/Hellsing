import discord
from datetime import datetime, timezone

def embed_domain_alert(subdomain: str, main: str):
    embed = discord.Embed(
        title="🔥 New Subdomain Found",
        description=f"Main Domain: **{main}**",
        color=discord.Color.red(), 
        timestamp=datetime.now(timezone.utc)
        )
    embed.add_field(name="Result", value=f"```{subdomain}```")
    embed.set_thumbnail(url="https://i.pinimg.com/originals/99/38/a4/9938a40807369ae9dce32dcb5678736d.gif")
    embed.set_footer(text="Automated Monitor")
    embed.set_author(name="The WatchD0g", icon_url="https://i.pinimg.com/originals/14/c0/1d/14c01d070ef4669ac8d9aca1f4aa9de1.gif")

    return embed


def embed_reescan_alert(subdomains: str, main: str):
    embed = discord.Embed(
        title="♻️ Rescan Detection",
        description=f"Main Domain: **{main}**\n**Alive Subdomains:**\n```\n{subdomains}\n```",
        color=discord.Color.gold(), timestamp=datetime.now(timezone.utc)
        )
    embed.set_footer(text="Automated Monitor")
    embed.set_thumbnail(url="https://i.pinimg.com/originals/20/dc/ae/20dcae4d034b577df3e5e39daaf9cc03.gif")
    embed.set_author(name="The W1tch", icon_url="https://i.pinimg.com/originals/14/c0/1d/14c01d070ef4669ac8d9aca1f4aa9de1.gif")

    return embed