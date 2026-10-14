"""
Прогоняет тестовые ссылки через запущенный сервис и печатает краткий итог по каждой.

Что делает скрипт:
  1. Отправляет каждую ссылку из списка LINKS в ручку POST /playlist.
  2. Для успешных ответов печатает название, число из шапки, число треков и типы позиций.
  3. Для ошибок печатает код ответа и код ошибки.

Запуск (сервис уже запущен командой: uvicorn app.main:app):
  python research/check_links.py
"""
from collections import Counter

import requests

SERVICE = "http://127.0.0.1:8000/playlist"

# Подписи и ссылки. Замените ссылки на свои, если они отличаются.
LINKS = [
    ("публичный, music.youtube.com", "https://music.youtube.com/playlist?list=PLHHFkCbk5F28"),
    ("публичный, youtube.com", "https://www.youtube.com/playlist?list=PLHHFkCbk5F28"),
    ("публичный, browse/VL", "https://music.youtube.com/browse/VLPLHHFkCbk5F28"),
    ("публичный, &si и &start_radio", "https://music.youtube.com/playlist?list=PLHHFkCbk5F28&si=abc123&start_radio=1"),
    ("по ссылке (unlisted)", "https://music.youtube.com/playlist?list=PLBOzsXvc6O_8"),
    ("приватный", "https://music.youtube.com/playlist?list=PLWDSYnHvzx_c"),
    ("большой (300+)", "https://music.youtube.com/playlist?list=PLQHlRnDg3bu-31TJgsEUy6Zn7S7KG7k4v"),
    ("недоступные видео", "https://www.youtube.com/playlist?list=PLPeBc1Wlwc-k"),
    ("пустой", "https://music.youtube.com/playlist?list=PLGqXGJRh_f34"),
    ("автоплейлист альбома", "https://music.youtube.com/playlist?list=OLAK5uy_kQ_6n09WjMicPm7moQk7m0_Jww4oB6iMQ"),
    ("артист", "https://music.youtube.com/@metallica"),
    ("отдельная песня", "https://music.youtube.com/watch?v=Z85lxckrtzg"),
    ("микс RD", "https://music.youtube.com/watch?v=kOn-HdEg6AQ&list=RDAMVMkOn-HdEg6AQ"),
    ("несуществующий ID", "https://music.youtube.com/playlist?list=PLaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
]

for label, url in LINKS:
    try:
        response = requests.post(SERVICE, json={"url": url}, timeout=120)
    except requests.RequestException as error:
        print(f"{label}: сервис не отвечает ({type(error).__name__}). Запущен ли uvicorn?")
        continue

    if response.status_code == 200:
        data = response.json()
        kinds = dict(Counter(track["kind"] for track in data["tracks"]))
        print(
            f"{label}: 200, название={data['title']!r}, владелец={data['owner']}, "
            f"обложка={(data['cover'] or {}).get('width')}, "
            f"число из шапки={data['track_count']}, треков в списке={len(data['tracks'])}, "
            f"обрезан={data['truncated']}, типы={kinds}"
        )
    else:
        try:
            error = response.json()["error"]
            print(f"{label}: {response.status_code}, код={error['code']}, сообщение={error['message']}")
        except (ValueError, KeyError):
            print(f"{label}: {response.status_code}, {response.text[:200]}")
