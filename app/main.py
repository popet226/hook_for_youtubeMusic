"""HTTP-ручка сервиса: принимает ссылку на плейлист YouTube Music, возвращает нормализованный JSON.

Запуск из корня репозитория:
  uvicorn app.main:app
Документация и пробные запросы: http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.client import YouTubeMusicClient
from app.errors import LinkError, PlaylistNotFound, UpstreamError
from app.links import parse_playlist_link
from app.models import Playlist, PlaylistRequest
from app.parser import build_playlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = YouTubeMusicClient()
    yield
    await app.state.client.aclose()


app = FastAPI(title="SOUNDGRAM: плейлисты YouTube Music", lifespan=lifespan)


def error_response(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    """Все ошибки сервиса имеют один вид: {"error": {"code": ..., "message": ...}}."""
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


@app.exception_handler(LinkError)
async def link_error_handler(request: Request, error: LinkError):
    return error_response(422, error.code, error.message)


@app.exception_handler(PlaylistNotFound)
async def not_found_handler(request: Request, error: PlaylistNotFound):
    return error_response(404, "playlist_not_found", "Плейлист не найден или он приватный")


@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, error: UpstreamError):
    if error.status == 429:
        headers = {"Retry-After": error.retry_after} if error.retry_after else None
        return error_response(429, "upstream_rate_limited", "YouTube Music ограничил частоту запросов", headers)
    return error_response(502, "upstream_error", error.message)


@app.post("/playlist", response_model=Playlist, summary="Данные плейлиста по ссылке")
async def get_playlist(body: PlaylistRequest, request: Request):
    """Принимает ссылку на плейлист, возвращает данные плейлиста и треков.

    Ошибки: 422 (ссылка не подходит), 404 (плейлист не найден или приватный),
    429 (YouTube Music ограничил частоту), 502 (сбой YouTube Music или сети).
    """
    playlist_id = parse_playlist_link(body.url)
    pages, truncated = await request.app.state.client.fetch_playlist(playlist_id)
    return build_playlist(playlist_id, pages, truncated)


@app.get("/health", summary="Проверка, что сервис работает")
async def health():
    return {"status": "ok"}
