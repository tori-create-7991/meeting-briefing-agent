import os
import stat

import pytest
from google.auth.exceptions import RefreshError

from meeting_briefing_agent import auth
from meeting_briefing_agent.auth import _save_token, get_credentials


class FakeCreds:
    def __init__(self, valid=True, expired=False, refresh_token="refresh", refresh_error=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self._refresh_error = refresh_error
        self.refreshed = False

    def refresh(self, request):
        if self._refresh_error:
            raise self._refresh_error
        self.valid = True
        self.expired = False
        self.refreshed = True

    def to_json(self):
        return '{"token": "fake"}'


class FakeFlow:
    def __init__(self, creds):
        self.creds = creds
        self.ran = False

    def run_local_server(self, port):
        self.ran = True
        return self.creds


def patch_cached(monkeypatch, creds):
    monkeypatch.setattr(
        auth.Credentials,
        "from_authorized_user_file",
        staticmethod(lambda path, scopes: creds),
    )


def patch_flow(monkeypatch, flow):
    monkeypatch.setattr(
        auth.InstalledAppFlow,
        "from_client_secrets_file",
        staticmethod(lambda path, scopes: flow),
    )


def forbid_flow(monkeypatch):
    def fail(path, scopes):
        raise AssertionError("OAuth consent flow should not run")

    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_secrets_file", staticmethod(fail))


def file_mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_save_token_sets_0600_on_new_file(tmp_path):
    token_path = tmp_path / "token.json"

    _save_token(FakeCreds(), str(token_path))

    assert file_mode(token_path) == 0o600
    assert token_path.read_text() == '{"token": "fake"}'
    assert list(tmp_path.glob(".token-*.tmp")) == []


def test_save_token_tightens_permissions_on_pre_existing_file(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token": "stale"}')
    os.chmod(token_path, 0o644)

    _save_token(FakeCreds(), str(token_path))

    assert file_mode(token_path) == 0o600


def test_save_token_leaves_existing_token_untouched_when_write_fails(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text('{"token": "old"}')

    class BrokenCreds:
        def to_json(self):
            raise RuntimeError("serialization failed")

    with pytest.raises(RuntimeError):
        _save_token(BrokenCreds(), str(token_path))

    assert token_path.read_text() == '{"token": "old"}'
    assert list(tmp_path.glob(".token-*.tmp")) == []


def test_get_credentials_explains_missing_client_secret(tmp_path):
    with pytest.raises(FileNotFoundError, match="OAuth client secret not found"):
        get_credentials(
            credentials_path=str(tmp_path / "credentials.json"),
            token_path=str(tmp_path / "token.json"),
        )


def test_get_credentials_reuses_valid_cached_token(tmp_path, monkeypatch):
    cached = FakeCreds(valid=True)
    patch_cached(monkeypatch, cached)
    forbid_flow(monkeypatch)

    assert get_credentials(token_path=str(tmp_path / "token.json")) is cached


def test_get_credentials_refreshes_expired_token_and_saves_it_0600(tmp_path, monkeypatch):
    cached = FakeCreds(valid=False, expired=True)
    patch_cached(monkeypatch, cached)
    forbid_flow(monkeypatch)
    token_path = tmp_path / "token.json"

    creds = get_credentials(token_path=str(token_path))

    assert creds is cached and cached.refreshed
    assert file_mode(token_path) == 0o600


def test_get_credentials_falls_back_to_consent_when_refresh_fails(tmp_path, monkeypatch):
    patch_cached(
        monkeypatch,
        FakeCreds(valid=False, expired=True, refresh_error=RefreshError("invalid_grant")),
    )
    fresh = FakeCreds()
    flow = FakeFlow(fresh)
    patch_flow(monkeypatch, flow)
    token_path = tmp_path / "token.json"

    creds = get_credentials(token_path=str(token_path))

    assert flow.ran and creds is fresh
    assert file_mode(token_path) == 0o600


def test_get_credentials_falls_back_to_consent_when_token_file_is_corrupt(tmp_path, monkeypatch):
    token_path = tmp_path / "token.json"
    token_path.write_text("{not json")
    fresh = FakeCreds()
    flow = FakeFlow(fresh)
    patch_flow(monkeypatch, flow)

    creds = get_credentials(token_path=str(token_path))

    assert flow.ran and creds is fresh
    assert token_path.read_text() == '{"token": "fake"}'
