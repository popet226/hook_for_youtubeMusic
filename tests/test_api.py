"""Проверка HTTP-ручки. Настоящий клиент YouTube Music заменён подставным: сеть не нужна."""
from fastapi.testclient import TestClient
from samples import CATALOG_TRACK, PRIVATE_PAGE, UGC_VIDEO, header, page

from app.errors import UpstreamError
from app.main import app


class FakeClient:
    def __init__(self, pages=None, error=None, truncated=False):
        self.pages, self.error, self.truncated = pages, error, truncated
        self.requested = []

    async def fetch_playlist(self, playlist_id):
        self.requested.append(playlist_id)
        if self.error:
            raise self.error
        return self.pages, self.truncated

    async def aclose(self):
        pass


def call(fake, url):
    with TestClient(app) as client:
        app.state.client = fake  # подставляем клиент после запуска приложения
        return client.post("/playlist", json={"url": url})


def test_success():
    fake = FakeClient([page([CATALOG_TRACK, UGC_VIDEO], with_header=header("2 tracks"))])
    response = call(fake, "https://www.youtube.com/playlist?list=PLabc123&si=zzz")
    assert response.status_code == 200
    data = response.json()
    assert fake.requested == ["PLabc123"]
    assert data["track_count"] == 2 and len(data["tracks"]) == 2
    assert data["tracks"][0]["kind"] == "track" and data["tracks"][1]["kind"] == "video"


def test_bad_link_gives_422_and_never_reaches_youtube():
    fake = FakeClient([])
    response = call(fake, "https://music.youtube.com/@metallica")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_a_playlist"
    assert fake.requested == []


def test_mix_link():
    response = call(FakeClient([]), "https://music.youtube.com/watch?v=kOn-HdEg6AQ&list=RDAMVMkOn-HdEg6AQ")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mix_not_supported"


def test_private_playlist_gives_404():
    response = call(FakeClient([PRIVATE_PAGE]), "https://music.youtube.com/playlist?list=PLprivate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "playlist_not_found"


def test_rate_limit_is_passed_on_with_retry_after():
    fake = FakeClient(error=UpstreamError("limit", status=429, retry_after="30"))
    response = call(fake, "https://music.youtube.com/playlist?list=PLabc123")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"


def test_upstream_failure_gives_502():
    fake = FakeClient(error=UpstreamError("Сетевая ошибка: ConnectError"))
    response = call(fake, "https://music.youtube.com/playlist?list=PLabc123")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_error"


def test_missing_url_field():
    with TestClient(app) as client:
        assert client.post("/playlist", json={}).status_code == 422


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
