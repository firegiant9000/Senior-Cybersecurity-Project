"""Firebase Admin SDK initialization."""

import json
import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

_log = logging.getLogger(__name__)


def init_firebase() -> None:
    """Initialize Firebase Admin SDK (idempotent).

    Uses the GOOGLE_APPLICATION_CREDENTIALS environment variable
    which should point to the service account key JSON file.
    """
    if firebase_admin._apps:
        return

    cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS.strip()
    project_id = settings.FIREBASE_PROJECT_ID.strip()

    if cred_path:
        # Support relative paths from backend/.env (e.g. "./service-account.json").
        resolved = Path(cred_path)
        if not resolved.is_absolute():
            resolved = Path(__file__).resolve().parents[2] / resolved
        cred = credentials.Certificate(str(resolved))
        if not project_id:
            # Use the service-account project when FIREBASE_PROJECT_ID is not explicitly set.
            try:
                project_id = json.loads(resolved.read_text()).get("project_id", "")
            except (OSError, ValueError):  # pragma: no cover - defensive only
                project_id = ""
    else:
        cred = credentials.ApplicationDefault()

    options = {"projectId": project_id} if project_id else None
    firebase_admin.initialize_app(cred, options)
    _log.info(
        "Firebase Admin SDK initialized (project_id=%s, cred_path=%s)",
        project_id or "<empty>",
        cred_path or "<adc>",
    )
