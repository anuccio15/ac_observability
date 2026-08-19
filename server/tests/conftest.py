from __future__ import annotations

import os


os.environ.setdefault(
    "AC_EDGE_API_TOKEN", "test-edge-token-that-is-at-least-32-characters"
)
os.environ.setdefault(
    "AC_DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused"
)
os.environ.setdefault(
    "AC_DASHBOARD_PASSWORD_HASH",
    "pbkdf2_sha256:600000:MDEyMzQ1Njc4OWFiY2RlZg:wb2l8JuhJjo7GeppjEHJHGWc-q6HhJMJY1Jfn0ZdfuE",
)
os.environ.setdefault(
    "AC_DASHBOARD_SESSION_SECRET",
    "test-dashboard-session-secret-at-least-32-characters",
)
