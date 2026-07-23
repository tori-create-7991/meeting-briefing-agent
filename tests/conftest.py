import pytest


@pytest.fixture
def event_with_attachment():
    return {
        "summary": "Q3 planning",
        "description": "Kickoff for Q3 planning cycle.",
        "attachments": [
            {
                "fileId": "attachment-doc-id",
                "mimeType": "application/vnd.google-apps.document",
                "title": "Q3 Plan",
            },
            {
                "fileId": "attachment-sheet-id",
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "title": "Q3 Budget",
            },
        ],
    }


@pytest.fixture
def event_with_description_link():
    return {
        "summary": "Design review",
        "description": (
            "Please review before the call: "
            "https://docs.google.com/document/d/description-doc-id/edit"
        ),
        "attachments": [],
    }


@pytest.fixture
def event_with_no_material():
    return {
        "summary": "1:1",
        "description": "Weekly sync, no agenda doc.",
        "attachments": [],
    }
