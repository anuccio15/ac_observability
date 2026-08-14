from __future__ import annotations

import os


os.environ.setdefault(
    "AC_EDGE_API_TOKEN", "test-edge-token-that-is-at-least-32-characters"
)
os.environ.setdefault(
    "AC_DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
)
