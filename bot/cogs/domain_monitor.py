import os
import asyncio
import logging
import discord
import aiosqlite
from utils.db import init_db
from utils.embeds import embed_domain_alert, embed_reescan_alert
from discord.ext import commands, tasks
from datetime import datetime, timezone

logger = logging.getLogger("DOMAIN-HUNTER")
DB_FILE = "/home/purgemebxby/Escritorio/Hellsing/bot/data/monitor.db"
HTTPX = ["httpx", "-ports", "80,443,8080,8000,8888,8443", "-sc", "-td", "-silent", "-no-color"]
MAX_WORKERS = 5
BATCH_SIZE = 50

class DomainHunter(commands.Cog):
    """Automated domain monitoring and subdomain discovery using Gungnir and HTTPX."""
    logger.info("Initializing DomainHunter...")
    init_db(DB_FILE)

    def __init__(self, bot):
        self.bot = bot
        self.active_workers = {}
        self.rescanner.start()
        self.bot.loop.create_task(self.restore_workers())

    def cog_unload(self):
        logger.info("cog_unload:Unloading DomainHunter...")
        self.rescanner.cancel()
        for process in self.active_workers.values():
            process.terminate()

    async def restore_workers(self):
        await self.bot.wait_until_ready()
        try:
            logger.info("restore_workers:Restoring workers...")
            async with aiosqlite.connect(DB_FILE, timeout=10) as db:
                async with db.execute("SELECT domain, webhook_url FROM main_domains") as cursor:
                    for domain, webhook_url in await cursor.fetchall():
                        if domain not in self.active_workers:
                            asyncio.create_task(self.gungnir_worker(domain, webhook_url))
            logger.info("restore_workers:Workers restored successfully.")
        except Exception as e:
            logger.error(f"restore_workers:Error while trying to restore workers - {e}")




# Send webhook alert
    async def send_webhook_alert(self, url: str, info: str, main: str, is_rescan: bool = False):
        try:
            webhook = discord.Webhook.from_url(url, session=self.bot.http._HTTPClient__session)
            if is_rescan:
                logger.info(f"webhook:Sending re-scan alert for {main}")
                embed = embed_reescan_alert(info, main)
                await webhook.send(embed=embed, username="The W1tch", avatar_url="https://i.pinimg.com/736x/0e/fc/86/0efc86b4084ad0110276610c66f16e59.jpg")
            else:
                embed = embed_domain_alert(info, main)
                await webhook.send(embed=embed, username="The WatchD0g", avatar_url="https://i.pinimg.com/736x/c8/55/c9/c855c9672d6cd0b33209e77617e3dc78.jpg")
        except Exception as e:
            logger.error(f"webhook:Webhook failed for {main}: {e}")




# Monitor Process
# Process results from gungnir with httpx
    async def httpx_process(self, batch: list, main: str, webhook_url: str):
        if not batch: 
            logger.warning("httpx_process:Batch is empty.")
            return

        logger.info(f"httpx_process:Processing {len(batch)} results for {main}")
        process = await asyncio.create_subprocess_exec(*HTTPX,
                                                        stdin=asyncio.subprocess.PIPE,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.DEVNULL)
        out, _ = await process.communicate(input=("\n".join(batch) + "\n").encode())
        if not out:
            logger.warning(f"httpx_process:No results for {main}")
            return
        results = out.decode().strip().split('\n')

        # Process results from gungnir with httpx
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            results = list(line.split()[0].replace("https://", "").replace("http://", "") for line in results if line)
            if not results:
                return

            params = []
            timestamp = datetime.now(timezone.utc).isoformat()
            placeholders = ', '.join(['(?, ?, 1, ?)'] * len(results))
            for subdomain in results:
                params.extend([subdomain, main, timestamp])


            # Insert new subdomains into DB
            async with db.execute(f"""INSERT OR IGNORE INTO subdomains (subdomain, domain, is_alive, timestamp) 
                                      VALUES {placeholders} RETURNING subdomain""", params) as cursor:
                new_subdomains = [row[0] for row in await cursor.fetchall()]


            # Send webhook alerts for new subdomains
            if new_subdomains:
                await db.commit()
                for subdomain in new_subdomains:
                    await self.send_webhook_alert(webhook_url, subdomain, main)


# Worker to process gungnir results
    async def gungnir_worker(self, main: str, webhook_url: str):
        tmp = f"/tmp/gungnir_{main}.txt"
        with open(tmp, "w") as f:
            f.write(main + "\n")


        try:
            batch = set()
            logger.info(f"gungnir_worker:Starting worker for {main}")
            process = await asyncio.create_subprocess_exec("gungnir", "-r", tmp,
                                                            stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.DEVNULL)
            self.active_workers[main] = process

            # Monitor Loop
            while True:
                try:
                    # Read line from gungnir
                    if not (line := await asyncio.wait_for(process.stdout.readline(), timeout=10)):
                        break

                    # Process line with httpx
                    if domain := line.decode().strip():
                        batch.add(domain)
                        if len(batch) >= BATCH_SIZE:
                            await self.httpx_process(list(batch), main, webhook_url)
                            batch.clear()

                except asyncio.TimeoutError:
                    if batch:
                        await self.httpx_process(list(batch), main, webhook_url)
                        batch.clear()

            # Process remaining results
            if batch: await self.httpx_process(list(batch), main, webhook_url)
        except asyncio.CancelledError:
            pass
        finally:
            if 'process' in locals() and process.returncode is None:
                process.terminate()
            self.active_workers.pop(main, None)
            if os.path.exists(tmp):
                os.remove(tmp)




# Commands
# Monitor command
    @commands.command(help="Add a target domain, create a dedicated channel and deploy a worker.")
    @commands.has_permissions(manage_channels=True)
    async def monitor(self, ctx, domain: str):
        #Constraints
        if len(self.active_workers) >= MAX_WORKERS: 
            return await ctx.send("5 active workers reached.")

        if domain in self.active_workers:
            return await ctx.send(f"Target {domain} is already monitored.")

        if not domain:
            return await ctx.send("Domain cannot be empty.")


        #Check if monitor already exists
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            async with db.execute("SELECT domain FROM main_domains WHERE domain = ?", (domain,)) as cursor:
                if await cursor.fetchone():
                    return await ctx.send("Target already exists in DB.")


            #Create channel and webhook (and category if it doesn't exist), and add to DB
            await ctx.message.add_reaction("⚙️")
            try:
                category = discord.utils.get(ctx.guild.categories, name="BUG BOUNTY") or await ctx.guild.create_category("BUG BOUNTY")
                channel = await ctx.guild.create_text_channel(f"monitor-{domain.replace('.', '-')}", category=category)
                webhook = await channel.create_webhook(name=f"Hunter-{domain}")
                logger.info(f"monitor:Channel and webhook created for {domain}")
            except discord.Forbidden:
                return await ctx.send("Insufficient permissions to create channels/webhooks.")

            await db.execute("""INSERT INTO main_domains
                                (domain, channel_id, webhook_url) VALUES (?, ?, ?)""", (domain, channel.id, webhook.url))
            await db.commit()
            logger.info(f"monitor:Added to DB for {domain}")

        #Deploy worker
        asyncio.create_task(self.gungnir_worker(domain, webhook.url))
        await ctx.send(f"Worker deployed. Monitoring started in {channel.mention}")


# Unmonitor command
    @commands.command(help="Remove a target domain and clean up its resources.")
    @commands.has_permissions(manage_channels=True)
    async def unmonitor(self, ctx, domain: str):
        if process := self.active_workers.pop(domain, None):
            logger.info(f"unmonitor:Terminating worker for {domain}")
            process.terminate()
            if os.path.exists(tmp := f"/tmp/gungnir_{domain}.txt"):
                os.remove(tmp)


        #Remove from DB
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            async with db.execute("SELECT webhook_url, channel_id FROM main_domains WHERE domain = ?", (domain,)) as cursor:
                if not (row := await cursor.fetchone()):
                    return await ctx.send(f"Target '{domain}' not found.")
                webhook_url, channel_id = row

            await db.execute("DELETE FROM main_domains WHERE domain = ?", (domain,))
            await db.execute("DELETE FROM subdomains WHERE domain = ?", (domain,))
            await db.commit()
            logger.info(f"unmonitor:Removed from DB for {domain}")

        #Delete webhook
        try:
            await discord.Webhook.from_url(webhook_url, session=self.bot.http._HTTPClient__session).delete()
            logger.info(f"unmonitor:Webhook deleted for {domain}")
        except Exception:
            pass

        #Delete channel
        if channel := ctx.guild.get_channel(channel_id):
            try:
                await channel.delete()
                logger.info(f"unmonitor:Channel deleted for {domain}")
            except Exception:
                pass
        await ctx.send(f"`{domain}` monitoring stopped. Cleaned up resources.")




# Rescanner
    @tasks.loop(hours=10)
    async def rescanner(self):
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            query = """
                SELECT m.domain, m.webhook_url, GROUP_CONCAT(s.subdomain)
                FROM main_domains m
                JOIN subdomains s ON m.domain = s.domain
                GROUP BY m.domain
            """
            async with db.execute(query) as cursor:
                if not (domains_data := await cursor.fetchall()):
                    return

        for domain, webhook_url, subs_str in domains_data:
            if not subs_str:
                continue


            alive = []
            subs = subs_str.split(',')
            # Process with max size of batches if there are more than 50 subdomains stored
            for i in range(0, len(subs), BATCH_SIZE):
                batch = subs[i:i+BATCH_SIZE]
                process = await asyncio.create_subprocess_exec(*HTTPX, 
                                                            stdin=asyncio.subprocess.PIPE, 
                                                            stdout=asyncio.subprocess.PIPE, 
                                                            stderr=asyncio.subprocess.DEVNULL)

                out, _ = await process.communicate(input=("\n".join(batch) + "\n").encode())
                if out:
                    alive.extend([line for line in out.decode().strip().split('\n') if line])

            if alive and webhook_url:
                message = "\n".join(alive[:50]) + (f"\n\nSkipped {len(alive)-50} alive subdomains." if len(alive) > 50 else "")
                if len(message) > 4000: message = message[:4000]
                await self.send_webhook_alert(webhook_url, message, domain, is_rescan=True)

    @rescanner.before_loop
    async def before_rescanner(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DomainHunter(bot))