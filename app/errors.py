"""Ошибки сервиса. Каждая ошибка превращается в понятный ответ HTTP (см. main.py)."""


class LinkError(Exception):
    """Ссылку нельзя использовать: она неверная или ведёт не на плейлист."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class PlaylistNotFound(Exception):
    """YouTube Music не вернул ни шапки, ни треков: плейлиста нет или он приватный."""


class UpstreamError(Exception):
    """Сбой на стороне YouTube Music или в сети."""

    def __init__(self, message: str, status: int | None = None, retry_after: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after
