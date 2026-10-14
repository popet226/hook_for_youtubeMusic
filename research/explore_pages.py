"""

Что делает скрипт:

  Делает запрос browse.
  Пока в ответе есть токен дозагрузки, делает следующий запрос.
  Для каждой страницы печатает число треков, размер и время.

"""
import gzip
import json
import re
import sys
import time
from collections import Counter

import requests

if len(sys.argv) < 2:
    sys.exit("Укажите ID плейлиста.")

PLAYLIST_ID = sys.argv[1]
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
BROWSE_URL = "https://music.youtube.com/youtubei/v1/browse"
MAX_PAGES = 10  # защита: скрипт не сделает больше 10 запросов
PAUSE = 1       
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}


def walk(node):
    """Обходит JSON рекурсивно. Отдаёт пары (ключ, значение)."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def first_value(node, wanted_key):
    """Первое значение ключа wanted_key внутри node. Если ключа нет, возвращает None."""
    for key, value in walk(node):
        if key == wanted_key:
            return value
    return None

def find_item_lists(node):
    """Находит списки, в которых лежат записи треков.
    """
    if isinstance(node, dict):
        for value in node.values():
            yield from find_item_lists(value)
    elif isinstance(node, list):
        if any(isinstance(x, dict) and "musicResponsiveListItemRenderer" in x for x in node):
            yield node
        for x in node:
            yield from find_item_lists(x)

def post_browse(session, api_key, body):
    """Один запрос browse. Возвращает статус, размеры, время и текст ответа."""
    start = time.perf_counter()
    response = session.post(
        BROWSE_URL,
        params={"key": api_key, "prettyPrint": "false"},
        json=body,
        headers={"Origin": "https://music.youtube.com"},
        stream=True,
        timeout=30,
    )
    raw = response.raw.read(decode_content=False)
    elapsed = time.perf_counter() - start
    if response.headers.get("content-encoding") == "gzip":
        text = gzip.decompress(raw).decode()
    else:
        text = raw.decode()
    return response.status_code, len(raw), len(text), elapsed, text


session = requests.Session()
session.headers.update(HEADERS)

html = session.get(PAGE_URL, timeout=15).text
key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
version_match = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', html)
if not key_match or not version_match:
    sys.exit("Ключ API или версия клиента не найдены.")
api_key = key_match.group(1)

CONTEXT = {"client": {"clientName": "WEB_REMIX", "clientVersion": version_match.group(1), "hl": "en"}}

body = {"context": CONTEXT, "browseId": "VL" + PLAYLIST_ID}
all_ids = []
total_compressed = 0
requests_made = 0

for page in range(1, MAX_PAGES + 1):
    status, compressed, raw_size, elapsed, text = post_browse(session, api_key, body)
    requests_made += 1
    if status != 200:
        print(f"page {page}: status={status}. Начало ответа: {text[:300]}")
        break

    data = json.loads(text)
    total_compressed += compressed

    ids = []
    without_id = 0
    for key, value in walk(data):
        if key == "musicResponsiveListItemRenderer":
            video_id = first_value(value, "videoId")
            if video_id:
                ids.append(video_id)
            else:
                without_id += 1
                if without_id == 1:
                    print("  пример записи без videoId:", json.dumps(value, ensure_ascii=False)[:400])
    all_ids.extend(ids)

    token = None
    for key, value in walk(data):
        if key == "continuationItemRenderer":
            token = first_value(value, "token")
            break

    print(
        f"page {page}: tracks={len(ids)} without_id={without_id} compressed={compressed} B "
        f"raw={raw_size} B time={elapsed:.2f} s next={'yes' if token else 'no'}"
    )

    for item_list in find_item_lists(data):
        kinds = Counter(next(iter(x)) for x in item_list if isinstance(x, dict) and x)
        print("  состав списка:", dict(kinds))

    if page == 1:
        found = set(re.findall(r'"text":"([^"]*\d+ (?:songs?|tracks?|videos?)[^"]*)"', text))
        print("  строки с числом треков в заголовке:", sorted(found)[:5])

    if not token:
        break
    body = {"context": CONTEXT, "continuation": token}  
    time.sleep(PAUSE)  

print(
    f"\nИтого: запросов={requests_made}, треков={len(all_ids)}, "
    f"уникальных={len(set(all_ids))}, трафик со сжатием={total_compressed} B"
)