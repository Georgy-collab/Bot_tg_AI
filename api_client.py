"""Консольный запрос к языковой модели через ProxyAPI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

API_URL = "https://api.proxyapi.ru/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-5-mini"
MODELS = (
    "openai/gpt-5-mini",
    "openai/gpt-5",
    "openai/gpt-5-nano",
    "anthropic/claude-haiku-4-5",
    "google/gemini-2.5-flash",
)
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000


def prompt_line(label: str) -> str:
    return input(label).strip()


def choose_model() -> str:
    print("Модели:")
    for index, model in enumerate(MODELS, start=1):
        suffix = " — по умолчанию" if model == DEFAULT_MODEL else ""
        print(f"  {index}. {model}{suffix}")

    hint = f"Номер или идентификатор [{DEFAULT_MODEL}]: "
    while True:
        raw = prompt_line(hint)
        if not raw:
            return DEFAULT_MODEL
        if raw.isdigit() and 1 <= int(raw) <= len(MODELS):
            return MODELS[int(raw) - 1]
        if raw in MODELS:
            return raw
        print("Выберите модель из списка: номер или полный идентификатор.")


def read_query() -> str:
    while True:
        text = prompt_line("Запрос: ")
        if text:
            return text
        print("Запрос не может быть пустым.")


def read_temperature() -> float:
    while True:
        raw = prompt_line(f"Температура от 0 до 1 [{DEFAULT_TEMPERATURE}]: ")
        if not raw:
            return DEFAULT_TEMPERATURE
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            print("Введите число, например 0.7.")
            continue
        if 0 <= value <= 1:
            return value
        print("Температура должна быть от 0 до 1.")


def read_max_tokens() -> int:
    while True:
        raw = prompt_line(f"max_tokens [{DEFAULT_MAX_TOKENS}]: ")
        if not raw:
            return DEFAULT_MAX_TOKENS
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("Введите целое число больше нуля.")


def read_system_message() -> str | None:
    text = prompt_line("Системное сообщение (Enter — пропустить): ")
    return text or None


def load_api_key() -> str:
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)
    key = os.getenv("PROXY_API_KEY", "").strip()
    if not key:
        sys.exit(
            "Не найден ключ PROXY_API_KEY.\n"
            "Скопируйте .env.example в .env и вставьте ключ ProxyAPI."
        )
    return key


def build_messages(query: str, system_message: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": query})
    return messages


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


def limit_parameter(model: str) -> str:
    """Модели OpenAI вроде gpt-5 принимают max_completion_tokens, не max_tokens."""
    if model.startswith("openai/"):
        return "max_completion_tokens"
    return "max_tokens"


def post_chat(api_key: str, payload: dict) -> requests.Response:
    return requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )


def ask(
    api_key: str,
    model: str,
    query: str,
    temperature: float,
    max_tokens: int,
    system_message: str | None,
) -> tuple[str, dict, str, float]:
    limit_name = limit_parameter(model)
    used_temperature = temperature
    payload = {
        "model": model,
        "messages": build_messages(query, system_message),
        "temperature": used_temperature,
        limit_name: max_tokens,
    }
    response = post_chat(api_key, payload)
    for _ in range(2):
        if response.ok:
            break
        text = response.text
        alternate = (
            "max_tokens" if limit_name == "max_completion_tokens" else "max_completion_tokens"
        )
        if response.status_code == 400 and alternate in text and limit_name in text:
            payload.pop(limit_name)
            limit_name = alternate
            payload[limit_name] = max_tokens
            response = post_chat(api_key, payload)
            continue
        if response.status_code == 400 and "Only the default" in text and "temperature" in text:
            used_temperature = 1
            payload["temperature"] = used_temperature
            response = post_chat(api_key, payload)
            continue
        break
    if not response.ok:
        detail = response.text.strip() or response.reason
        sys.exit(f"Ошибка API ({response.status_code}): {detail}")

    try:
        data = response.json()
        content = message_text(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, ValueError):
        sys.exit(f"Неожиданный ответ API: {response.text.strip()}")

    if not content.strip():
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details")
        reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, dict) else None
        finish_reason = ""
        choices = data.get("choices") if isinstance(data.get("choices"), list) else []
        if choices and isinstance(choices[0], dict):
            finish_reason = str(choices[0].get("finish_reason") or "")
        if finish_reason == "length" and isinstance(reasoning_tokens, int) and reasoning_tokens > 0:
            sys.exit(
                "Модель израсходовала лимит токенов на рассуждение и не успела написать ответ. "
                f"Увеличьте max_tokens: сейчас {max_tokens}, на рассуждение ушло {reasoning_tokens}."
            )
        sys.exit(f"Модель вернула пустой ответ: {response.text.strip()}")
    return content, data, limit_name, used_temperature


def token_count(usage: dict, key: str) -> str:
    value = usage.get(key)
    if isinstance(value, int):
        return str(value)
    return "нет в ответе"


def print_result(
    content: str,
    data: dict,
    requested_model: str,
    temperature: float,
    used_temperature: float,
    max_tokens: int,
    limit_name: str,
    system_message: str | None,
) -> None:
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    finish_reason = ""
    if choices and isinstance(choices[0], dict):
        finish_reason = str(choices[0].get("finish_reason") or "")
    model = data.get("model") or requested_model

    print(content)
    print()
    print("Токены:")
    print(f"  вход: {token_count(usage, 'prompt_tokens')}")
    print(f"  ответ: {token_count(usage, 'completion_tokens')}")
    print(f"  всего: {token_count(usage, 'total_tokens')}")
    print("Параметры:")
    print(f"  модель: {model}")
    if used_temperature == temperature:
        print(f"  temperature: {used_temperature}")
    else:
        print(
            f"  temperature: {used_temperature} "
            f"(модель принимает только это значение, запрошено {temperature})"
        )
    print(f"  {limit_name}: {max_tokens}")
    print(f"  system_message: {system_message or 'не задано'}")
    if finish_reason:
        print(f"  finish_reason: {finish_reason}")


def main() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    api_key = load_api_key()
    model = choose_model()
    query = read_query()
    temperature = read_temperature()
    max_tokens = read_max_tokens()
    system_message = read_system_message()

    content, data, limit_name, used_temperature = ask(
        api_key=api_key,
        model=model,
        query=query,
        temperature=temperature,
        max_tokens=max_tokens,
        system_message=system_message,
    )
    print()
    print_result(
        content,
        data,
        requested_model=model,
        temperature=temperature,
        used_temperature=used_temperature,
        max_tokens=max_tokens,
        limit_name=limit_name,
        system_message=system_message,
    )


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as error:
        sys.exit(f"Не удалось выполнить запрос: {error}")
    except KeyboardInterrupt:
        sys.exit("\nПрервано.")
