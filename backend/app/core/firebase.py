"""Firebase Admin SDK initialization."""

import logging

import firebase_admin
from firebase_admin import credentials

_log = logging.getLogger(__name__)


def init_firebase() -> None:
    """Initialize Firebase Admin SDK (idempotent).

    Uses the GOOGLE_APPLICATION_CREDENTIALS environment variable
    which should point to the service account key JSON file.
    """
    if firebase_admin._apps:
        return

    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
    _log.info("Firebase Admin SDK initialized")
