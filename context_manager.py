"""История диалога в памяти процесса. После перезапуска бота она пропадает."""

from __future__ import annotations


class ContextManager:
    def __init__(self, limit: int = 20) -> None:
        self.limit = limit
        self._chats: dict[int, list[dict[str, str]]] = {}

    def history(self, chat_id: int) -> list[dict[str, str]]:
        return list(self._chats.get(chat_id, []))

    def for_request(self, chat_id: int, user_text: str) -> list[dict[str, str]]:
        messages = self.history(chat_id)
        messages.append({"role": "user", "content": user_text})
        if len(messages) > self.limit:
            return messages[-self.limit :]
        return messages

    def add(self, chat_id: int, role: str, content: str) -> int:
        messages = self._chats.setdefault(chat_id, [])
        messages.append({"role": role, "content": content})
        extra = len(messages) - self.limit
        if extra > 0:
            del messages[:extra]
            return extra
        return 0

    def stats(self, chat_id: int) -> tuple[int, int, int, int]:
        messages = self._chats.get(chat_id, [])
        user_count = sum(1 for item in messages if item["role"] == "user")
        assistant_count = sum(1 for item in messages if item["role"] == "assistant")
        characters = sum(len(item["content"]) for item in messages)
        return len(messages), user_count, assistant_count, characters

    def reset(self, chat_id: int) -> None:
        self._chats.pop(chat_id, None)
