<div align="center">

<img src="https://i.pinimg.com/originals/08/20/36/0820366bf388ea30469160e576595827.gif" width="200" alt="Hellsing left ornament">

# Hellsing

### Passive Attack-Surface Monitor & Discord Alerting Bot

</div>

<div align="center">
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python 3.11 | 3.12"/></a>
<a href="https://discordpy.readthedocs.io/"><img src="https://img.shields.io/badge/discord.py-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white" alt="discord.py"/></a>
<a href="https://python-poetry.org/"><img src="https://img.shields.io/badge/Poetry-60A5FA?style=for-the-badge&logo=poetry&logoColor=0B3D8D" alt="Poetry"/></a>
<a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite"/></a>
<br>
</div>

<p align="center">
<b>Hellsing</b> is a self-hosted Discord bot that turns a server into a live command center for continuous subdomain discovery. Point it at a target's root domain and it will watch <b>Certificate Transparency logs in real time</b>, probe every newly issued hostname to see if it's actually alive, and drop a formatted alert straight into a dedicated channel the moment something new shows up.
</p>

---

### Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation &amp; Setup](#installation--setup)
- [Configuration Notes](#configuration-notes)
- [Commands](#commands)
- [Before You Deploy](#before-you-deploy)

---

## <img src="https://i.pinimg.com/originals/82/37/6d/82376d09f6ad1ce49bf1075e63da9c49.gif" width="45" alt="icon"> Overview

**Hellsing** keeps a persistent watch on CT logs for every domain you register, and the second a new hostname surfaces, it checks whether it's actually serving HTTP(S) and pings your team.

Each monitored domain gets its own Discord category (`BUG BOUNTY`), its own dedicated text channel, and its own webhook, so multiple targets can be tracked in parallel without alerts bleeding into each other. Under the hood, the project leans on two [ProjectDiscovery](https://github.com/projectdiscovery) tools: `gungnir` for the CT-log tailing and `httpx` for liveness/tech-detection probing, orchestrated by an `asyncio`-based worker model, with SQLite as the source of truth so monitoring survives a bot restart.

## <img src="https://i.pinimg.com/originals/53/8d/88/538d88d2332c4b18566808d5e3224cdc.gif" width="45" alt="icon"> Features

- [x] Real-time subdomain discovery via Certificate Transparency logs (`gungnir`), no wordlists required.
- [x] Automatic liveness + basic tech-detection probing of every new hostname (`httpx`).
- [x] One isolated Discord channel + webhook per monitored domain, auto-organized under a `BUG BOUNTY` category.
- [x] Persistent state in SQLite — monitoring resumes automatically after a bot restart.
- [x] Deduplication at the database level, so a subdomain is never alerted on twice.
- [x] Scheduled 10-hour re-scan of every stored subdomain to catch liveness changes over time.
- [x] Clean teardown command that removes the channel, webhook and all stored data for a target.
- [x] Interactive, categorized help menu via [`discord-pretty-help`](https://github.com/stroupbslayen/discord-pretty-help).
- [x] Basic channel-hygiene utility (`$purge`) for keeping monitor channels tidy.

## <img src="https://i.pinimg.com/originals/20/dc/ae/20dcae4d034b577df3e5e39daaf9cc03.gif" width="45" alt="icon"> Prerequisites

Before running Hellsing, make sure you have:

- **Python 3.11 or 3.12** (`requires-python = "^3.11 || ^3.12"`).
- **[Poetry](https://python-poetry.org/)** for dependency management.
- **A Discord Bot Token**, created via the [Discord Developer Portal](https://discord.com/developers/applications), with the **`MESSAGE CONTENT`** privileged intent enabled and, at minimum, the **Manage Channels**, **Manage Webhooks**, **Manage Messages**, **View Channels**, **Send Messages** and **Embed Links** permissions granted on invite (the bot enforces `manage_channels` / `manage_messages` at the command level regardless of the invite scope).
- **[`gungnir`](https://github.com/projectdiscovery/gungnir)** and **[`httpx`](https://github.com/projectdiscovery/httpx)** installed as system binaries and reachable from `PATH`. Both are invoked as external subprocesses — `pip install httpx` will **not** satisfy this requirement, since Hellsing calls the Go CLI tool, not the Python HTTP client library of the same name.

## <img src="https://i.pinimg.com/originals/c6/fb/16/c6fb1692b53480442c44e54620271f43.gif" width="45" alt="icon"> Installation &amp; Setup

```bash
# 1. Clone the repository
git clone https://github.com/purgemebaby/Hellsing.git
cd Hellsing

# 2. Install dependencies (creates/uses a Poetry-managed virtualenv)
poetry install

# 3. Create the .env file at the repository root
echo "DISCORD_TOKEN=your-bot-token-here" > .env

# 4. Create the folder the SQLite database will live in
mkdir -p bot/data

# 5. Run the bot from the repository root
poetry run python bot/bot.py
```

> [!IMPORTANT]
> `.env` must sit at the repository root (where you run `poetry run python bot/bot.py` from), since it's loaded via `os.getcwd()`, not relative to `bot.py`'s own location.

## <img src="https://i.pinimg.com/originals/4b/4f/a1/4b4fa16fff0d9782b6e53db976f89f78.gif" width="45" alt="icon"> Configuration Notes

- The command prefix is `$` and is case-insensitive (`case_insensitive=True`).
- `MAX_WORKERS` (default `5`) and `BATCH_SIZE` (default `50`) live at the top of `bot/cogs/domain_monitor.py` and can be tuned to fit your server's rate limits and how many targets you actually hunt at once.
- The bot's `DB_FILE` path is currently **hardcoded** in `bot/cogs/domain_monitor.py`:
  ```python
  DB_FILE = "/home/purgemebxby/Escritorio/Hellsing/bot/data/monitor.db"
  ```
  You'll need to change this to a path that exists on your own machine before the bot will start correctly — otherwise `init_db()` will fail on launch.

## <img src="https://i.pinimg.com/originals/37/ea/40/37ea40673387016d2ff367d51cafa218.gif" width="45" alt="icon"> Commands

| Command | Description | Required Permission |
|---|---|---|
| `$monitor <domain>` | Registers a new target: creates its channel + webhook and deploys a `gungnir` worker for it. | Manage Channels |
| `$unmonitor <domain>` | Stops monitoring a target and deletes its channel, webhook, and stored data. | Manage Channels |
| `$purge [amount]` | Deletes the given number of messages in the current channel (default `10`, max `100`). | Manage Messages |
| `$help [command\|group]` | Opens the interactive, paginated help menu. | — |

## Before You Deploy

- The hardcoded `DB_FILE` path (see [Configuration Notes](#configuration-notes)) must be edited, and its parent directory must already exist.
- `httpx` here always refers to the ProjectDiscovery CLI binary; if the wrong `httpx` is on your `PATH`, the probing subprocess calls will fail silently.
- `$unmonitor` is destructive and immediate: the channel, the webhook and every stored subdomain for that target are deleted with no soft-delete or confirmation step.
- The 5-worker cap is a hard ceiling, not a queue — a 6th `$monitor` call is simply rejected until a slot frees up via `$unmonitor`.
