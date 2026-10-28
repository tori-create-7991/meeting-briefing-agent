import contextlib
import logging
import os
import tempfile

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
    # Write to a fresh 0600 temp file in the same directory (mkstemp uses
    # O_EXCL and a unique name), then atomically replace token.json. The
    # replaced file takes the temp file's permissions, so a pre-existing
    # token.json with looser permissions ends up 0600 too, and a failed
    # write never leaves a half-written token.json behind.
    directory = os.path.dirname(token_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".token-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as token_file:
            token_file.write(creds.to_json())
        os.replace(tmp_path, token_path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


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
