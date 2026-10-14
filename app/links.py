"""Разбор ссылки: из любой поддерживаемой формы получаем ID плейлиста.

Поддерживаемые формы:
  music.youtube.com/playlist?list=...          (основная)
  youtube.com/playlist?list=...                (тот же плейлист на обычном YouTube)
  music.youtube.com/browse/VL...               (внутренняя; ID идёт после префикса VL)
  любая из них с лишними параметрами (&si=..., &start_radio=...)
  music.youtube.com/playlist?list=OLAK5uy_...  (автоплейлист альбома)
  watch?v=...&list=...                         (видео внутри плейлиста)
"""
import re
from urllib.parse import parse_qs, urlparse

from app.errors import LinkError

YOUTUBE_HOSTS = {"music.youtube.com", "www.youtube.com", "youtube.com", "m.youtube.com"}
PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,}$")


def parse_playlist_link(url: str) -> str:
    """Возвращает ID плейлиста или бросает LinkError с понятным кодом."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LinkError("invalid_url", "Нужна полная ссылка, которая начинается с https://")

    if parsed.hostname.lower() not in YOUTUBE_HOSTS:
        raise LinkError("unsupported_host", "Поддерживаются только ссылки music.youtube.com и youtube.com")

    path = parsed.path.rstrip("/")
    list_id = parse_qs(parsed.query).get("list", [None])[0]

    if path.startswith("/browse/"):
        browse_id = path[len("/browse/"):]
        if browse_id.startswith("VL") and len(browse_id) > 2:
            return _check_playlist_id(browse_id[2:])
        raise LinkError("not_a_playlist", "Это страница альбома или артиста, а не плейлист")

    if path in ("/playlist", "/watch"):
        if list_id:
            return _check_playlist_id(list_id)
        if path == "/watch":
            raise LinkError("not_a_playlist", "Это ссылка на отдельное видео или трек, в ней нет плейлиста")
        raise LinkError("not_a_playlist", "В ссылке нет параметра list")

    if path.startswith(("/channel/", "/@", "/c/", "/user/")):
        raise LinkError("not_a_playlist", "Это страница артиста или канала, а не плейлист")

    raise LinkError("not_a_playlist", "Не удалось найти плейлист в этой ссылке")


def _check_playlist_id(playlist_id: str) -> str:
    if not PLAYLIST_ID_PATTERN.match(playlist_id):
        raise LinkError("invalid_url", "ID плейлиста содержит недопустимые символы")

    # Радио и миксы (RDAMVM..., RDEM... и др.) строятся автоматически по выбранному треку.
    # Это не плейлист пользователя: список меняется сам и не подходит для ленты.
    # Исключение: RDCLAK5uy_... это плейлисты, которые собрал сам YouTube Music.
    if playlist_id.startswith("RD") and not playlist_id.startswith("RDCLAK"):
        raise LinkError("mix_not_supported", "Радио и миксы YouTube Music не поддерживаются: список строится автоматически")

    return playlist_id
