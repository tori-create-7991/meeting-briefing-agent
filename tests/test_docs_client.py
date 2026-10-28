import http.client

import httplib2
import pytest
from google.auth.exceptions import TransportError
from googleapiclient.errors import HttpError

from meeting_briefing_agent.docs_client import fetch_doc_text


class FakeDocumentsGet:
    def __init__(self, document=None, error=None):
        self._document = document
        self._error = error

    def execute(self, num_retries=0):
        if self._error:
            raise self._error
        return self._document


class FakeDocuments:
    def __init__(self, document=None, error=None):
        self._document = document
        self._error = error

    def get(self, documentId):
        return FakeDocumentsGet(self._document, self._error)


class FakeDocsService:
    def __init__(self, document=None, error=None):
        self._document = document
        self._error = error

    def documents(self):
        return FakeDocuments(self._document, self._error)


def test_fetch_doc_text_returns_none_on_http_error():
    error = HttpError(httplib2.Response({"status": 404}), b"not found")
    service = FakeDocsService(error=error)

    assert fetch_doc_text(service, "missing-doc-id") is None


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        http.client.IncompleteRead(b""),
        httplib2.HttpLib2Error("connection reset"),
        TransportError("tls failure"),
    ],
)
def test_fetch_doc_text_returns_none_on_network_errors(error):
    service = FakeDocsService(error=error)

    assert fetch_doc_text(service, "slow-doc-id") is None


def test_fetch_doc_text_returns_empty_string_for_empty_document():
    service = FakeDocsService(document={"body": {"content": []}})

    assert fetch_doc_text(service, "empty-doc-id") == ""


def test_fetch_doc_text_flattens_paragraph_text_runs():
    document = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {"textRun": {"content": "Hello "}},
                            {"textRun": {"content": "world."}},
                        ]
                    }
                },
                {"sectionBreak": {}},
            ]
        }
    }
    service = FakeDocsService(document=document)

    result = fetch_doc_text(service, "doc-id")

    assert result == "Hello world."


def test_fetch_doc_text_truncates_at_max_chars():
    document = {
        "body": {
            "content": [
                {"paragraph": {"elements": [{"textRun": {"content": "abcdef"}}]}}
            ]
        }
    }
    service = FakeDocsService(document=document)

    result = fetch_doc_text(service, "doc-id", max_chars=3)

    assert result == "abc…"
