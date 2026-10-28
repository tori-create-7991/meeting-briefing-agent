from meeting_briefing_agent.doc_links import (
    extract_doc_ids_from_attachments,
    extract_doc_ids_from_description,
    resolve_doc_ids,
)


def test_extract_doc_ids_from_description_single_url():
    description = "Notes: https://docs.google.com/document/d/abc123/edit"
    assert extract_doc_ids_from_description(description) == ["abc123"]


def test_extract_doc_ids_from_description_no_match_returns_empty():
    assert extract_doc_ids_from_description("No links here.") == []


def test_extract_doc_ids_from_description_handles_none():
    assert extract_doc_ids_from_description(None) == []


def test_extract_doc_ids_from_description_dedups_preserving_order():
    description = (
        "See https://docs.google.com/document/d/dup1/edit and again "
        "https://docs.google.com/document/d/dup1/edit plus "
        "https://docs.google.com/document/d/dup2/edit"
    )
    assert extract_doc_ids_from_description(description) == ["dup1", "dup2"]


def test_extract_doc_ids_from_attachments_filters_non_doc_mimetypes(event_with_attachment):
    ids = extract_doc_ids_from_attachments(event_with_attachment["attachments"])
    assert ids == ["attachment-doc-id"]


def test_extract_doc_ids_from_attachments_handles_none():
    assert extract_doc_ids_from_attachments(None) == []


def test_resolve_doc_ids_prefers_attachments_over_description(event_with_attachment):
    assert resolve_doc_ids(event_with_attachment) == ["attachment-doc-id"]


def test_resolve_doc_ids_falls_back_to_description_when_no_attachments(
    event_with_description_link,
):
    assert resolve_doc_ids(event_with_description_link) == ["description-doc-id"]


def test_resolve_doc_ids_returns_empty_when_neither_present(event_with_no_material):
    assert resolve_doc_ids(event_with_no_material) == []


def test_extract_doc_ids_from_description_matches_account_scoped_url():
    description = "Notes: https://docs.google.com/document/u/0/d/scoped123/edit"
    assert extract_doc_ids_from_description(description) == ["scoped123"]


def test_extract_doc_ids_from_attachments_dedups_preserving_order():
    doc = "application/vnd.google-apps.document"
    attachments = [
        {"fileId": "a", "mimeType": doc},
        {"fileId": "b", "mimeType": doc},
        {"fileId": "a", "mimeType": doc},
    ]
    assert extract_doc_ids_from_attachments(attachments) == ["a", "b"]
