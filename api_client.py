"""Запрос к ProxyAPI. Температура не передаётся: у модели остаётся значение по умолчанию."""

from __future__ import annotations

import logging

import requests

from config import API_URL, MAX_COMPLETION_TOKENS, MODEL, PROXY_API_KEY

logger = logging.getLogger("api_client")


class ApiError(Exception):
    """Запрос к модели не выполнен."""


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def ask(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }
    logger.info(
        "Параметры запроса: model=%s, temperature=по умолчанию, max_completion_tokens=%s, сообщений=%s",
        MODEL,
        MAX_COMPLETION_TOKENS,
        len(messages),
    )

    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {PROXY_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
    except requests.RequestException as error:
        logger.error("Сетевая ошибка: %s", error)
        raise ApiError("Не удалось связаться с ProxyAPI.") from error

    if not response.ok:
        detail = response.text.strip() or response.reason
        logger.error("Ошибка API %s: %s", response.status_code, detail[:2000])
        raise ApiError(f"ProxyAPI вернул ошибку {response.status_code}.")

    try:
        data = response.json()
        content = message_text(data["choices"][0]["message"]["content"])
        finish_reason = str(data["choices"][0].get("finish_reason") or "")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    except (KeyError, IndexError, TypeError, ValueError) as error:
        logger.error("Неожиданный ответ API: %s", response.text.strip()[:2000])
        raise ApiError("ProxyAPI вернул неожиданный ответ.") from error

    logger.info(
        "Ответ получен: finish_reason=%s, prompt_tokens=%s, completion_tokens=%s, total_tokens=%s",
        finish_reason or "нет",
        usage.get("prompt_tokens", "нет"),
        usage.get("completion_tokens", "нет"),
        usage.get("total_tokens", "нет"),
    )

    if content.strip():
        return content

    details = usage.get("completion_tokens_details")
    reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
    if finish_reason == "length" and isinstance(reasoning_tokens, int) and reasoning_tokens > 0:
        logger.error(
            "Пустой ответ: лимит ушёл на рассуждение, reasoning_tokens=%s, max_completion_tokens=%s",
            reasoning_tokens,
            MAX_COMPLETION_TOKENS,
        )
        raise ApiError("Модель не успела написать ответ в заданном лимите токенов.")

    logger.error("Пустой ответ API: %s", response.text.strip()[:2000])
    raise ApiError("Модель вернула пустой ответ.")
