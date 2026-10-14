import re
import time
import requests

PLAYLIST_ID = "PLHHFkCbk5F28"
PAGE_URL = f"https://music.youtube.com/playlist?list={PLAYLIST_ID}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

html = requests.get(PAGE_URL, headers=HEADERS, timeout=15).text

def find(name):
    m = re.search(r'"%s":"([^"]+)"' % name, html)
    return m.group(1) if m else None

api_key = find("INNERTUBE_API_KEY")
client_version = find("INNERTUBE_CONTEXT_CLIENT_VERSION")
print("api key found:", bool(api_key))
print("client version:", client_version)

body = {
    "context": {
        "client": {
            "clientName": "WEB_REMIX",
            "clientVersion": client_version,
            "hl": "en",
        }
    },
    "browseId": "VL" + PLAYLIST_ID,
}
headers = {**HEADERS, "Origin": "https://music.youtube.com", "Content-Type": "application/json"}

t = time.perf_counter()
r = requests.post(
    "https://music.youtube.com/youtubei/v1/browse",
    params={"key": api_key, "prettyPrint": "false"},
    json=body, headers=headers, stream=True, timeout=15,
)
raw = r.raw.read(decode_content=False)
total = time.perf_counter() - t

print("status:", r.status_code)
print("compressed bytes:", len(raw))
print("total, s:", round(total, 2))

import gzip, json
text = gzip.decompress(raw).decode() if r.headers.get("content-encoding") == "gzip" else raw.decode()
print("uncompressed bytes:", len(text))
print("One Step in response:", "One Step" in text)
print("continuation in response:", "continuation" in text)

with open("browse_response.json", "w", encoding="utf-8") as f:
    f.write(text)