import os
import asyncio
import logging
import sqlite3
import discord

from utils.db import init_db
from discord.ext import commands, tasks
from datetime import datetime, timezone

logger = logging.getLogger("DOMAIN-HUNTER")

DB_FILE = "/home/purgemebxby/Escritorio/Hellsing/bot/data/monitor.db"
HTTPX = ["httpx", "-ports", "80,443,8080,8000,8888,8443", "-sc", "-td", "-silent", "-no-color"]
MAX_WORKERS = 5
BATCH_SIZE = 50


class DomainHunter(commands.Cog):
    """Automated domain monitoring and subdomain discovery using Gungnir and HTTPX."""
    # Module configuration
    init_db(DB_FILE)

    def __init__(self, bot):
        self.bot = bot
        self.active_workers = {} # Concurrent tasks
        self.rescanner.start() # Start Rescanner Loop

    def cog_unload(self):
        """Terminate workers and rescanner loop when the module is unloaded."""
        self.rescanner.cancel()
        logger.critical("Rescanner loop cancelled.")
        for domain, process in self.active_workers.items():
            process.terminate()
            logger.critical(f"Worker terminated: {domain}")




# Webhook messages
    async def send_webhook_alert(self, webhook_url: str, subdomain_info: str, main: str):
        try:
            client = self.bot.http._HTTPClient__session
            async with discord.Webhook.from_url(webhook_url, session=client) as webhook:
                embed = discord.Embed(
                    title="🔥 New Subdomain Found",
                    description=f"Main Domain: **{main}**",
                    color=discord.Color.red(), 
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Result", value=f"```{subdomain_info}```")
                embed.set_thumbnail(url="https://i.pinimg.com/originals/86/b1/58/86b15845e3604452cb8539470eea3641.gif")
                embed.set_footer(text="Automated Monitor")
                embed.set_author(name="Hellsing", icon_url="https://i.pinimg.com/originals/14/c0/1d/14c01d070ef4669ac8d9aca1f4aa9de1.gif")
                await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Webhook transmission failed for {main}: {e}")


    async def send_rescan_webhook_alert(self, webhook_url: str, subdomains: list, main: str):
        """Emits notifications through native webhooks."""
        if not subdomains: return

        # Limit output
        skip = len(subdomains) - 50
        subdomains = "\n".join(subdomains[:50])
        if skip > 0:
            subdomains += f"\n\nSkipped {skip} alive subdomains."
        if len(subdomains) > 4000:
            subdomains = subdomains[:4000]

        try:
            client = self.bot.http._HTTPClient__session
            async with discord.Webhook.from_url(webhook_url, session=client) as webhook:
                embed = discord.Embed(
                    title="♻️ Rescan Detection",
                    description=f"Main Domain: **{main}**\n**Alive Subdomains:**\n```\n{subdomains}\n```",
                    color=discord.Color.gold(), timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text="Automated Monitor")
                embed.set_thumbnail(url="https://i.pinimg.com/originals/20/dc/ae/20dcae4d034b577df3e5e39daaf9cc03.gif")
                embed.set_author(name="Hellsing", icon_url="https://i.pinimg.com/originals/14/c0/1d/14c01d070ef4669ac8d9aca1f4aa9de1.gif")
                await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Webhook transmission failed for {main}: {e}")




# HTTPX processing and Gungnir tasks creation 
    async def process_batch(self, batch: list, main: str, webhook_url: str):
        """Processes batches of subdomains, updates DB and notifies."""
        if not batch: return
        domains_str = "\n".join(batch) + "\n"

        try:
            process = await asyncio.create_subprocess_exec(*HTTPX,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_data, _ = await process.communicate(input=domains_str.encode())
            
            # Process HTTPX output, initiate connection with DB and replace schema
            if stdout_data:
                results = stdout_data.decode().strip().split('\n')
                conn = sqlite3.connect(DB_FILE, timeout=10)
                cursor: sqlite3.Cursor = conn.cursor()
                timestamp = datetime.now(timezone.utc).isoformat()

                for line in results:
                    if not line:
                        continue
                    subdomain = line.split()[0].replace("https://", "").replace("http://", "")

                    # Insert new subdomains into DB. If exists, ignore.
                    try:
                        cursor.execute("INSERT INTO subdomains (subdomain, domain, is_alive, timestamp) VALUES (?, ?, 1, ?)", 
                            (subdomain, main, timestamp))
                        conn.commit()
                        await self.send_webhook_alert(webhook_url, line, main)
                    except sqlite3.IntegrityError:
                        continue
                conn.close()

        except Exception as e:
            logger.error(f"HTTPX batch processing failed: {e}")


    async def gungnir_worker(self, main: str, webhook_url: str):
        """Background process that executes Gungnir for a specific target."""
        tmp_root_file = f"/tmp/gungnir_{main}.txt"
        with open(tmp_root_file, "w") as f:
            f.write(main + "\n")

        GUNGNIR = ["gungnir", "-r", tmp_root_file, "-f"]
        batch = []

        # Execute Gungnir
        try:
            process = await asyncio.create_subprocess_exec(*GUNGNIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            self.active_workers[main] = process
            logger.info(f"Worker started for: {main}")

            while True:
                line = await process.stdout.readline()
                if not line: break
                
                domain = line.decode().strip()
                if domain: batch.append(domain)

                if len(batch) >= BATCH_SIZE:
                    await self.process_batch(batch, main, webhook_url)
                    batch.clear()

            if batch:
                await self.process_batch(batch, main, webhook_url)

        except asyncio.CancelledError:
            logger.info(f"Worker cancelled for {main}")
        finally:
            # Terminate workers
            if 'process' in locals() and process.returncode is None:
                process.terminate()

            if main in self.active_workers:
                del self.active_workers[main]

            if os.path.exists(tmp_root_file):
                os.remove(tmp_root_file)



# Commands
    @commands.command(help="Add a target domain, create a dedicated channel and deploy a worker. Max 5 simultaneous.")
    @commands.has_permissions(manage_channels=True)
    async def monitor(self, ctx, domain: str):
        if len(self.active_workers) >= MAX_WORKERS:
            return await ctx.send("5 active workers reached. Close an active worker first.")
        if domain in self.active_workers:
            return await ctx.send(f"Target {domain} is already being monitored.")
        if len(domain) == 0:
            return await ctx.send("Domain cannot be empty.")

        await ctx.message.add_reaction("⚙️")
        logger.info(f" Deploying worker for {domain} \nUser: {ctx.author.name}\nServer: {ctx.guild.name}\nChannel: {ctx.channel.name}\n")

        # Create category, channel and webhook
        try:
            category = discord.utils.get(ctx.guild.categories, name="BUG BOUNTY")
            if not category:
                category = await ctx.guild.create_category("BUG BOUNTY")
            
            channel_name = f"monitor-{domain.replace('.', '-')}"
            channel = await ctx.guild.create_text_channel(channel_name, category=category)
            webhook = await channel.create_webhook(name=f"Hunter-{domain}")
        except discord.Forbidden:
            return await ctx.send("Insufficient permissions to create channels or webhooks.")

        # Register in database
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor: sqlite3.Cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO main_domains (domain, channel_id, webhook_url) VALUES (?, ?, ?)", (domain, channel.id, webhook.url))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close(); return await ctx.send("Target already exists in the database.")
        conn.close()

        # Deploy async worker
        asyncio.create_task(self.gungnir_worker(domain, webhook.url))
        await ctx.send(f"Worker deployed. Monitoring started in {channel.mention}")



# Rescanner
    @tasks.loop(hours=10)
    async def rescanner(self):
        """Rescanner cycle. Groups results by target to send a report."""
        # SQLite fetch targets
        logger.info("Starting rescan cycle.")
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("SELECT domain, webhook_url FROM main_domains")
        domains_data = cursor.fetchall()

        if not domains_data: 
            logger.warning("No domains found in the DB.")
            conn.close()
            return

        webhooks: dict[str, str] = {row[0]: row[1] for row in domains_data} # {domain: webhook_url}
        alive_by_domain = {domain: [] for domain in webhooks.keys()} # {domain: [subdomains]}

        # SQLite fetch subdomains
        cursor.execute("SELECT subdomain, domain FROM subdomains")
        while True:
            batch_rows = cursor.fetchmany(BATCH_SIZE)
            if not batch_rows: break
            
            subdomains_batch = [row[0] for row in batch_rows] # [Subdomains]
            batch_map = {row[0]: row[1] for row in batch_rows} # {Subdomain: domain}
            domains_str = "\n".join(subdomains_batch) + "\n" 
            try:
                process = await asyncio.create_subprocess_exec(*HTTPX,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )
                stdout_data, _ = await process.communicate(input=domains_str.encode())
                
                if stdout_data:
                    results = stdout_data.decode().strip().split('\n')
                    for line in results:
                        if not line: 
                            continue
                        subdomain = line.split()[0].replace("https://", "").replace("http://", "")

                        domain = batch_map.get(subdomain) # {Subdomain: Target}, get target from subdomain
                        if domain and domain in alive_by_domain:
                            alive_by_domain[domain].append(line)
            except Exception as e:
                logger.error(f"Error in rescanner execution: {e}")
        conn.close()

        # Send data via webhook
        for domain, valid_subdomains in alive_by_domain.items():
            if valid_subdomains:
                webhook_url = webhooks.get(domain)
                if webhook_url:
                    await self.send_rescan_webhook_alert(webhook_url, valid_subdomains, domain)
        logger.info("Rescanner cycle completed.")

    @rescanner.before_loop
    async def before_rescanner(self): # Wait until bot is ready to start loop
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DomainHunter(bot))