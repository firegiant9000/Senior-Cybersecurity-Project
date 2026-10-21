"""The harness patch: `_call_gemini_raw` split out of the sync Gemini call.

Stage A's tests pinned the legacy `google.generativeai` call exactly, because
the patch must not change the SDK call (protocol §1). Stage C replaced that
call on purpose (google-genai with the §1 settings); the arguments it sends are
pinned in tests/test_ai_summary_gemini_call.py. These tests keep the seam's
contract: the raw call returns the SDK response object, and the sync call its
text. A fake `google.genai.Client` means no network and no key.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import ai_summary


class _FakeResponse:
    text = '{"narrative": "n"}'


class _FakeClient:
    def __init__(self, **kwargs):
        self.models = SimpleNamespace(generate_content=lambda **kw: _FakeResponse())

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_client(monkeypatch):
    monkeypatch.setattr("google.genai.Client", _FakeClient)


def test_raw_call_returns_the_sdk_response_object(fake_client):
    with patch.object(ai_summary, "settings") as s:
        s.GEMINI_API_KEY = "k"
        s.GEMINI_MODEL = "gemini-3.6-flash"
        response = ai_summary._call_gemini_raw("PROMPT")
    assert isinstance(response, _FakeResponse)


def test_sync_call_still_returns_text(fake_client):
    with patch.object(ai_summary, "settings") as s:
        s.GEMINI_API_KEY = "k"
        s.GEMINI_MODEL = "gemini-3.6-flash"
        assert ai_summary._call_gemini_sync("PROMPT") == _FakeResponse.text
