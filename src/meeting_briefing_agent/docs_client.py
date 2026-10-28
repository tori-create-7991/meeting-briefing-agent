import http.client
import logging

import httplib2
from google.auth.exceptions import TransportError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Failures that only affect the one document being fetched. Anything else
# (for example an auth failure) is left to propagate.
FETCH_ERRORS = (
    HttpError,
    OSError,
    http.client.HTTPException,
    httplib2.HttpLib2Error,
    TransportError,
)


def build_docs_service(creds):
    return build("docs", "v1", credentials=creds)


def fetch_doc_text(service, document_id: str, max_chars: int = 4000) -> str | None:
    """Fetch and flatten a Google Doc's body text.

    Returns None when the document could not be fetched, so callers can tell
    a failed fetch apart from a document that is genuinely empty.

    Only walks top-level paragraph text runs; nested table content is not
    extracted (known limitation, out of scope for milestone 1).
    """
    try:
        document = (
            service.documents().get(documentId=document_id).execute(num_retries=2)
        )
    except FETCH_ERRORS as exc:
        logger.warning("Failed to fetch Google Doc %s: %s", document_id, exc)
        return None

    chunks: list[str] = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for part in paragraph.get("elements", []):
            text_run = part.get("textRun")
            if text_run and text_run.get("content"):
                chunks.append(text_run["content"])

    text = "".join(chunks)
    if len(text) > max_chars:
        return text[:max_chars] + "…"
    return text
