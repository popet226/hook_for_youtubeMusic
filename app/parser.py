"""Разбор ответа browse: превращает JSON YouTube Music в наши поля.

Модуль не ходит в сеть. Его можно проверять на сохранённых ответах и на тестовых данных.
Правило: каждое поле берётся своим путём. Если пути нет, поле равно None. Ответ не падает.
"""
import re
from typing import Any, Iterator

from app.errors import PlaylistNotFound

CATALOG_TRACK_TYPES = {"MUSIC_VIDEO_TYPE_ATV"}
OFFICIAL_VIDEO_TYPES = {"MUSIC_VIDEO_TYPE_OMV", "MUSIC_VIDEO_TYPE_OFFICIAL_SOURCE_MUSIC"}
COUNT_PATTERN = re.compile(r"^([\d.,\s]+)\s+(?:songs?|tracks?|videos?)$")


def walk(node: Any) -> Iterator[tuple[str, Any]]:
    """Обходит JSON рекурсивно. Отдаёт пары (ключ, значение) для всех словарей внутри."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def first(node: Any, wanted_key: str) -> Any:
    """Первое значение ключа wanted_key внутри node. Если ключа нет, возвращает None."""
    for key, value in walk(node):
        if key == wanted_key:
            return value
    return None


def dig(node: Any, *path: Any) -> Any:
    """Идёт по пути из ключей и номеров. Если пути нет, возвращает None."""
    for step in path:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def _parents_with_key(node: Any, wanted_key: str) -> Iterator[dict]:
    """Находит словари, в которых есть ключ wanted_key."""
    if isinstance(node, dict):
        if wanted_key in node:
            yield node
        for value in node.values():
            yield from _parents_with_key(value, wanted_key)
    elif isinstance(node, list):
        for value in node:
            yield from _parents_with_key(value, wanted_key)


def text_of_runs(runs: list[dict] | None) -> str:
    """Склеивает текст из частей (runs). Части разделены запятыми, амперсандами и т. п."""
    return "".join(run.get("text", "") for run in runs or [])


def run_browse_id(run: dict) -> str | None:
    return dig(run, "navigationEndpoint", "browseEndpoint", "browseId")


def best_cover(thumbnails: list[dict] | None) -> dict | None:
    """Выбирает обложку с наибольшей шириной."""
    if not thumbnails:
        return None
    best = max(thumbnails, key=lambda t: t.get("width") or 0)
    if not best.get("url"):
        return None
    return {"url": best["url"], "width": best.get("width"), "height": best.get("height")}


def parse_duration(text: str | None) -> int | None:
    """'2:38' -> 158, '1:02:03' -> 3723. Если формат другой, возвращает None."""
    if not text:
        return None
    parts = text.strip().split(":")
    if len(parts) > 3 or not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def kind_of(video_type: str | None) -> str | None:
    """Тип позиции для ленты: аудиотрек каталога, официальный клип или обычное видео."""
    if video_type is None:
        return None
    if video_type in CATALOG_TRACK_TYPES:
        return "track"
    if video_type in OFFICIAL_VIDEO_TYPES:
        return "official_video"
    return "video"  # UGC, PODCAST_EPISODE и любые неизвестные типы


def find_items(page: dict) -> list[dict]:
    """Все записи списка (треки) на странице ответа."""
    return [value for key, value in walk(page) if key == "musicResponsiveListItemRenderer"]


def find_continuation_token(page: dict) -> str | None:
    """Токен следующей страницы. На последней странице его нет."""
    for key, value in walk(page):
        if key == "continuationItemRenderer":
            return first(value, "token")
    return None


def _flex_runs(item: dict, index: int) -> list[dict]:
    columns = item.get("flexColumns") or []
    if index >= len(columns):
        return []
    return dig(columns[index], "musicResponsiveListItemFlexColumnRenderer", "text", "runs") or []


def parse_track(item: dict) -> dict | None:
    """Одна запись списка -> словарь с полями трека. Запись без videoId пропускаем."""
    video_id = dig(item, "playlistItemData", "videoId") or first(item, "videoId")
    if not video_id:
        return None

    artist_runs = _flex_runs(item, 1)
    artists = [{"name": run.get("text", ""), "id": run_browse_id(run)} for run in artist_runs if run_browse_id(run)]

    # Третья колонка не всегда альбом: у выпусков подкастов там дата.
    # Альбом узнаём по ID: у страницы альбома он начинается с MPRE.
    album = None
    for run in _flex_runs(item, 2):
        browse_id = run_browse_id(run)
        if browse_id and browse_id.startswith("MPRE"):
            album = {"name": run.get("text", ""), "id": browse_id}
            break

    video_type = first(item, "musicVideoType")
    duration_text = dig(item, "fixedColumns", 0, "musicResponsiveListItemFixedColumnRenderer", "text", "runs", 0, "text")

    return {
        "id": video_id,
        "title": text_of_runs(_flex_runs(item, 0)) or None,
        "artist": text_of_runs(artist_runs) or None,
        "artists": artists,
        "album": album,
        "duration_seconds": parse_duration(duration_text),
        "cover": best_cover(dig(item, "thumbnail", "musicThumbnailRenderer", "thumbnail", "thumbnails")),
        "kind": kind_of(video_type),
        "video_type": video_type,
    }


def parse_header(page: dict) -> dict | None:
    """Шапка плейлиста. Ищем блок по ключу secondSubtitle: в нём лежит число треков.

    Пути для названия (title), владельца (straplineTextOne) и обложки взяты по аналогии
    с другими ответами YouTube Music. Если пути неверны, поля будут None.
    """
    header = next(_parents_with_key(page, "secondSubtitle"), None)
    if header is None:
        return None

    track_count = None
    for run in dig(header, "secondSubtitle", "runs") or []:
        match = COUNT_PATTERN.match(run.get("text", ""))
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            track_count = int(digits) if digits else None
            break

    return {
        "title": text_of_runs(dig(header, "title", "runs")) or None,
        "cover": best_cover(first(header, "thumbnails")),
        "owner": parse_owner(header),
        "track_count": track_count,
    }


def parse_owner(header: dict) -> dict | None:
    """Владелец плейлиста.

    В реальном ответе он лежит в блоке facepile (аватар владельца). Оттуда берём ID канала (browseId
    вида UC...) и имя (ключ content). Оба пути проверены на ответах check_links.py: имя и ID пришли
    для обычных плейлистов. Запасной вариант: блок straplineTextOne (на реальных данных не проверен).
    """
    facepile = header.get("facepile")
    if facepile:
        name = first(facepile, "content")
        owner_id = first(facepile, "browseId")
        name = name if isinstance(name, str) and name else None
        if name or owner_id:
            return {"name": name, "id": owner_id}

    strapline = dig(header, "straplineTextOne", "runs") or []
    if strapline:
        return {
            "name": text_of_runs(strapline) or None,
            "id": next((run_browse_id(run) for run in strapline if run_browse_id(run)), None),
        }
    return None


def header_from_album(tracks: list[dict]) -> dict:
    """Запасная шапка для плейлиста, у которого в ответе шапки нет.

    Так выглядит автоплейлист альбома (OLAK5uy_...): в ответе только список треков, без названия.
    Если у всех треков один и тот же альбом, называем плейлист по альбому и берём обложку первого трека.
    Владельца такого плейлиста нет: это не плейлист пользователя. Если альбомы разные, возвращаем пустую шапку.
    """
    albums = {track["album"]["id"]: track["album"]["name"] for track in tracks if track["album"]}
    all_have_album = tracks and all(track["album"] for track in tracks)
    if all_have_album and len(albums) == 1:
        return {"title": next(iter(albums.values())), "cover": tracks[0]["cover"], "owner": None, "track_count": None}
    return {}


def build_playlist(playlist_id: str, pages: list[dict], truncated: bool) -> dict:
    """Собирает ответ сервиса из страниц ответа browse."""
    header = parse_header(pages[0])

    tracks = []
    for page in pages:
        for item in find_items(page):
            track = parse_track(item)
            if track:
                tracks.append(track)

    # Нет ни шапки, ни треков: так выглядит приватный или несуществующий плейлист
    if header is None and not tracks:
        raise PlaylistNotFound()

    if header is None:
        header = header_from_album(tracks)

    # Числа из шапки может не быть (так у автоплейлиста альбома). Если список загружен целиком,
    # берём его длину. Если список обрезан, честнее вернуть null, чем неверное число.
    track_count = header.get("track_count")
    if track_count is None and not truncated:
        track_count = len(tracks)

    return {
        "id": playlist_id,
        "url": f"https://music.youtube.com/playlist?list={playlist_id}",
        "title": header.get("title"),
        "cover": header.get("cover"),
        "owner": header.get("owner"),
        "track_count": track_count,
        "tracks": tracks,
        "truncated": truncated,
    }