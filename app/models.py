"""Модели запроса и ответа. По ним FastAPI проверяет ответ и строит документацию (/docs)."""
from typing import Literal

from pydantic import BaseModel, Field


class PlaylistRequest(BaseModel):
    url: str = Field(description="Ссылка на плейлист YouTube Music", examples=["https://music.youtube.com/playlist?list=PLHHFkCbk5F28"])


class Cover(BaseModel):
    url: str
    width: int | None = None
    height: int | None = None


class Person(BaseModel):
    """Артист, канал или владелец плейлиста. Имени может не быть: тогда есть только ID канала."""
    name: str | None = None
    id: str | None = None


class Album(BaseModel):
    name: str
    id: str | None = None


class Track(BaseModel):
    id: str = Field(description="ID видео (videoId)")
    title: str | None = None
    artist: str | None = Field(default=None, description="Артисты одной строкой, как на сайте. Для обычных видео здесь название канала")
    artists: list[Person] = Field(default_factory=list, description="Артисты по отдельности")
    album: Album | None = Field(default=None, description="Альбом. Для видео его нет")
    duration_seconds: int | None = None
    cover: Cover | None = None
    kind: Literal["track", "official_video", "video"] | None = Field(
        default=None,
        description="track: аудиотрек каталога; official_video: официальный клип; video: любое другое видео",
    )
    video_type: str | None = Field(default=None, description="Исходное значение musicVideoType из ответа YouTube Music")


class Playlist(BaseModel):
    id: str
    url: str
    title: str | None = None
    cover: Cover | None = None
    owner: Person | None = None
    track_count: int | None = Field(
        default=None,
        description="Число треков из шапки плейлиста. Может быть больше длины списка tracks: недоступные видео в список не попадают. "
        "Если шапки нет, равно длине списка (а при обрезанном списке null)",
    )
    tracks: list[Track]
    truncated: bool = Field(description="True, если плейлист длиннее лимита страниц и список обрезан")
