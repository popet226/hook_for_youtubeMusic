"""
Что делает скрипт:
   Берёт ключ API и версию клиента со страницы плейлиста.
   Отправляет запросы browse ступенями: каждая ступень держит заданную частоту
     (запросов в секунду) STAGE_SECONDS секунд.
   После каждой ступени печатает статусы, время ответа и трафик.
   Останавливается при первом ответе, который не равен 200, или при сетевой ошибке.
"""
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter

PLAYLIST_ID = sys.argv[1] if len(sys.argv) > 1 else "PLHHFkCbk5F28"
RATES = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [1, 2, 5, 10]
STAGE_SECONDS = int(sys.argv[3]) if len(sys.argv) > 3 else 15   
PAUSE_BETWEEN = 10   
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
BROWSE_URL = "https://music.youtube.com/youtubei/v1/browse"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

session = requests.Session()
session.mount("https://", HTTPAdapter(pool_maxsize=64)) 
session.headers.update(HEADERS)

html = session.get(PAGE_URL, timeout=15).text
key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
version_match = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', html)
if not key_match or not version_match:
    sys.exit("Ключ API или версия клиента не найдены.")

BODY = {
    "context": {"client": {"clientName": "WEB_REMIX", "clientVersion": version_match.group(1), "hl": "en"}},
    "browseId": "VL" + PLAYLIST_ID,
}
PARAMS = {"key": key_match.group(1), "prettyPrint": "false"}

bad_response = threading.Event()  


def one_request():
    """Отправляет один запрос browse. Возвращает словарь с результатом."""
    start = time.perf_counter()
    try:
        response = session.post(
            BROWSE_URL,
            params=PARAMS,
            json=BODY,
            headers={"Origin": "https://music.youtube.com"},
            stream=True,
            timeout=20,
        )
        raw = response.raw.read(decode_content=False)  
        response.close()
        result = {
            "status": response.status_code,
            "bytes": len(raw),
            "time": time.perf_counter() - start,
            "retry_after": response.headers.get("retry-after"),
        }
    except requests.RequestException as error:
        result = {"status": type(error).__name__, "bytes": 0, "time": time.perf_counter() - start, "retry_after": None}

    if result["status"] != 200:
        bad_response.set() 
    return result


total_sent = 0
with ThreadPoolExecutor(max_workers=64) as pool:
    for rate in RATES:
        planned = rate * STAGE_SECONDS
        futures = []
        stage_start = time.perf_counter()

        for i in range(planned):
            if bad_response.is_set():
                break
            wait = stage_start + i / rate - time.perf_counter()  
            if wait > 0:
                time.sleep(wait)
            futures.append(pool.submit(one_request))

        results = [f.result() for f in futures]
        elapsed = time.perf_counter() - stage_start
        total_sent += len(results)

        statuses = Counter(r["status"] for r in results)
        times = sorted(r["time"] for r in results if r["status"] == 200)
        p50 = times[len(times) // 2] if times else 0
        p95 = times[int(0.95 * (len(times) - 1))] if times else 0
        traffic = sum(r["bytes"] for r in results)
        print(
            f"{rate:3d} запр/с: отправлено={len(results)} из {planned}, "
            f"реальная частота={len(results) / elapsed:.1f}/с, статусы={dict(statuses)}, "
            f"время p50={p50:.2f} с p95={p95:.2f} с, трафик={traffic} B"
        )

        if bad_response.is_set():
            bad = next(r for r in results if r["status"] != 200)
            print(f"СТОП на ступени {rate} запр/с. Первый плохой ответ: status={bad['status']}, retry-after={bad['retry_after']}")
            break
        time.sleep(PAUSE_BETWEEN)

print(f"\nВсего отправлено запросов: {total_sent}")