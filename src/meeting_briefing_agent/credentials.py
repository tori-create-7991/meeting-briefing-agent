"""Workspace credentials for local runs and for the deployed agent.

WORKSPACE_AUTH selects the mode:

- local_oauth (default): browser consent, cached in token.json (auth.py).
- dwd: keyless domain-wide delegation. The runtime identity signs the JWT
  through the IAM signBlob API as WORKSPACE_SA_EMAIL, impersonating
  WORKSPACE_SUBJECT. No service account key ever exists.
"""

import os

import google.auth
from google.auth import iam
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

from meeting_briefing_agent.auth import WORKSPACE_SCOPES, get_credentials

TOKEN_URI = "https://oauth2.googleapis.com/token"
CLOUD_PLATFORM = "https://www.googleapis.com/auth/cloud-platform"


def get_workspace_credentials():
    mode = os.getenv("WORKSPACE_AUTH", "local_oauth")
    if mode == "local_oauth":
        return get_credentials()
    if mode != "dwd":
        raise ValueError(f"Unknown WORKSPACE_AUTH: {mode!r} (use local_oauth or dwd)")

    sa_email = os.getenv("WORKSPACE_SA_EMAIL")
    subject = os.getenv("WORKSPACE_SUBJECT")
    missing = [
        name
        for name, value in (("WORKSPACE_SA_EMAIL", sa_email), ("WORKSPACE_SUBJECT", subject))
        if not value
    ]
    if missing:
        raise RuntimeError(f"Domain-wide delegation needs {', '.join(missing)}")

    source, _ = google.auth.default(scopes=[CLOUD_PLATFORM])
    # On Agent Runtime the Agent Identity token is bound to the agent's
    # certificate, and Google APIs reject it unless it arrives over mTLS
    # with that certificate. configure_mtls_channel() is a no-op where no
    # client certificate is configured (local runs, a service account).
    session = AuthorizedSession(source)
    session.configure_mtls_channel()
    signer = iam.Signer(Request(session=session), source, sa_email)
    return service_account.Credentials(
        signer, sa_email, TOKEN_URI, scopes=WORKSPACE_SCOPES, subject=subject
    )
