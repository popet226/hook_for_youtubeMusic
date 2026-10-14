import pytest

from app.errors import LinkError
from app.links import parse_playlist_link

PLAYLIST = "PLHHFkCbk5F28"


@pytest.mark.parametrize(
    "url",
    [
        f"https://music.youtube.com/playlist?list={PLAYLIST}",
        f"https://www.youtube.com/playlist?list={PLAYLIST}",
        f"https://youtube.com/playlist?list={PLAYLIST}",
        f"https://music.youtube.com/browse/VL{PLAYLIST}",
        f"https://music.youtube.com/playlist?list={PLAYLIST}&si=abc123&start_radio=1",
        f"https://music.youtube.com/watch?v=KwN_f0fTHoE&list={PLAYLIST}",
        f"  https://music.youtube.com/playlist?list={PLAYLIST}  ",
    ],
)
def test_playlist_links(url):
    assert parse_playlist_link(url) == PLAYLIST


def test_album_autoplaylist_is_accepted():
    url = "https://music.youtube.com/playlist?list=OLAK5uy_kQ_6n09WjMicPm7moQk7m0_Jww4oB6iMQ"
    assert parse_playlist_link(url) == "OLAK5uy_kQ_6n09WjMicPm7moQk7m0_Jww4oB6iMQ"


def test_curated_playlist_is_accepted():
    assert parse_playlist_link("https://music.youtube.com/playlist?list=RDCLAK5uy_k6Pk") == "RDCLAK5uy_k6Pk"


@pytest.mark.parametrize(
    "url, code",
    [
        ("https://music.youtube.com/@metallica", "not_a_playlist"),
        ("https://music.youtube.com/channel/UCxgN32UVVztKAQd2HkXzBtw", "not_a_playlist"),
        ("https://music.youtube.com/browse/MPREb_odUae150mq3", "not_a_playlist"),
        ("https://music.youtube.com/watch?v=Z85lxckrtzg", "not_a_playlist"),
        ("https://music.youtube.com/playlist", "not_a_playlist"),
        ("https://music.youtube.com/watch?v=kOn-HdEg6AQ&list=RDAMVMkOn-HdEg6AQ", "mix_not_supported"),
        ("https://example.com/playlist?list=PLHHFkCbk5F28", "unsupported_host"),
        ("music.youtube.com/playlist?list=PLHHFkCbk5F28", "invalid_url"),
        ("не ссылка", "invalid_url"),
        ("", "invalid_url"),
    ],
)
def test_links_that_are_not_supported(url, code):
    with pytest.raises(LinkError) as error:
        parse_playlist_link(url)
    assert error.value.code == code
