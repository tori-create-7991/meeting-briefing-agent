import re

# Matches /document/d/<id> and the account-scoped /document/u/<n>/d/<id>.
DOC_URL_RE = re.compile(r"docs\.google\.com/document/(?:u/\d+/)?d/([\w-]+)")
GOOGLE_DOC_MIMETYPE = "application/vnd.google-apps.document"


def _dedup(ids: list[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def extract_doc_ids_from_description(description: str | None) -> list[str]:
    if not description:
        return []
    return _dedup([match.group(1) for match in DOC_URL_RE.finditer(description)])


def extract_doc_ids_from_attachments(attachments: list[dict] | None) -> list[str]:
    if not attachments:
        return []
    return _dedup(
        [
            attachment["fileId"]
            for attachment in attachments
            if attachment.get("mimeType") == GOOGLE_DOC_MIMETYPE
            and attachment.get("fileId")
        ]
    )


def resolve_doc_ids(event: dict) -> list[str]:
    from_attachments = extract_doc_ids_from_attachments(event.get("attachments"))
    if from_attachments:
        return from_attachments
    return extract_doc_ids_from_description(event.get("description"))
