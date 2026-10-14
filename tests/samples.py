"""Тестовые данные. Структура записей повторяет реальные ответы browse (по выводу explore_track.py).

Шапка плейлиста (title, straplineTextOne, thumbnail) собрана по догадке, потому что реальную шапку
мы ещё не разбирали. Число треков (secondSubtitle) взято из реального ответа.
"""


def run(text, browse_id=None):
    part = {"text": text}
    if browse_id:
        part["navigationEndpoint"] = {"browseEndpoint": {"browseId": browse_id}}
    return part


def column(*runs):
    return {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": list(runs)}}}


def item(video_id, video_type, title, artist_runs, album_runs=None, duration="3:00", thumbnails=None):
    flex_columns = [column(run(title)), column(*artist_runs)]
    if album_runs is not None:
        flex_columns.append(column(*album_runs))
    return {
        "musicResponsiveListItemRenderer": {
            "playlistItemData": {"videoId": video_id},
            "thumbnail": {
                "musicThumbnailRenderer": {
                    "thumbnail": {
                        "thumbnails": thumbnails
                        or [
                            {"url": "https://img/60", "width": 60, "height": 60},
                            {"url": "https://img/120", "width": 120, "height": 120},
                        ]
                    }
                }
            },
            "overlay": {
                "musicItemThumbnailOverlayRenderer": {
                    "content": {
                        "musicPlayButtonRenderer": {
                            "playNavigationEndpoint": {
                                "watchEndpoint": {
                                    "videoId": video_id,
                                    "watchEndpointMusicSupportedConfigs": {
                                        "watchEndpointMusicConfig": {"musicVideoType": video_type}
                                    },
                                }
                            }
                        }
                    }
                }
            },
            "flexColumns": flex_columns,
            "fixedColumns": [{"musicResponsiveListItemFixedColumnRenderer": {"text": {"runs": [{"text": duration}]}}}],
        }
    }


def header(count_text="22 tracks", owner_name="Popet"):
    """Шапка по реальной структуре ответа (ключи взяты из вывода explore_header.py).

    Имя владельца facepile.avatarStackViewModel.text.content в реальном выводе не попало,
    поэтому его путь здесь предположение. ID канала взят из реального ответа.
    """
    return {
        "musicResponsiveHeaderRenderer": {
            "title": {"runs": [{"text": "Мой тестовый плейлист"}]},
            "subtitle": {"runs": [{"text": "Playlist"}, {"text": " \u2022 "}, {"text": "2026"}]},
            "description": {"musicDescriptionShelfRenderer": {"description": {"runs": [{"text": "20 tracks"}]}}},
            "secondSubtitle": {"runs": [{"text": "2 views"}, {"text": " \u2022 "}, {"text": count_text}, {"text": " \u2022 "}, {"text": "1 hour, 38 minutes"}]},
            "facepile": {
                "avatarStackViewModel": {
                    "text": {"content": owner_name},
                    "avatars": [{"avatarViewModel": {"image": {"sources": [{"url": "https://yt3.ggpht.com/avatar"}]}}}],
                    "rendererContext": {
                        "commandContext": {"onTap": {"innertubeCommand": {"browseEndpoint": {"browseId": "UCtvfuq95pN7nmk1aTL5MSdQ"}}}}
                    },
                }
            },
            "thumbnail": {
                "musicThumbnailRenderer": {
                    "thumbnail": {
                        "thumbnails": [
                            {"url": "https://cover/192", "width": 192, "height": 192},
                            {"url": "https://cover/576", "width": 576, "height": 576},
                            {"url": "https://cover/1200", "width": 1200, "height": 1200},
                        ]
                    }
                }
            },
        }
    }


def page(items, token=None, with_header=None):
    """Страница ответа browse: шапка (по желанию), список треков и токен следующей страницы."""
    contents = list(items)
    if token:
        contents.append({"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": token}}}})
    result = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "secondaryContents": {"sectionListRenderer": {"contents": [{"musicPlaylistShelfRenderer": {"contents": contents}}]}}
            }
        }
    }
    if with_header is not None:
        result["header"] = with_header
    return result


CATALOG_TRACK = item(
    "KwN_f0fTHoE", "MUSIC_VIDEO_TYPE_ATV", "One Step Closer",
    [run("Linkin Park", "UCxgN32UVVztKAQd2HkXzBtw")],
    [run("Hybrid Theory", "MPREb_odUae150mq3")],
    duration="2:38",
)
MULTI_ARTIST = item(
    "E2lX1ZovtcA", "MUSIC_VIDEO_TYPE_ATV", "Give Me Everything (feat. Nayer)",
    [run("Pitbull", "UC_1"), run(", "), run("Afrojack", "UC_2"), run(" & "), run("Ne-Yo", "UC_3")],
    [run("Planet Pit", "MPREb_planet")],
)
UGC_VIDEO = item(
    "FjZm6PQYQBY", "MUSIC_VIDEO_TYPE_UGC", "Metallica: M72 World Tour Returns to North America",
    [run("Metallica", "UC_metallica")],
    duration="1:01",
)
OFFICIAL_CLIP = item(
    "6ulQgfqkvLY", "MUSIC_VIDEO_TYPE_OMV", "Yeah",
    [run("OMFG", "UCogujxdYRhzQf1eU-MU4IJQ")],
    duration="3:46",
    thumbnails=[{"url": "https://img/400", "width": 400, "height": 225}],
)
PODCAST_WITH_DATE = item(
    "8Oos6D4_Bjo", "MUSIC_VIDEO_TYPE_PODCAST_EPISODE", "I Animated This Entire Video using ONLY Subtitles",
    [run("#1 on Trending", "UC_trending")],
    [run("Aug 18, 2024")],  # в третьей колонке дата, а не альбом
    duration="0:46",
)

# Приватный плейлист: ответ без шапки и без списка (так выглядел реальный ответ, 806 байт)
PRIVATE_PAGE = {
    "responseContext": {"visitorData": "x"},
    "trackingParams": "y",
    "microformat": {"microformatDataRenderer": {"noindex": True}},
}
