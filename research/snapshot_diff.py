"""

Что делает скрипт:
  Загружает все страницы плейлиста (как explore_pages.py).
  Сравнивает список videoId с прошлым снимком, если он есть.
   Показывает, что добавилось и что пропало, и на какой позиции.
  Сохраняет новый снимок в research/snapshots/<ID>.json.

"""
import gzip
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

if len(sys.argv) < 2:
    sys.exit("Укажите ID плейлиста.")

PLAYLIST_ID = sys.argv[1]
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
BROWSE_URL = "https://music.youtube.com/youtubei/v1/browse"
MAX_PAGES = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
SNAPSHOT_FILE = SNAPSHOT_DIR / f"{PLAYLIST_ID}.json"


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
    """Первое значение ключа wanted_key внутри node или None."""
    for key, value in walk(node):
        if key == wanted_key:
            return value
    return None


def find_track_count(data):
    """Число треков из строки secondSubtitle в шапке плейлиста, например "22 tracks".

    Искать число по всему тексту ответа нельзя: описание плейлиста пишет владелец,
    и в нём может стоять любое число.
    """
    for key, value in walk(data):
        if key == "secondSubtitle" and isinstance(value, dict):
            for run in value.get("runs", []):
                text = run.get("text", "")
                if re.fullmatch(r"\d[\d,.\s]*\s(?:songs?|tracks?|videos?)", text):
                    return text
    return None


def post_browse(session, api_key, body):
    """Один запрос browse. Возвращает статус, сжатый размер и текст ответа."""
    response = session.post(
        BROWSE_URL,
        params={"key": api_key, "prettyPrint": "false"},
        json=body,
        headers={"Origin": "https://music.youtube.com"},
        stream=True,
        timeout=30,
    )
    raw = response.raw.read(decode_content=False)
    if response.headers.get("content-encoding") == "gzip":
        text = gzip.decompress(raw).decode()
    else:
        text = raw.decode()
    return response.status_code, len(raw), text


def fetch_playlist(session, api_key, context):
    """Загружает все страницы плейлиста.

    Возвращает: список videoId, строку из заголовка, число запросов, трафик в байтах.
    """
    body = {"context": context, "browseId": "VL" + PLAYLIST_ID}
    ids, header = [], None
    requests_made, total_bytes = 0, 0

    for _ in range(MAX_PAGES):
        status, compressed, text = post_browse(session, api_key, body)
        requests_made += 1
        total_bytes += compressed
        if status != 200:
            sys.exit(f"Запрос не удался: status={status}. Начало ответа: {text[:300]}")

        data = json.loads(text)

        if requests_made == 1:  # число треков берём только из первой страницы
            header = find_track_count(data)

        for key, value in walk(data):
            if key == "musicResponsiveListItemRenderer":
                video_id = first_value(value, "videoId")
                if video_id:
                    ids.append(video_id)

        token = None
        for key, value in walk(data):
            if key == "continuationItemRenderer":
                token = first_value(value, "token")
                break
        if not token:
            break
        body = {"context": context, "continuation": token}
        time.sleep(1)

    return ids, header, requests_made, total_bytes


session = requests.Session()
session.headers.update(HEADERS)

html = session.get(PAGE_URL, timeout=15).text
key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
version_match = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', html)
if not key_match or not version_match:
    sys.exit("Ключ API или версия клиента не найдены.")

context = {"client": {"clientName": "WEB_REMIX", "clientVersion": version_match.group(1), "hl": "en"}}
ids, header, requests_made, total_bytes = fetch_playlist(session, key_match.group(1), context)
print(f"Загружено: запросов={requests_made}, треков={len(ids)}, заголовок={header}, трафик={total_bytes} B")

if SNAPSHOT_FILE.exists():
    old = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    old_ids = old["ids"]
    old_set, new_set = set(old_ids), set(ids)

    added = [(i + 1, v) for i, v in enumerate(ids) if v not in old_set]
    removed = [(i + 1, v) for i, v in enumerate(old_ids) if v not in new_set]
    # Порядок общих треков: сравниваем два списка без добавленных и удалённых
    same_order = [v for v in ids if v in old_set] == [v for v in old_ids if v in new_set]

    print(f"Прошлый снимок: {old['time']}, заголовок={old['header']}, треков={len(old_ids)}")
    print(f"Сейчас: заголовок={header}, треков={len(ids)}")
    print(f"Добавлено: {len(added)}")
    for position, video_id in added:
        print(f"  позиция {position} из {len(ids)}: {video_id}")
    print(f"Удалено: {len(removed)}")
    for position, video_id in removed:
        print(f"  была позиция {position} из {len(old_ids)}: {video_id}")
    print("Порядок общих треков:", "не изменился" if same_order else "изменился")
    if not added and not removed and same_order:
        print("Изменений нет.")
else:
    print("Прошлого снимка нет. Сохраняю первый.")

SNAPSHOT_DIR.mkdir(exist_ok=True)
SNAPSHOT_FILE.write_text(
    json.dumps(
        {"time": datetime.now().isoformat(timespec="seconds"), "header": header, "ids": ids},
        ensure_ascii=False,
    ),
    encoding="utf-8",
)