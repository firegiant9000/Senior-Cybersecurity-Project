"""The production Gemini call: pinned settings (protocol §1) and the timeout fallback.

The eval harness pins its settings in backend/evals/ai_summary/eval_config.yaml.
These tests assert that production sends exactly those values, so the eval
measures what ships. No test here touches the network: google.genai.Client is
replaced by a recorder.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.genai import types

from app.core.config import Settings
from app.db.organization import Organization
from app.schemas.ai_summary import StructuredSummary
from app.services import ai_summary
from evals.ai_summary.config import load_config
from evals.ai_summary.run_eval import _sdk_name_of

CFG = load_config()


class _RecordingClient:
    """Stands in for google.genai.Client and records what production passes."""

    instances: list["_RecordingClient"] = []
    raises: BaseException | None = None
    response: object | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[dict] = []
        self.models = SimpleNamespace(generate_content=self._generate_content)
        _RecordingClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def _generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if _RecordingClient.raises is not None:
            raise _RecordingClient.raises
        return _RecordingClient.response or SimpleNamespace(text="{}")


@pytest.fixture
def recording_client(monkeypatch):
    _RecordingClient.instances = []
    _RecordingClient.raises = None
    _RecordingClient.response = None
    monkeypatch.setattr("google.genai.Client", _RecordingClient)
    yield _RecordingClient
    _RecordingClient.raises = None
    _RecordingClient.response = None


def test_empty_response_raises_a_named_error(recording_client):
    """google-genai returns text=None for a blocked or empty response; say why."""
    recording_client.response = SimpleNamespace(
        text=None,
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="SAFETY"))],
        prompt_feedback=None,
    )
    with patch("app.services.ai_summary.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_MODEL = CFG.model
        with pytest.raises(ai_summary.GeminiEmptyResponseError, match="SAFETY"):
            ai_summary._call_gemini_sync("the prompt")


def test_production_imports_the_eval_sdk():
    assert CFG.sdk_target == "google-genai"
    assert _sdk_name_of(ai_summary) == CFG.sdk_target


def test_production_default_model_matches_eval_config():
    assert Settings.model_fields["GEMINI_MODEL"].default == CFG.model


def test_call_gemini_raw_sends_the_pinned_settings(recording_client):
    with patch("app.services.ai_summary.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_MODEL = CFG.model
        ai_summary._call_gemini_raw("the prompt")

    (client,) = recording_client.instances
    assert client.kwargs["api_key"] == "test-key"
    http = client.kwargs["http_options"]
    assert http.timeout == CFG.timeout_ms
    # One attempt only: a retry would be billed and would hide failures.
    assert http.retry_options.attempts == 1

    (call,) = client.calls
    assert call["model"] == CFG.model
    assert call["contents"] == "the prompt"
    config = call["config"]
    assert config.temperature == CFG.temperature
    assert config.top_p == CFG.top_p
    assert config.top_k == CFG.top_k
    assert config.candidate_count == CFG.candidate_count
    assert config.seed == CFG.seed
    assert config.max_output_tokens == CFG.max_output_tokens
    assert config.thinking_config.thinking_level == types.ThinkingLevel(CFG.thinking_level.upper())
    assert config.response_mime_type == "application/json"
    assert config.response_schema is StructuredSummary


@pytest.mark.asyncio
async def test_timeout_uses_the_existing_fallback(recording_client):
    """A timeout from the SDK takes the last-good lookup, then the template."""
    recording_client.raises = httpx.ReadTimeout("timed out")

    org = MagicMock(spec=Organization)
    org.id = 7
    org.name = "Gamma"
    org.industry_label = "Retail"
    org.employee_range = "11-50"
    org.primary_state = "OH"

    report = MagicMock()
    report.summary.total = 1
    report.summary.by_severity = {}
    report.assessment_tier = "partial"
    report.data_sources_used = []
    report.findings = []

    db = MagicMock()
    snap = MagicMock()
    snap.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=snap)

    with (
        patch("app.services.ai_summary.FindingsEngine") as engine_cls,
        patch(
            "app.services.ai_summary._get_feedback_meta", new_callable=AsyncMock, return_value=None
        ),
        patch("app.services.ai_summary.settings") as mock_settings,
        patch("app.services.ai_summary.SqlAISummaryGenerationRepository") as repo_cls,
    ):
        engine_cls.return_value.build = AsyncMock(return_value=report)
        mock_settings.AI_SUMMARY_ENABLED = True
        mock_settings.GEMINI_API_KEY = "test-key"
        mock_settings.GEMINI_MODEL = CFG.model
        mock_settings.AI_SUMMARY_CACHE_TTL = 3600
        repo = AsyncMock()
        repo.get_last_successful_gemini.return_value = None
        repo_cls.return_value = repo

        svc = ai_summary.AISummaryService(db)
        svc.invalidate(org.id)
        result = await svc.build(org)

    # The timeout came from the new SDK call, not from an import or setup error.
    assert len(recording_client.instances[-1].calls) == 1
    repo.get_last_successful_gemini.assert_awaited_once_with(org.id)
    kwargs = repo.create.call_args.kwargs
    assert kwargs["status"] == "fallback_used"
    assert kwargs["source"] == "fallback"
    assert result.ai_generated is False
