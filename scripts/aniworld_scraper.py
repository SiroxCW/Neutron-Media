
from bs4 import BeautifulSoup
from requests import get, post
from os.path import exists, getsize
from os import remove, mkdir, walk, listdir
from scripts import jelly_api, plex_api
from re import compile
from urllib.request import urlopen, Request
from subprocess import run, PIPE, CalledProcessError
from threading import Thread, active_count, enumerate
from datetime import datetime, timedelta
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService

debug = False

def changeWebhook(webhook):
    global discord_webhook
    discord_webhook = webhook

VOE_PATTERNS = [compile(r"'hls': '(?P<url>.+)'"),
                compile(r'prompt\("Node",\s*"(?P<url>[^"]+)"')]

log_output_path = ""
log_anime_name = ""
log_aniworld_total_episodes = -1

def log_error(message):
    if log_aniworld_total_episodes != -1:
        file_count = 0
        for path, dirs, files in walk(f"{log_output_path}/{log_anime_name.replace('-', ' ').title()}"):
            for i in files:
                file_count += 1
        data = {
            'content': f"[{str(file_count).zfill(2)}/{log_aniworld_total_episodes} | ERROR | {datetime.now().strftime('%H:%M:%S')}] {message}"
        }
    else:
        data = {
            'content': f"[ERROR | {datetime.now().strftime('%H:%M:%S')}] {message}"
        }
    response = post(discord_webhook, json=data)
    if response.status_code != 204:
        print(f'Failed to send message to Discord: {response.status_code} - {response.text}')

def log_success(message):
    data = {
        'content': f"[SUCCESS | {datetime.now().strftime('%H:%M:%S')}] {message}"
    }
    response = post(discord_webhook, json=data)
    if response.status_code != 204:
        print(f'Failed to send message to Discord: {response.status_code} - {response.text}')

def log_debug(message):
    if debug:
        if log_aniworld_total_episodes != -1:
            file_count = 0
            for path, dirs, files in walk(f"{log_output_path}/{log_anime_name.replace('-', ' ').title()}"):
                for i in files:
                    file_count += 1
            data = {
                'content': f"[{str(file_count).zfill(2)}/{log_aniworld_total_episodes} | INFO | {datetime.now().strftime('%H:%M:%S')}] {message}"
            }
        else:
            data = {
                'content': f"[DEBUG | {datetime.now().strftime('%H:%M:%S')}] {message}"
            }
        response = post(discord_webhook, json=data)
        if response.status_code != 204:
            print(f'Failed to send message to Discord: {response.status_code} - {response.text}')

def log_info(message):
    if log_aniworld_total_episodes != -1:
        file_count = 0
        for path, dirs, files in walk(f"{log_output_path}/{log_anime_name.replace('-', ' ').title()}"):
            for i in files:
                file_count += 1
        data = {
            'content': f"[{str(file_count).zfill(2)}/{log_aniworld_total_episodes} | INFO | {datetime.now().strftime('%H:%M:%S')}] {message}"
        }
    else:
        data = {
            'content': f"[INFO | {datetime.now().strftime('%H:%M:%S')}] {message}"
        }
    response = post(discord_webhook, json=data)
    if response.status_code != 204:
        print(f'Failed to send message to Discord: {response.status_code} - {response.text}')

def download_voe(hls_url, file_name, anime_name_full):
    try:
        ffmpeg_cmd = ['ffmpeg', '-i', hls_url, '-c', 'copy', file_name]
        run(ffmpeg_cmd, check=True, stdout=PIPE, stderr=PIPE)
        log_info(f"VOE -> Finished download of {anime_name_full}.\n")
    except CalledProcessError as e:
        print(e)
        if exists(file_name):
            remove(file_name)
            log_debug(f"VOE -> Server Error. Can't download {file_name}.\n")


def download_other(link, file_name, anime_provider, anime_name_full):
    try:
        r = get(link, stream=True)
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        if getsize(file_name) != 0:
            log_info(f"{anime_provider} -> Finished download of {anime_name_full}.\n")
        else:
            if exists(file_name):
                remove(file_name)
                log_debug(f"{anime_provider} -> Server Error. Can't download {file_name}.\n")
    except Exception as e:
        print(e)
        if exists(file_name):
            remove(file_name)
            log_debug(f"{anime_provider} -> Server Error. Can't download {file_name}.\n")

def voe_pattern_search(decoded_html):
    for VOE_PATTERN in VOE_PATTERNS:
        match = VOE_PATTERN.search(decoded_html)
        if match is None:
            continue
        content_link = match.group("url")
        if content_link_is_not_valid(content_link):
            continue
        return content_link

def content_link_is_not_valid(content_link):
    return content_link is None or not content_link.startswith("https://")

def get_voe_content_link_with_selenium(provider_url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--no-sandbox")
    chrome_options.binary_location = "/opt/google/chrome/chrome"
    chrome_driver_path = "/usr/bin/chromedriver"
    if exists(chrome_driver_path):
        chrome_service = ChromeService(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    driver.get(provider_url)
    decoded_html = urlopen(driver.current_url).read().decode("utf-8")
    content_link = voe_pattern_search(decoded_html)
    if content_link is not None:
        driver.quit()
        return content_link
    voe_play_div = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'voe-play'))
    )
    voe_play_div.click()
    video_in_media_provider = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'media-provider video source'))
    )
    content_link = video_in_media_provider.get_attribute('src')
    driver.quit()
    return content_link

def fetch_cache_url(url, provider, failed):
    log_debug(f"{provider} -> Fetching cache URL for {url}.\n")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    STREAMTAPE_PATTERN = compile(r'get_video\?id=[^&\'\s]+&expires=[^&\'\s]+&ip=[^&\'\s]+&token=[^&\'\s]+\'')
    request = Request(url, headers=headers)
    html_page = urlopen(request).read().decode("utf-8")
    try:
        if provider == "Vidoza":
            soup = BeautifulSoup(html_page, features="html.parser")
            cache_link = soup.find("source").get("src")
        elif provider == "VOE":
            cache_link = voe_pattern_search(html_page)
            if cache_link is None:
                cache_link = get_voe_content_link_with_selenium(url)
        elif provider == "Streamtape":
            cache_link = STREAMTAPE_PATTERN.search(html_page)
            if cache_link is None:
                return fetch_cache_url(url, provider, True)
            cache_link = "https://" + provider + ".com/" + cache_link.group()[:-1]
    except AttributeError:
        if not failed:
            return fetch_cache_url(url, provider, True)
        else:
            return None

    try:
        return cache_link
    except UnboundLocalError:
        return None

def fetch_redirect_url(aniworld_season_and_episode_url, anime_language, anime_provider):
    aniworld_season_and_episode_url_html = get(aniworld_season_and_episode_url)

    soup = BeautifulSoup(aniworld_season_and_episode_url_html.content, "html.parser")
    lang_key_mapping = {}
    # Find the div with class "changeLanguageBox"
    change_language_div = soup.find("div", class_="changeLanguageBox")
    if change_language_div:
        # Find all img tags inside the div to extract language and data-lang-key
        lang_elements = change_language_div.find_all("img")
        for lang_element in lang_elements:
            language = lang_element.get("alt", "") + "," + lang_element.get("title", "")
            data_lang_key = lang_element.get("data-lang-key", "")
            if language and data_lang_key:
                lang_key_mapping[language] = data_lang_key
    new_dict = {}
    already_seen = set()
    for key, value in lang_key_mapping.items():
        new_dict[value] = set([element.strip() for element in key.split(',')])
    return_dict = {}
    for key, values in new_dict.items():
        for value in values:
            if value in already_seen and value in return_dict:
                del return_dict[value]
                continue
            if value not in already_seen and value not in return_dict:
                return_dict[value] = key
                already_seen.add(value)
    lang_key_mapping = return_dict
    lang_key = lang_key_mapping.get(anime_language)
    if not lang_key:
        return False, lang_key_mapping
    matching_li_elements = soup.find_all("li", {"data-lang-key": lang_key})
    matching_li_element = next((li_element for li_element in matching_li_elements if li_element.find("h4").get_text() == anime_provider), None)

    try:
        if matching_li_element:
                href_value = matching_li_element.get("data-link-target", "")

        link_to_redirect = f"https://aniworld.to{href_value}"
        return True, link_to_redirect
    except:
        return False, f"{anime_provider} does not provide this episode."

def fetch_episodecount(aniworld_url, aniworld_season):
    aniworld_season_url = aniworld_url + f"/staffel-{aniworld_season}"
    episode_count = 1
    aniworld_season_url_html = get(aniworld_season_url)
    soup = BeautifulSoup(aniworld_season_url_html.content, features="html.parser")
    for link in soup.findAll('a'):
        episode = str(link.get("href"))
        if "/staffel-{}/episode-{}".format(aniworld_season, episode_count) in episode:
            episode_count = episode_count + 1
    return episode_count - 1

def fetch_seasoncount(aniworld_url):
    aniworld_seasoncount = 1
    aniworld_url_html = get(aniworld_url)
    soup = BeautifulSoup(aniworld_url_html.content, features="html.parser")
    for link in soup.findAll('a'):
        seasons = str(link.get("href"))
        if "/staffel-{}".format(aniworld_seasoncount) in seasons:
            aniworld_seasoncount += 1
    return aniworld_seasoncount - 1

def download_aniworld(anime_name, anime_language, output_path, anime_provider, dos_waitcount, dos_activecount, dos_activecount_ffmpeg, debug_passed):
    global debug
    global log_output_path
    global log_anime_name
    global log_aniworld_total_episodes
    debug = debug_passed
    log_output_path = output_path
    log_anime_name = anime_name
    anime_name = anime_name.lower().replace(" ", "-")
    aniworld_url = f"https://aniworld.to/anime/stream/{anime_name}"
    if anime_language.lower() == "deutsch":
        anime_language = "Deutsch"
    aniworld_response = get(aniworld_url)

    if aniworld_response.status_code != 200:
        log_error(f"Web response was not 200. Status Code: {aniworld_response.status_code}")
        return False

    aniworld_seasons = fetch_seasoncount(aniworld_url=aniworld_url)

    if aniworld_seasons == 0:
        log_error(f"Anime {anime_name.replace('-', ' ').title()} not found.")
        return False
    if anime_provider == "VOE":
        log_info(f"Anime has {aniworld_seasons} season(s).")

    if not exists(f"{output_path}/{anime_name.replace('-', ' ').title()}"):
        mkdir(f"{output_path}/{anime_name.replace('-', ' ').title()}")

    for i in range(1, aniworld_seasons + 1):
        if not exists(f"{output_path}/{anime_name.replace('-', ' ').title()}/Season {str(i).zfill(2)}"):
            mkdir(f"{output_path}/{anime_name.replace('-', ' ').title()}/Season {str(i).zfill(2)}")

    aniworld_seasons_and_episodes = []
    aniworld_total_episodes = 0

    for aniworld_season in range(aniworld_seasons):
        aniworld_season += 1
        aniworld_season_episodes = fetch_episodecount(aniworld_url=aniworld_url, aniworld_season=aniworld_season)
        aniworld_seasons_and_episodes.append(f"{aniworld_season}_{aniworld_season_episodes}")
        aniworld_total_episodes += aniworld_season_episodes
    log_aniworld_total_episodes = aniworld_total_episodes

    dos_count = 0

    language_failed = 0
    for aniworld_season_and_episode in aniworld_seasons_and_episodes:
        aniworld_season = int(aniworld_season_and_episode.split("_")[0])
        aniworld_episodes = int(aniworld_season_and_episode.split("_")[1])

        for aniworld_episode in range(aniworld_episodes):
            aniworld_episode += 1

            anime_name_full = f"{anime_name} - s{aniworld_season:02}e{aniworld_episode:02} - {anime_language}.mp4"
            output_filename = f"{output_path}/{anime_name.replace('-', ' ').title()}/Season {str(aniworld_season).zfill(2)}/{anime_name} - s{aniworld_season:02}e{aniworld_episode:02} - {anime_language}.mp4"

            if exists(output_filename):
                print(f"ALREADY EXISTS {output_filename}")
                continue
            else:
                dos_count += 1
                if dos_count > dos_waitcount:
                    sleep(60)
                    dos_count = 1
            aniworld_season_and_episode_url = f"{aniworld_url}/staffel-{aniworld_season}/episode-{aniworld_episode}"
            redirect_status, redirect_url = fetch_redirect_url(aniworld_season_and_episode_url=aniworld_season_and_episode_url, anime_language=anime_language, anime_provider=anime_provider)

            if redirect_status:
                cache_url = fetch_cache_url(url=redirect_url, provider=anime_provider, failed=False)
                log_debug(f"Found cache URL for {anime_name_full}. URL: {cache_url}\n")
                if cache_url is None:
                    log_debug(f"{anime_provider} -> Can't find cache URL for {anime_name_full}.\n")
                    continue

                log_info(f"{anime_provider} -> Starting download of {anime_name_full}.\n")

                if anime_provider == "VOE":
                    while active_count() > dos_activecount_ffmpeg:
                        log_debug(f"FFmpeg active count of {dos_activecount_ffmpeg-2} reached. Sleeping for 15 seconds...\n")
                        sleep(15)
                    Thread(target=download_voe, args=(cache_url, output_filename, anime_name_full)).start()
                else:
                    while active_count() > dos_activecount:
                        log_debug(f"Direct download active count of {dos_activecount-2} reached. Sleeping for 15 seconds...\n")
                        sleep(15)
                    Thread(target=download_other, args=(cache_url, output_filename, anime_provider, anime_name_full)).start()
            else:
                if " does not provide this episode." in redirect_url:
                    log_debug(f"{anime_provider} -> {anime_name_full} not provided.\n")
                elif anime_provider == "VOE":
                    language_failed += 1
                    log_error(f"{anime_provider} -> Language '{anime_language}' for {anime_name_full} is invalid. Languages: {list(redirect_url.keys())}.\n")
                    if language_failed == aniworld_total_episodes:
                        return False

    while True:
        threads_string = ""
        for thread in enumerate():
            threads_string += thread.name
        if not "download_voe" in threads_string and not "download_other" in threads_string:
            break
        log_info(f'{anime_provider} -> {threads_string.count("download_voe") + threads_string.count("download_other")} download(s) still running...\n')
        sleep(30)


    if anime_provider == "VOE":
        download_aniworld(anime_name=anime_name, anime_language=anime_language, output_path=output_path, anime_provider="Streamtape", dos_waitcount=dos_waitcount, dos_activecount=dos_activecount, debug_passed=debug_passed, dos_activecount_ffmpeg=dos_activecount_ffmpeg)
        return
    elif anime_provider == "Streamtape":
        download_aniworld(anime_name=anime_name, anime_language=anime_language, output_path=output_path, anime_provider="Vidoza", dos_waitcount=dos_waitcount, dos_activecount=dos_activecount, debug_passed=debug_passed, dos_activecount_ffmpeg=dos_activecount_ffmpeg)
        return

    # count files in directory and subdirectories
    file_count = 0
    for path, dirs, files in walk(f"{output_path}/{anime_name.replace('-', ' ').title()}"):
        for i in files:
            file_count += 1

    log_success(f"Finished download of {anime_name.replace('-', ' ').title()}. Episodes: {file_count}/{aniworld_total_episodes}.")
    return True

def auto_add_animes(media_folder, plex_url, x_plex_token, media_folder_srv, jelly_url, jelly_token, hour_passed, minute_passed):
    while True:
        now = datetime.now()
        # Calculate the next 8 PM
        next_run = now.replace(hour=hour_passed, minute=minute_passed, second=0, microsecond=0)

        # If it's already past 8 PM today, schedule for tomorrow
        if now >= next_run:
            next_run += timedelta(days=1)

        # Sleep until the next run time
        sleep_time = (next_run - now).total_seconds()
        log_info(f"Next auto-add run is scheduled for {next_run.strftime('%d-%m-%Y %H:%M')}.")
        sleep(sleep_time)

        # Execute the given function
        for anime_name in listdir(media_folder):
            anime_name_aniworld = anime_name.replace(' ', '-').lower()
            anime_language = listdir(f"{media_folder}/{anime_name}/Season 01")[0].split(" - ")[2].replace(".mp4", "")
            log_info(f"Starting auto-add for {anime_name.title().replace('-', ' ')}...")
            download_aniworld(anime_name_aniworld, anime_language, media_folder, "VOE", 5, 4, 3, False)

        plex_api.plex_refresh(media_folder_srv=media_folder_srv, plex_url=plex_url, x_plex_token=x_plex_token)
        jelly_api.jelly_refresh(jelly_url, jelly_token)
        log_info(f"Libraries are refreshing...")
