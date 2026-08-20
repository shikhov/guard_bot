# guard-bot

Telegram-бот для подтверждения заявок на вступление в чат (join requests), развёрнутый на **Vercel** (serverless).

Проект переписан с self-hosted (aiogram long-polling + aiohttp + Docker) на **aiogram webhook + FastAPI**, потому что Vercel не умеет держать постоянный процесс поллинга.

## Структура

```
api/
  index.py                  # FastAPI-приложение (точка входа ASGI)
  html/join_request.html    # Web App-страница для подтверждения входа
crons.json                  # Vercel Cron: часовое обновление вебхука
vercel.json                 # настройки деплоя Vercel
```

## Эндпоинты

| Метод | Путь                  | Описание |
|-------|-----------------------|----------|
| GET   | `/join_request`        | HTML Web App, показываемый пользователю |
| POST  | `/answer_join_request` | Подтверждает заявку из Web App |
| POST  | `/webhook`             | Приём апдейтов Telegram (`chat_join_request`) |
| POST  | `/setup-webhook`       | (Пере)регистрация URL вебхука |
| GET   | `/`                    | health-check |

## Переменные окружения (Vercel Project Settings → Environment Variables)

| Переменная   | Обязательно | Описание |
|--------------|-------------|----------|
| `TOKEN`      | да          | Токен бота от @BotFather |
| `VERCEL_PROJECT_PRODUCTION_URL` | автоматически | Домен production (напр. `guard-bot.vercel.app`); Vercel подставляет самостоятельно БЕЗ схемы. Схема `https://` добавляется в коде. Из него берётся `WEBAPP_URL` |
| `WEBAPP_URL` | нет         | Ручное переопределение базового URL (для dev/локального теста). По умолчанию = `VERCEL_PROJECT_PRODUCTION_URL` |
| `WEBHOOK_URL`| нет         | URL вебхука; по умолчанию `WEBAPP_URL + "/webhook"` |

## Как это работает

1. Пользователь запрашивает вступление в закрытый чат.
2. Telegram доставляет апдейт `chat_join_request` на `POST /webhook`.
3. Бот отправляет пользователю ссылку на Web App (`/join_request?query_id=...&title=...`).
4. Пользователь открывает Web App и жмёт «Войти».
5. Web App вызывает `POST /answer_join_request` с подписанными `initData` и `query_id`.
6. Сервер проверяет подпись через `safe_parse_webapp_init_data` и подтверждает заявку через Telegram API.

Вебхук автоматически настраивается при холодном старте инстанса (idempotent — только если URL отличается) и дополнительно перерегистрируется раз в час с помощью Vercel Cron (`crons.json`).

## Локальный запуск

```bash
# установка зависимостей
uv sync            # или: pip install -e .

# запуск приложения
TOKEN=... WEBAPP_URL=http://localhost:8000 uvicorn api.index:app --reload --port 8000
```

Для полного локального теста вебхука Telegram нужен публичный адрес (например, через `ngrok`/`localtunnel`): укажите его в `WEBAPP_URL`/`WEBHOOK_URL` и вызовите `POST /setup-webhook`.

## Деплой на Vercel

1. Импортируйте репозиторий в Vercel (или `vercel deploy` из CLI).
2. Задайте переменную окружения `TOKEN`. Базовый URL (`WEBAPP_URL`) берётся из автоматического `VERCEL_PROJECT_PRODUCTION_URL`; отдельно его указывать не нужно.
3. Vercel сам определит Python/FastAPI-приложение по `api/index.py`.
4. Вебхук зарегистрируется на первом холодном старте и будет поддерживаться cron'ом. При желании можно один раз вызвать `POST /setup-webhook`, чтобы не ждать cron.

> Примечание: метод `Bot.send_chat_join_request_web_app` в теле обработчика перенесён из исходной версии как есть (в оригинале предполагалась кастомная сборка). Если он отсутствует в вашей версии aiogram, замените его на штатный способ отправки Web App (например, кнопку во вложении к личному сообщению).