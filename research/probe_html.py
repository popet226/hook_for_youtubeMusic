import requests

URL = "https://music.youtube.com/playlist?list=PLHHFkCbk5F28"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}

r = requests.get(URL, headers=HEADERS, timeout=15)
print("status:", r.status_code)
print("final url:", r.url)
print("content-encoding:", r.headers.get("content-encoding"))
print("size without compression, bytes:", len(r.content))
print("elapsed, s:", r.elapsed.total_seconds())

with open("page.html", "w", encoding="utf-8") as f:
    f.write(r.text)

for needle in ["One Step", "KwN_f0fTHoE", "initialData", "INNERTUBE_API_KEY", "continuation"]:
    print(needle, "->", needle in r.text)