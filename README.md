# Bot_tg_AI

Консольный клиент к языковым моделям через [ProxyAPI](https://proxyapi.ru/). Скрипт `api_client.py` отправляет один запрос на `https://api.proxyapi.ru/v1/chat/completions` и печатает ответ в терминал.

## Требования

- Python 3.12
- Ключ ProxyAPI

## Установка

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

В `.env` вставьте ключ:

```text
PROXY_API_KEY=ваш_ключ
```

Ключ берётся в личном кабинете ProxyAPI, а не у OpenAI, Anthropic или Google.

1. Зарегистрируйтесь в [консоли ProxyAPI](https://console.proxyapi.ru/register) и подтвердите почту.
2. Откройте раздел [Ключи API](https://console.proxyapi.ru/keys) и нажмите «Создать новый ключ API».
3. Скопируйте строку, которая начинается с `sk-`. Целиком она показывается только сразу после создания. Если ключ потерян, создайте новый.

Одного ключа хватает для всех моделей из списка ниже. Пока на балансе нет денег, запрос не выполнится: пополнение — в разделе «Биллинг» того же кабинета. Подробности — в [документации по ключам](https://proxyapi.ru/docs/api-keys).

Файл `.env` не коммитится.

## Запуск

```powershell
python api_client.py
```

Скрипт по очереди спрашивает:

1. Модель. Enter оставляет `openai/gpt-5-mini`. Можно ввести номер или идентификатор из списка.
2. Запрос.
3. Температуру от 0 до 1. По умолчанию `0.7`. Дробь можно писать через запятую.
4. `max_tokens`. По умолчанию `1000`.
5. Системное сообщение. Enter пропускает его.

Ответ модели выводится в консоль.

## Модели

| Номер | Идентификатор |
| --- | --- |
| 1 | `openai/gpt-5-mini` |
| 2 | `openai/gpt-5` |
| 3 | `openai/gpt-5-nano` |
| 4 | `anthropic/claude-haiku-4-5` |
| 5 | `google/gemini-2.5-flash` |

Для Claude и Gemini нужен полный идентификатор с вендором. Короткое имя вроде `claude-haiku-4-5` на этом адресе вернёт ошибку. Подробности — в [документации ProxyAPI](https://proxyapi.ru/docs/models).
