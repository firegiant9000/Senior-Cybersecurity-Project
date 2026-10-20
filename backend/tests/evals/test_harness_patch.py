"""The harness patch: `_call_gemini_raw` split out of the sync Gemini call.

Protocol §1: the patch must not change the SDK call. These tests swap in a
fake `google.generativeai` module, so no network and no key are involved.
"""

import sys
import types
from unittest.mock import patch

from app.services import ai_summary


class _FakeResponse:
    text = '{"narrative": "n"}'


def _fake_sdk(calls: list):
    module = types.ModuleType("google.generativeai")

    def configure(**kwargs):
        calls.append(("configure", kwargs))

    class GenerativeModel:
        def __init__(self, *args, **kwargs):
            calls.append(("model", args, kwargs))

        def generate_content(self, *args, **kwargs):
            calls.append(("generate", args, kwargs))
            return _FakeResponse()

    module.configure = configure
    module.GenerativeModel = GenerativeModel
    return module


def _patched(calls):
    google_pkg = types.ModuleType("google")
    fake = _fake_sdk(calls)
    google_pkg.generativeai = fake
    return patch.dict(sys.modules, {"google": google_pkg, "google.generativeai": fake})


def test_raw_call_returns_the_sdk_response_object():
    calls: list = []
    with _patched(calls), patch.object(ai_summary, "settings") as s:
        s.GEMINI_API_KEY = "k"
        s.GEMINI_MODEL = "gemini-2.5-flash"
        response = ai_summary._call_gemini_raw("PROMPT")
    assert isinstance(response, _FakeResponse)


def test_raw_call_keeps_todays_sdk_arguments_exactly():
    calls: list = []
    with _patched(calls), patch.object(ai_summary, "settings") as s:
        s.GEMINI_API_KEY = "k"
        s.GEMINI_MODEL = "gemini-2.5-flash"
        ai_summary._call_gemini_raw("PROMPT")
    assert calls == [
        ("configure", {"api_key": "k"}),
        (
            "model",
            ("gemini-2.5-flash",),
            {"generation_config": {"response_mime_type": "application/json"}},
        ),
        ("generate", ("PROMPT",), {}),
    ]


def test_sync_call_still_returns_text():
    calls: list = []
    with _patched(calls), patch.object(ai_summary, "settings") as s:
        s.GEMINI_API_KEY = "k"
        s.GEMINI_MODEL = "gemini-2.5-flash"
        assert ai_summary._call_gemini_sync("PROMPT") == _FakeResponse.text
