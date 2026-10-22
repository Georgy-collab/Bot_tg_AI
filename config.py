"""Ключи и параметры запроса к модели."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "").strip()

MODEL = "openai/gpt-5-mini"
MAX_COMPLETION_TOKENS = 5000
MAX_CONTEXT_MESSAGES = 20
API_URL = "https://api.proxyapi.ru/v1/chat/completions"


def telegram_proxy() -> str | None:
    """Прокси для api.telegram.org. Прямое соединение с этой машины не открывается."""
    configured = os.getenv("TELEGRAM_PROXY", "").strip()
    if configured:
        return configured
    proxies = urllib.request.getproxies()
    return proxies.get("https") or proxies.get("http")


def proxy_label(proxy: str) -> str:
    parts = urlsplit(proxy)
    if parts.hostname and parts.port:
        return f"{parts.hostname}:{parts.port}"
    return parts.hostname or "задан"


def missing_settings() -> list[str]:
    missing: list[str] = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not PROXY_API_KEY:
        missing.append("PROXY_API_KEY")
    return missing
