import pytest

from meeting_briefing_agent import credentials
from meeting_briefing_agent.auth import WORKSPACE_SCOPES

SA = "workspace-reader@p.iam.gserviceaccount.com"
SUBJECT = "user@example.org"


@pytest.fixture
def fake_google(monkeypatch):
    signer_calls = []

    class FakeSigner:
        def __init__(self, request, source, sa_email):
            signer_calls.append((source, sa_email))

        key_id = None

        def sign(self, message):
            return b"sig"

    monkeypatch.setattr(credentials.google.auth, "default", lambda scopes: ("source-creds", "p"))
    monkeypatch.setattr(credentials.iam, "Signer", FakeSigner)
    return signer_calls


def set_env(monkeypatch, **env):
    for name in ("WORKSPACE_AUTH", "WORKSPACE_SA_EMAIL", "WORKSPACE_SUBJECT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def test_dwd_builds_keyless_delegated_credentials(monkeypatch, fake_google):
    set_env(monkeypatch, WORKSPACE_AUTH="dwd", WORKSPACE_SA_EMAIL=SA, WORKSPACE_SUBJECT=SUBJECT)

    creds = credentials.get_workspace_credentials()

    assert creds._subject == SUBJECT
    assert creds._service_account_email == SA
    assert list(creds.scopes) == WORKSPACE_SCOPES
    assert fake_google == [("source-creds", SA)]


@pytest.mark.parametrize("missing", ["WORKSPACE_SA_EMAIL", "WORKSPACE_SUBJECT"])
def test_dwd_names_the_missing_variable(monkeypatch, fake_google, missing):
    env = {"WORKSPACE_AUTH": "dwd", "WORKSPACE_SA_EMAIL": SA, "WORKSPACE_SUBJECT": SUBJECT}
    del env[missing]
    set_env(monkeypatch, **env)

    with pytest.raises(RuntimeError, match=missing):
        credentials.get_workspace_credentials()


def test_local_oauth_is_the_default(monkeypatch):
    set_env(monkeypatch)
    monkeypatch.setattr(credentials, "get_credentials", lambda: "local-creds")

    assert credentials.get_workspace_credentials() == "local-creds"


def test_unknown_mode_is_rejected(monkeypatch):
    set_env(monkeypatch, WORKSPACE_AUTH="magic")

    with pytest.raises(ValueError, match="WORKSPACE_AUTH"):
        credentials.get_workspace_credentials()
