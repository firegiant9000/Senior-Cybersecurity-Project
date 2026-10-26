"""Tests for the deploy info reported by the public /health endpoints."""

import re
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.deploy_info import deployed_commit, scheduler_state


def test_git_commit_prefers_render_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "ABCDEF0123456789abcdef0123456789abcdef01")
    monkeypatch.setenv("GIT_COMMIT", "1111111")
    assert deployed_commit() == "abcdef012345"


def test_git_commit_falls_back_to_build_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "1234567890abcdef")
    assert deployed_commit() == "1234567890ab"


def test_git_commit_unknown_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert deployed_commit() == "unknown"


def test_git_commit_unknown_for_dockerfile_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "unknown")
    assert deployed_commit() == "unknown"


def test_git_commit_rejects_non_hex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "not a sha; <script>")
    assert deployed_commit() == "unknown"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "main")
    assert deployed_commit() == "unknown"
    monkeypatch.setenv("RENDER_GIT_COMMIT", " abc1234 \n")
    assert deployed_commit() == "abc1234"


def test_scheduler_state_when_not_running() -> None:
    fake = MagicMock()
    fake.running = False
    with patch("app.services.deploy_info.scheduler", fake):
        assert scheduler_state() == (settings.SCHEDULER_ENABLED, 0)


def test_scheduler_state_counts_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    fake = MagicMock()
    fake.running = True
    fake.get_jobs.return_value = [object(), object(), object()]
    with patch("app.services.deploy_info.scheduler", fake):
        assert scheduler_state() == (True, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/health", "/api/v1/health"])
async def test_health_includes_deploy_fields(anon_client: AsyncClient, path: str) -> None:
    response = await anon_client.get(path)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "status",
        "service",
        "version",
        "environment",
        "git_commit",
        "scheduler_enabled",
        "scheduled_jobs",
    }
    assert data["git_commit"] == "unknown" or re.fullmatch(r"[0-9a-f]{7,12}", data["git_commit"])
    assert isinstance(data["scheduler_enabled"], bool)
    assert isinstance(data["scheduled_jobs"], int) and data["scheduled_jobs"] >= 0
