import time
import requests

URL = "https://music.youtube.com/playlist?list=PLHHFkCbk5F28"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

for i in range(5):
    t = time.perf_counter()
    r = requests.get(URL, headers=HEADERS, stream=True, timeout=15)
    raw = r.raw.read(decode_content=False)
    total = time.perf_counter() - t
    print(f"run {i}: status={r.status_code} compressed={len(raw)} B total={total:.2f} s")
    time.sleep(2)