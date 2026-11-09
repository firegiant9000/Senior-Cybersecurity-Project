"""Startup Firebase credential resolution on hosts that pass the key as an env var."""

import json
import tempfile
from unittest.mock import patch

from app.core import firebase
from app.core.config import settings
from app.main import _ensure_firebase_credentials


def test_service_account_json_wins_over_stale_credentials_path(monkeypatch, tmp_path):
    # Render: a leftover GOOGLE_APPLICATION_CREDENTIALS can point at a file that never
    # exists, and the key arrives in FIREBASE_SERVICE_ACCOUNT_JSON instead.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "/app/service-account.json")
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/service-account.json")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", json.dumps({"project_id": "test-project"}))

    _ensure_firebase_credentials()

    written = tmp_path / "firebase-service-account.json"
    with (
        patch.object(firebase.firebase_admin, "_apps", {}),
        patch.object(firebase.credentials, "Certificate") as certificate,
        patch.object(firebase.firebase_admin, "initialize_app"),
    ):
        firebase.init_firebase()

    certificate.assert_called_once_with(str(written))


def test_without_service_account_json_the_configured_path_is_kept(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", "/srv/key.json")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)

    _ensure_firebase_credentials()

    assert settings.GOOGLE_APPLICATION_CREDENTIALS == "/srv/key.json"
