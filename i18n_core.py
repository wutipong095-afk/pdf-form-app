"""UI locale helper — catalogs in locales/{th,en}.json"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from envutil import BASE

SUPPORTED = ("th", "en")
DEFAULT_LOCALE = "th"
COOKIE_NAME = "ui_lang"
# Optional process override for launcher/dev only — never written by the app.
ENV_NAME = "PDFMARKER_UI_LANG"

_DATA_DIR: Optional[Path] = None
_CATALOGS: dict[str, dict[str, Any]] = {}


def init_i18n(data_dir: Path) -> None:
    global _DATA_DIR
    _DATA_DIR = data_dir


def locales_dir() -> Path:
    return BASE / "locales"


def ui_lang_path() -> Optional[Path]:
    if _DATA_DIR is None:
        return None
    return _DATA_DIR / "ui_lang.txt"


def normalize_locale(raw: Optional[str]) -> str:
    if not raw:
        return DEFAULT_LOCALE
    v = str(raw).strip().lower().replace("_", "-")
    if v.startswith("en"):
        return "en"
    if v.startswith("th"):
        return "th"
    return DEFAULT_LOCALE


def _load_catalog(locale: str) -> dict[str, Any]:
    loc = normalize_locale(locale)
    if loc in _CATALOGS:
        return _CATALOGS[loc]
    path = locales_dir() / f"{loc}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    _CATALOGS[loc] = data
    return data


def _lookup(catalog: dict[str, Any], key: str) -> Optional[str]:
    cur: Any = catalog
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) else None


def get_locale() -> str:
    try:
        from flask import has_request_context, request

        if has_request_context():
            c = request.cookies.get(COOKIE_NAME)
            if c:
                return normalize_locale(c)
            arg = request.args.get("lang")
            if arg:
                return normalize_locale(arg)
    except ImportError:
        pass

    # Persisted preference (shared on this PC) before optional env override
    path = ui_lang_path()
    if path and path.is_file():
        try:
            return normalize_locale(path.read_text(encoding="utf-8").splitlines()[0])
        except (OSError, IndexError):
            pass

    env = os.environ.get(ENV_NAME)
    if env:
        return normalize_locale(env)

    return DEFAULT_LOCALE


def set_persisted_locale(locale: str) -> str:
    """Persist locale to ui_lang.txt only — do not mutate process env."""
    loc = normalize_locale(locale)
    path = ui_lang_path()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(loc + "\n", encoding="utf-8")
    return loc


def t(key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
    loc = normalize_locale(locale or get_locale())
    text = _lookup(_load_catalog(loc), key)
    if text is None and loc != DEFAULT_LOCALE:
        text = _lookup(_load_catalog(DEFAULT_LOCALE), key)
    if text is None:
        text = key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
