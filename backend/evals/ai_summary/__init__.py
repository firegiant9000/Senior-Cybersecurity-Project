"""AI executive summary evaluation harness (docs/ai/eval-protocol.md)."""

import os

# The harness never opens a database session, but importing app modules builds
# Settings, which requires DATABASE_URL. Default it to an unroutable dummy so a
# run needs no database and cannot read a real organisation.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://eval-harness:unused@127.0.0.1:1/unused")
