from functools import lru_cache
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parent.parent / "content" / "pg_rules.md"


@lru_cache
def get_rules_text() -> str:
    """Cached like app/config.py's get_settings() — this is static,
    operator-edited content (app/content/pg_rules.md), not tenant data; a
    restart to pick up an edit is an accepted tradeoff for not re-reading
    disk on every /api/v1/rules call.
    """
    return _RULES_PATH.read_text(encoding="utf-8").strip()
