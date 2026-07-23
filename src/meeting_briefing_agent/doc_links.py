import re

DOC_URL_RE = re.compile(r"docs\.google\.com/document/d/([\w-]+)")
GOOGLE_DOC_MIMETYPE = "application/vnd.google-apps.document"


def extract_doc_ids_from_description(description: str | None) -> list[str]:
    if not description:
        return []
    ids: list[str] = []
    for match in DOC_URL_RE.finditer(description):
        doc_id = match.group(1)
        if doc_id not in ids:
            ids.append(doc_id)
    return ids


def extract_doc_ids_from_attachments(attachments: list[dict] | None) -> list[str]:
    if not attachments:
        return []
    return [
        attachment["fileId"]
        for attachment in attachments
        if attachment.get("mimeType") == GOOGLE_DOC_MIMETYPE and attachment.get("fileId")
    ]


def resolve_doc_ids(event: dict) -> list[str]:
    from_attachments = extract_doc_ids_from_attachments(event.get("attachments"))
    if from_attachments:
        return from_attachments
    return extract_doc_ids_from_description(event.get("description"))
