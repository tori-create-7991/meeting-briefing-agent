import pytest

from meeting_briefing_agent import credentials
from meeting_briefing_agent.auth import WORKSPACE_SCOPES

SA = "workspace-reader@p.iam.gserviceaccount.com"
SUBJECT = "user@example.org"


class Calls(list):
    """Signer calls, plus the requests and sessions the fakes saw."""


@pytest.fixture
def fake_google(monkeypatch):
    signer_calls = Calls()
    signer_requests = []
    sessions = []

    class FakeSession:
        def __init__(self, source):
            self.source = source
            self.mtls_configured = False
            sessions.append(self)

        def configure_mtls_channel(self):
            self.mtls_configured = True

    class FakeSigner:
        def __init__(self, request, source, sa_email):
            signer_calls.append((source, sa_email))
            signer_requests.append(request)

        key_id = None

        def sign(self, message):
            return b"sig"

    monkeypatch.setattr(credentials.google.auth, "default", lambda scopes: ("source-creds", "p"))
    monkeypatch.setattr(credentials.iam, "Signer", FakeSigner)
    monkeypatch.setattr(credentials, "AuthorizedSession", FakeSession)
    signer_calls.requests = signer_requests
    signer_calls.sessions = sessions
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


def test_dwd_signs_over_an_mtls_session(monkeypatch, fake_google):
    # On Agent Runtime the Agent Identity token is bound to the agent's
    # certificate; the IAM API rejects it (401) unless sent over mTLS.
    set_env(monkeypatch, WORKSPACE_AUTH="dwd", WORKSPACE_SA_EMAIL=SA, WORKSPACE_SUBJECT=SUBJECT)

    credentials.get_workspace_credentials()

    [session] = fake_google.sessions
    assert session.source == "source-creds"
    assert session.mtls_configured
    [request] = fake_google.requests
    assert request.session is session


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
