
from json import load
from sys import exit
from discord import Intents
from discord.ext.commands import Bot
from discord import Status
from os import listdir, walk
from psutil import process_iter, AccessDenied, NoSuchProcess, TimeoutExpired
from os.path import getsize, join
from shutil import rmtree
from asyncio import get_event_loop
from discord.app_commands import describe
from discord import Activity
from discord.activity import ActivityType
from scripts.aniworld_scraper import download_aniworld, auto_add_animes, changeWebhook
from scripts import jelly_api, plex_api
from discord import Interaction
from datetime import datetime

def log_debug(message):
    print(f"[DEBUG | {datetime.now().strftime('%H:%M:%S')}] {message}")

log_debug(f"Contents in main: {len(listdir('./'))}")
log_debug(f"Current absolute path: {__file__}")

# Read the config file
try:
    with open("config.json") as json_config:
        config_data = load(json_config)
        json_config.close()
    discord_token = config_data["discord_token"]
    media_folder = config_data["media_folder"]
    plex_url = config_data["plex_url"]
    jelly_url = config_data["jelly_url"]
    x_plex_token = config_data["x_plex_token"]
    media_folder_srv = config_data["media_folder_srv"]
    jelly_token = config_data["jelly_token"]
    discord_webhook_config = config_data["discord_webhook"]
    version = config_data["version"]
except:
    print("Failed to load config.")
    exit()

log_debug(f"Contents in media folder: {len(listdir(media_folder))}")

activity = Activity(name=f"Media {version}", type=ActivityType.listening)
bot = Bot(command_prefix="!", intents=Intents.all(), activity=activity, status=Status.dnd)
lock = False

async def add_anime_function(anime_name, anime_language, debug):
    loop = get_event_loop()
    await loop.run_in_executor(None, download_aniworld, anime_name, anime_language, media_folder, "VOE", 5, 5, 4, debug)

async def auto_add_function():
    loop = get_event_loop()
    await loop.run_in_executor(None, auto_add_animes, media_folder, plex_url, x_plex_token, media_folder_srv, jelly_url, jelly_token, 2, 30)

async def send_error(message):
    channel = bot.get_channel(1217911001354211359)
    await channel.send(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] {message}")

async def send_info(message):
    channel = bot.get_channel(1217911001354211359)
    await channel.send(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] {message}")


@bot.event
async def on_ready():
    changeWebhook(discord_webhook_config)
    synced = await bot.tree.sync()
    log_debug(f"Synced {len(synced)} command(s) for {bot.user.name}")
    channel = bot.get_channel(1217911001354211359)
    await channel.send(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Media {version} is online.")
    await auto_add_function()

@bot.tree.command(name="remove_anime", description="Remove Anime from Media Server")
@describe(name="Anime Name")
async def remove_anime(interaction: Interaction, name: str):
    if not (interaction.channel_id == 1217911001354211359):
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Wrong channel was used. Please use {bot.get_channel(1217911001354211359).mention}.", ephemeral=True) # noqa
        return
    global lock
    if lock:
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Media commands are currently locked. Please try again later.") # noqa
        return
    lock = True
    await send_info(f"Enabled media lock.")
    await interaction.response.send_message(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Removing {name.replace('-', ' ').title()} from the media server...") # noqa
    try:
        rmtree(f"{media_folder}/{name.replace('-', ' ').title()}")
        await send_info(f"Successfully removed {name.replace('-', ' ').title()} from the media server.")
        plex_api.plex_refresh(media_folder_srv=media_folder_srv, plex_url=plex_url, x_plex_token=x_plex_token)
        jelly_api.jelly_refresh(jelly_url, jelly_token)
        await send_info(f"Libraries are refreshing...")
    except FileNotFoundError:
        await send_error(f"Anime {name.replace('-', ' ').title()} cannot be found on the media server.")
    except:
        await send_error(f"Failed to remove {name.replace('-', ' ').title()} from the media server.")

    lock = False
    await send_info(f"Disabled media lock.")

@bot.tree.command(name="jelly_user", description="Create Jellyfin User")
@describe(username="Username", password="Password")
async def jelly_user(interaction: Interaction, username: str, password: str):
    if not (interaction.channel_id == 1217911001354211359):
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Wrong channel was used. Please use {bot.get_channel(1217911001354211359).mention}.", ephemeral=True) # noqa
        return
    await interaction.response.send_message(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Creating Jellyfin user {username}...", ephemeral=True) # noqa
    res_code = jelly_api.jelly_user(username, password, jelly_url, jelly_token)
    if res_code == 200:
        await send_info(f"Jellyfin user {username} has been successfully created.")
    else:
        await send_error(f"Failed to create Jellyfin user {username}.")

@bot.tree.command(name="add_anime", description="Add Anime to Media Server")
@describe(name="Anime Name", language="Language")
async def add_anime(interaction: Interaction, name: str, language: str, debug: bool = False):
    if not (interaction.channel_id == 1217911001354211359):
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Wrong channel was used. Please use {bot.get_channel(1217911001354211359).mention}.", ephemeral=True) # noqa
        return
    global lock
    if lock:
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Media commands are currently locked. Please try again later.") # noqa
        return
    lock = True
    await send_info(f"Enabled media lock.")
    await interaction.response.send_message(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Adding {name.replace('-', ' ').title()} in {language.lower().capitalize()} to the media server...") # noqa
    await add_anime_function(name, language, debug)
    plex_api.plex_refresh(media_folder_srv=media_folder_srv, plex_url=plex_url, x_plex_token=x_plex_token)
    jelly_api.jelly_refresh(jelly_url, jelly_token)
    await send_info(f"Libraries are refreshing...")
    lock = False
    await send_info(f"Disabled media lock.")

@bot.tree.command(name="size_library", description="Size of Media Library")
async def size_library(interaction: Interaction):
    if not (interaction.channel_id == 1217911001354211359):
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Wrong channel was used. Please use {bot.get_channel(1217911001354211359).mention}.", ephemeral=True) # noqa
        return
    await interaction.response.send_message(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Calculating size of media library...") # noqa
    folder_size = 0
    for (path, dirs, files) in walk(media_folder):
        for file in files:
            folder_size += getsize(join(path, file))
    await send_info(f"Media library size: {round(folder_size / 1024 / 1024 / 1024, 2)} GB")

@bot.tree.command(name="kill_voe", description="Use this if VOE is stuck")
async def kill_voe(interaction: Interaction):
    if not (interaction.channel_id == 1217911001354211359):
        await interaction.response.send_message(f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] Wrong channel was used. Please use {bot.get_channel(1217911001354211359).mention}.", ephemeral=True)
        return
    await interaction.response.send_message(f"[INFO | {datetime.now().strftime('%H:%M:%S')}] Killing VOE process...")
    processes = [proc for proc in process_iter(['pid', 'name', 'cmdline'])]

    ffmpeg_processes = [proc for proc in processes if proc.info['cmdline'] and 'ffmpeg' in proc.info['cmdline']]

    for proc in ffmpeg_processes:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except NoSuchProcess:
            pass  # The process has already terminated
        except AccessDenied:
            await send_error(f"Access denied when trying to terminate process with PID {proc.pid}")
        except TimeoutExpired:
            await send_info(f"Process with PID {proc.pid} did not terminate in time, killing it")
            proc.kill()
    await send_info(f"Terminated {len(ffmpeg_processes)} ffmpeg process(es).")

bot.run(discord_token)
