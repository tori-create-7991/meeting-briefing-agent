import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def build_docs_service(creds):
    return build("docs", "v1", credentials=creds)


def fetch_doc_text(service, document_id: str, max_chars: int = 4000) -> str:
    """Fetch and flatten a Google Doc's body text.

    Only walks top-level paragraph text runs; nested table content is not
    extracted (known limitation, out of scope for milestone 1).
    """
    try:
        document = service.documents().get(documentId=document_id).execute()
    except HttpError as exc:
        logger.warning("Failed to fetch Google Doc %s: %s", document_id, exc)
        return ""

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
