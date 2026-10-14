"""

Что делает скрипт:
  Берёт ключ API и версию клиента со страницы плейлиста.
  Делает запрос browse и измеряет размер и время.
  Разбирает JSON: считает записи списка и ищет токен дозагрузки.

"""
import gzip
import json
import re
import sys
import time
from collections import Counter

import requests

if len(sys.argv) < 2:
    sys.exit("Укажите ID плейлиста. Пример: python explore_response.py PLHHFkCbk5F28")

PLAYLIST_ID = sys.argv[1]
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
BROWSE_URL = "https://music.youtube.com/youtubei/v1/browse"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}


def walk(node, path=""):
    """Обходит JSON рекурсивно.

    Для каждого элемента отдаёт три значения: путь, имя ключа, значение.
    Мы ищем нужные ключи по имени, потому что точной структуры ответа не знаем.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            current = f"{path}.{key}"
            yield current, key, value
            yield from walk(value, current)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{path}[{index}]")


def first_value(node, wanted_key):
    """Возвращает первое значение ключа wanted_key внутри node. Если ключа нет, возвращает None."""
    for _path, key, value in walk(node):
        if key == wanted_key:
            return value
    return None


session = requests.Session()
session.headers.update(HEADERS)

html = session.get(PAGE_URL, timeout=15).text
key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
version_match = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', html)
if not key_match or not version_match:
    sys.exit("Ключ API или версия клиента не найдены на странице.")
api_key = key_match.group(1)
client_version = version_match.group(1)

body = {
    "context": {"client": {"clientName": "WEB_REMIX", "clientVersion": client_version, "hl": "en"}},
    "browseId": "VL" + PLAYLIST_ID,  # для плейлиста к его ID добавляется префикс VL
}

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

print(f"status={response.status_code} compressed={len(raw)} B raw={len(text)} B time={elapsed:.2f} s")
if response.status_code != 200:
    sys.exit(f"Запрос не удался. Начало ответа: {text[:300]}")

data = json.loads(text)

items = Counter()        
continuations = Counter() 
video_ids = []

for path, key, value in walk(data):
    generic_path = re.sub(r"\[\d+\]", "[]", path)
    if key == "musicResponsiveListItemRenderer":
        items[generic_path] += 1
        video_ids.append(first_value(value, "videoId"))
    if "ontinuation" in key:
        continuations[generic_path] += 1

print("\nЗаписи списка (musicResponsiveListItemRenderer):")
for path, count in items.most_common(5):
    print(f"  {count:4d}  {path}")

known_ids = [v for v in video_ids if v]
print(f"\nvideoId найден в {len(known_ids)} записях, уникальных: {len(set(known_ids))}")
print("Первые 3 videoId:", known_ids[:3])

print("\nКлючи со словом 'continuation':")
for path, count in continuations.most_common(10):
    print(f"  {count:4d}  {path}")

with open(f"response_{PLAYLIST_ID}.json", "w", encoding="utf-8") as f:
    f.write(text)
print(f"\nОтвет сохранён в response_{PLAYLIST_ID}.json")