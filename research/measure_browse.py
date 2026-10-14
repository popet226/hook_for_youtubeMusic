import gzip
import re
import sys
import time

import requests

PLAYLIST_ID = sys.argv[1] if len(sys.argv) > 1 else "PLHHFkCbk5F28"
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

s = requests.Session()
s.headers.update(HEADERS)

html = s.get(PAGE_URL, timeout=15).text
api_key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html).group(1)
client_version = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', html).group(1)

body = {
    "context": {"client": {"clientName": "WEB_REMIX", "clientVersion": client_version, "hl": "en"}},
    "browseId": "VL" + PLAYLIST_ID,
}

for i in range(5):
    t = time.perf_counter()
    r = s.post(
        "https://music.youtube.com/youtubei/v1/browse",
        params={"key": api_key, "prettyPrint": "false"},
        json=body,
        headers={"Origin": "https://music.youtube.com"},
        stream=True,
        timeout=15,
    )
    raw = r.raw.read(decode_content=False)
    total = time.perf_counter() - t
    text = gzip.decompress(raw).decode() if r.headers.get("content-encoding") == "gzip" else raw.decode()
    print(
        f"run {i}: status={r.status_code} compressed={len(raw)} B "
        f"raw={len(text)} B total={total:.2f} s continuation={'continuation' in text}"
    )
    time.sleep(2)