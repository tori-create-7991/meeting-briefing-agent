from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_credentials(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
) -> Credentials:
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except FileNotFoundError:
        pass

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

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
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())

    return creds
