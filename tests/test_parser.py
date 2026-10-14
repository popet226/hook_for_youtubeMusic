import pytest
from samples import (CATALOG_TRACK, MULTI_ARTIST, OFFICIAL_CLIP, PODCAST_WITH_DATE, PRIVATE_PAGE, UGC_VIDEO,
                     header, page)

from app.errors import PlaylistNotFound
from app.parser import (build_playlist, find_continuation_token, parse_duration, parse_header, parse_track)


def track(sample):
    return parse_track(sample["musicResponsiveListItemRenderer"])


def test_catalog_track():
    result = track(CATALOG_TRACK)
    assert result["id"] == "KwN_f0fTHoE"
    assert result["title"] == "One Step Closer"
    assert result["artist"] == "Linkin Park"
    assert result["artists"] == [{"name": "Linkin Park", "id": "UCxgN32UVVztKAQd2HkXzBtw"}]
    assert result["album"] == {"name": "Hybrid Theory", "id": "MPREb_odUae150mq3"}
    assert result["duration_seconds"] == 158
    assert result["cover"]["width"] == 120
    assert result["kind"] == "track"
    assert result["video_type"] == "MUSIC_VIDEO_TYPE_ATV"


def test_several_artists():
    result = track(MULTI_ARTIST)
    assert result["artist"] == "Pitbull, Afrojack & Ne-Yo"
    assert [a["name"] for a in result["artists"]] == ["Pitbull", "Afrojack", "Ne-Yo"]


def test_video_has_no_album():
    result = track(UGC_VIDEO)
    assert result["album"] is None
    assert result["kind"] == "video"
    assert result["artist"] == "Metallica"  # у обычного видео это название канала
    assert result["duration_seconds"] == 61


def test_official_clip():
    result = track(OFFICIAL_CLIP)
    assert result["kind"] == "official_video"
    assert result["cover"]["width"] == 400


def test_date_in_third_column_is_not_an_album():
    result = track(PODCAST_WITH_DATE)
    assert result["album"] is None
    assert result["kind"] == "video"
    assert result["video_type"] == "MUSIC_VIDEO_TYPE_PODCAST_EPISODE"


def test_record_without_video_id_is_skipped():
    assert parse_track({"flexColumns": []}) is None


def test_record_with_missing_fields_does_not_break():
    result = parse_track({"playlistItemData": {"videoId": "abc"}})
    assert result["id"] == "abc"
    assert result["title"] is None and result["album"] is None and result["duration_seconds"] is None
    assert result["artists"] == [] and result["cover"] is None and result["kind"] is None


@pytest.mark.parametrize(
    "text, seconds",
    [("2:38", 158), ("54:30", 3270), ("1:02:03", 3723), ("0:46", 46), ("", None), (None, None), ("Aug 18, 2024", None)],
)
def test_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_header():
    result = parse_header(page([], with_header=header("22 tracks")))
    assert result["track_count"] == 22
    assert result["title"] == "Мой тестовый плейлист"
    assert result["owner"] == {"name": "Popet", "id": "UCtvfuq95pN7nmk1aTL5MSdQ"}
    assert result["cover"]["width"] == 1200


def test_header_count_with_thousands_separator():
    assert parse_header(page([], with_header=header("1,234 tracks")))["track_count"] == 1234
    assert parse_header(page([], with_header=header("1 song")))["track_count"] == 1


def test_continuation_token():
    assert find_continuation_token(page([CATALOG_TRACK], token="NEXT")) == "NEXT"
    assert find_continuation_token(page([CATALOG_TRACK])) is None


def test_build_playlist_from_two_pages():
    first = page([CATALOG_TRACK, UGC_VIDEO], token="NEXT", with_header=header("3 tracks"))
    second = page([MULTI_ARTIST])
    result = build_playlist("PLX", [first, second], truncated=False)
    assert [t["id"] for t in result["tracks"]] == ["KwN_f0fTHoE", "FjZm6PQYQBY", "E2lX1ZovtcA"]
    assert result["track_count"] == 3
    assert result["url"] == "https://music.youtube.com/playlist?list=PLX"
    assert result["truncated"] is False


def test_empty_playlist_is_not_an_error():
    result = build_playlist("PLX", [page([], with_header=header("0 tracks"))], truncated=False)
    assert result["tracks"] == [] and result["track_count"] == 0


def test_private_playlist_is_not_found():
    with pytest.raises(PlaylistNotFound):
        build_playlist("PLX", [PRIVATE_PAGE], truncated=False)


def test_owner_without_name_keeps_channel_id():
    sample = header()
    del sample["musicResponsiveHeaderRenderer"]["facepile"]["avatarStackViewModel"]["text"]
    result = parse_header(page([], with_header=sample))
    assert result["owner"] == {"name": None, "id": "UCtvfuq95pN7nmk1aTL5MSdQ"}


def test_no_owner_block_gives_none():
    sample = header()
    del sample["musicResponsiveHeaderRenderer"]["facepile"]
    assert parse_header(page([], with_header=sample))["owner"] is None


def test_description_number_is_not_used_as_track_count():
    # В описании плейлиста владелец написал «20 tracks», в шапке настоящее число 22
    assert parse_header(page([], with_header=header("22 tracks")))["track_count"] == 22


def test_playlist_without_header_takes_count_from_list():
    # Так выглядит автоплейлист альбома в реальном ответе: треки есть, шапки нет
    result = build_playlist("OLAK5uy_x", [page([CATALOG_TRACK, MULTI_ARTIST])], truncated=False)
    assert result["title"] is None and result["owner"] is None
    assert result["track_count"] == 2


def test_truncated_playlist_without_header_has_no_count():
    result = build_playlist("OLAK5uy_x", [page([CATALOG_TRACK])], truncated=True)
    assert result["track_count"] is None


def album_track(video_id, album_id="MPREb_one", album_name="Hybrid Theory", with_album=True):
    from samples import item, run
    return item(video_id, "MUSIC_VIDEO_TYPE_ATV", f"Song {video_id}", [run("Linkin Park", "UC_lp")],
                [run(album_name, album_id)] if with_album else None)


def test_album_autoplaylist_gets_title_and_cover_from_album():
    # Автоплейлист альбома: шапки нет, все треки из одного альбома
    pages = [page([album_track("a"), album_track("b"), album_track("c")])]
    result = build_playlist("OLAK5uy_x", pages, truncated=False)
    assert result["title"] == "Hybrid Theory"
    assert result["cover"]["width"] == 120
    assert result["owner"] is None  # у такого плейлиста нет владельца
    assert result["track_count"] == 3


def test_different_albums_do_not_give_a_title():
    pages = [page([album_track("a"), album_track("b", "MPREb_two", "Meteora")])]
    assert build_playlist("PLX", pages, truncated=False)["title"] is None


def test_track_without_album_blocks_the_fallback_title():
    pages = [page([album_track("a"), album_track("b", with_album=False)])]
    assert build_playlist("PLX", pages, truncated=False)["title"] is None


def test_real_header_is_not_replaced_by_album_name():
    pages = [page([album_track("a")], with_header=header("1 song"))]
    assert build_playlist("PLX", pages, truncated=False)["title"] == "Мой тестовый плейлист"