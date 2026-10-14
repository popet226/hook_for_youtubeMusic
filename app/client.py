"""Клиент YouTube Music: получает страницы плейлиста запросами browse.

Ключ API и версию клиента берём один раз со страницы плейлиста и храним в памяти.
Если YouTube Music их отклонил (статус 400 или 403), обновляем и повторяем запрос один раз.
"""
import asyncio
import re
from dataclasses import dataclass

import httpx

from app.errors import UpstreamError
from app.parser import find_continuation_token

PAGE_URL = "https://music.youtube.com/playlist?list={playlist_id}"
BROWSE_URL = "https://music.youtube.com/youtubei/v1/browse"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_PAGES = 30  # не больше 30 страниц по 100 треков
MAX_CONCURRENT_REQUESTS = 20  # не больше 20 одновременных запросов к YouTube Music


@dataclass(frozen=True)
class Config:
    api_key: str
    client_version: str


class _Rejected(Exception):
    """YouTube Music отклонил ключ или версию клиента."""

    def __init__(self, status: int):
        super().__init__(f"rejected with status {status}")
        self.status = status


class YouTubeMusicClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            headers=HEADERS,
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        self._config: Config | None = None
        self._config_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def fetch_playlist(self, playlist_id: str) -> tuple[list[dict], bool]:
        """Возвращает страницы ответа browse и признак «список обрезан по лимиту страниц»."""
        config = await self._get_config(playlist_id)
        config, first_page = await self._browse_with_refresh(config, playlist_id, {"browseId": "VL" + playlist_id})

        pages = [first_page]
        token = find_continuation_token(first_page)
        while token and len(pages) < MAX_PAGES:
            config, page = await self._browse_with_refresh(config, playlist_id, {"continuation": token})
            pages.append(page)
            token = find_continuation_token(page)

        return pages, token is not None

    async def _get_config(self, playlist_id: str, stale: Config | None = None) -> Config:
        """Отдаёт сохранённые настройки. Скачивает заново, если их нет или они устарели (stale)."""
        if self._config is not None and self._config is not stale:
            return self._config
        async with self._config_lock:
            # Пока мы ждали замок, другая задача могла уже обновить настройки
            if self._config is not None and self._config is not stale:
                return self._config
            self._config = await self._download_config(playlist_id)
            return self._config

    async def _download_config(self, playlist_id: str) -> Config:
        try:
            response = await self._http.get(PAGE_URL.format(playlist_id=playlist_id))
        except httpx.HTTPError as error:
            raise UpstreamError(f"Сетевая ошибка: {type(error).__name__}") from error

        if response.status_code != 200:
            raise UpstreamError("Страница плейлиста недоступна", response.status_code, response.headers.get("retry-after"))

        key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', response.text)
        version = re.search(r'"INNERTUBE_CONTEXT_CLIENT_VERSION":"([^"]+)"', response.text)
        if not key or not version:
            raise UpstreamError("Ключ API не найден на странице. Возможно, YouTube Music изменил страницу")
        return Config(key.group(1), version.group(1))

    async def _browse_with_refresh(self, config: Config, playlist_id: str, payload: dict) -> tuple[Config, dict]:
        try:
            return config, await self._browse(config, payload)
        except _Rejected:
            config = await self._get_config(playlist_id, stale=config)
            try:
                return config, await self._browse(config, payload)
            except _Rejected as error:
                raise UpstreamError("YouTube Music отклонил запрос", error.status) from error

    async def _browse(self, config: Config, payload: dict) -> dict:
        body = {
            "context": {"client": {"clientName": "WEB_REMIX", "clientVersion": config.client_version, "hl": "en"}},
            **payload,
        }
        async with self._slots:
            try:
                response = await self._http.post(
                    BROWSE_URL,
                    params={"key": config.api_key, "prettyPrint": "false"},
                    json=body,
                    headers={"Origin": "https://music.youtube.com"},
                )
            except httpx.HTTPError as error:
                raise UpstreamError(f"Сетевая ошибка: {type(error).__name__}") from error

        if response.status_code in (400, 403):
            raise _Rejected(response.status_code)
        if response.status_code != 200:
            raise UpstreamError("Запрос browse не удался", response.status_code, response.headers.get("retry-after"))
        try:
            return response.json()
        except ValueError as error:
            raise UpstreamError("Ответ browse не является JSON") from error
