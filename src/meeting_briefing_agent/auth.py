import logging
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]


def _save_token(creds: Credentials, token_path: str) -> None:
    # Write to a 0600 temp file, then atomically replace token.json. The
    # replaced file takes the temp file's permissions, so a pre-existing
    # token.json with looser permissions ends up 0600 too, and a crash
    # mid-write can never leave a half-written token.json behind.
    tmp_path = f"{token_path}.tmp"
    fd = os.open(tmp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        if hasattr(os, "fchmod"):  # not available on Windows before 3.13
            os.fchmod(fd, 0o600)
        token_file = os.fdopen(fd, "w")
    except BaseException:
        os.close(fd)
        raise
    with token_file:
        token_file.write(creds.to_json())
    os.replace(tmp_path, token_path)


def _load_cached_credentials(token_path: str) -> Credentials | None:
    try:
        return Credentials.from_authorized_user_file(token_path, SCOPES)
    except FileNotFoundError:
        return None
    except ValueError as exc:  # corrupt JSON or missing fields
        logger.warning(
            "Ignoring unreadable %s (%s); running OAuth consent again.",
            token_path,
            exc,
        )
        return None


def get_credentials(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
) -> Credentials:
    creds = _load_cached_credentials(token_path)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            # Typical cause: the OAuth client is in "Testing" status, where
            # refresh tokens expire after 7 days, or access was revoked.
            logger.warning(
                "Refreshing the cached token failed (%s); running OAuth "
                "consent again.",
                exc,
            )
            creds = None
        else:
            _save_token(creds, token_path)

    if not creds or not creds.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"OAuth client secret not found at '{credentials_path}'. "
                "Download it from the GCP project's OAuth Desktop app client "
                "and place it there — see README.md for setup steps."
            ) from exc
        creds = flow.run_local_server(port=0)
        _save_token(creds, token_path)

    return creds
