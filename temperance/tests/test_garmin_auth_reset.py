from __future__ import annotations

from types import SimpleNamespace

import pytest

import temperance.garmin_client as garmin_client


class FakeSession:
    def __init__(self) -> None:
        self.cookies = SimpleNamespace(clear=lambda: None)
        self.headers = {}
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeGarth:
    def __init__(self) -> None:
        self.sess = FakeSession()
        self.oauth1_token = {"token": "oauth1"}
        self.oauth2_token = {"token": "oauth2"}
        self._profile = {"displayName": "fake-display", "fullName": "Fake Runner"}
        self.loads_calls = 0

    @property
    def profile(self) -> dict[str, str]:
        return self._profile

    def connectapi(self, path: str) -> dict[str, dict[str, str]]:
        assert path == "/userprofile-service/userprofile/user-settings"
        return {"userData": {"measurementSystem": "metric"}}

    def dumps(self) -> str:
        return "encoded-session"

    def loads(self, payload: str) -> None:
        assert payload == "encoded-session"
        self.loads_calls += 1


class FakeClient:
    def __init__(self, login_error: Exception | None = None) -> None:
        self.garth = FakeGarth()
        self.display_name = None
        self.full_name = None
        self.unit_system = None
        self.login_calls = 0
        self.login_error = login_error

    def login(self) -> bool:
        self.login_calls += 1
        if self.login_error is not None:
            raise self.login_error
        return True


def _configure_tmp_session_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TEMPERANCE_GARMIN_SESSION_DIR", str(tmp_path / "garmin_auth"))
    garmin_client.reset_garmin_auth()


def test_get_session_logs_in_once_and_reuses_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_tmp_session_dir(monkeypatch, tmp_path)
    created: list[FakeClient] = []

    def build(email: str, password: str) -> FakeClient:
        client = FakeClient()
        created.append(client)
        return client

    monkeypatch.setattr(garmin_client, "_build_fresh_garmin_client", build)

    first = garmin_client.get_session("user@example.com", "pw")
    second = garmin_client.get_session("user@example.com", "pw")

    assert first is second
    assert len(created) == 1
    assert created[0].login_calls == 1
    assert (tmp_path / "garmin_auth" / "session.json").exists()


def test_get_session_reuses_disk_cache_without_login(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_tmp_session_dir(monkeypatch, tmp_path)
    first = FakeClient()
    second = FakeClient()
    created = [first, second]

    def build(email: str, password: str) -> FakeClient:
        return created.pop(0)

    monkeypatch.setattr(garmin_client, "_build_fresh_garmin_client", build)

    garmin_client.get_session("user@example.com", "pw")
    garmin_client._GARMIN_SHARED_CLIENT = None
    garmin_client._GARMIN_SHARED_EMAIL_HASH = None

    restored = garmin_client.get_session("user@example.com", "pw")

    assert restored is second
    assert second.login_calls == 0
    assert second.garth.loads_calls == 1


def test_reset_garmin_auth_clears_disk_and_memory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_tmp_session_dir(monkeypatch, tmp_path)
    client = FakeClient()
    monkeypatch.setattr(garmin_client, "_build_fresh_garmin_client", lambda email, password: client)

    garmin_client.get_session("user@example.com", "pw")
    session_file = tmp_path / "garmin_auth" / "session.json"
    assert session_file.exists()

    garmin_client.reset_garmin_auth()

    assert not session_file.exists()
    assert garmin_client._GARMIN_SHARED_CLIENT is None
    assert garmin_client._GARMIN_SHARED_EMAIL_HASH is None
    assert garmin_client._GARMIN_LOGIN_ATTEMPTED is False
    assert garmin_client._GARMIN_LOGIN_COMPLETED is False
    assert client.garth.oauth1_token is None
    assert client.garth.oauth2_token is None
    assert client.garth.sess.closed is True


def test_login_429_blocks_repeat_attempts_until_reset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_tmp_session_dir(monkeypatch, tmp_path)
    first = FakeClient(login_error=Exception("429 Too Many Requests"))
    second = FakeClient()
    third = FakeClient()
    created = [first, second, third]

    def build(email: str, password: str) -> FakeClient:
        return created.pop(0)

    monkeypatch.setattr(garmin_client, "_build_fresh_garmin_client", build)

    with pytest.raises(garmin_client.GarminRateLimitError):
        garmin_client.get_session("user@example.com", "pw")

    with pytest.raises(garmin_client.GarminRateLimitError):
        garmin_client.get_session("user@example.com", "pw")

    garmin_client.reset_garmin_auth()
    session = garmin_client.get_session("user@example.com", "pw")

    assert session is third
    assert second.login_calls == 0
    assert third.login_calls == 1


def test_safe_call_retries_429_with_exponential_backoff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_tmp_session_dir(monkeypatch, tmp_path)
    sleeps: list[int] = []
    attempts = {"count": 0}

    def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise Exception("429 Too Many Requests")
        return "ok"

    monkeypatch.setattr(garmin_client.time, "sleep", fake_sleep)

    payload, err = garmin_client._safe_call(flaky)

    assert payload == "ok"
    assert err is None
    assert sleeps == [2, 4]
