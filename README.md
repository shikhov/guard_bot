# Telegram Join Request Bot for Cloudflare Workers

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/shikhov/guard_bot)

Telegram-бот показывает пользователю Mini App при заявке на вступление в чат и подтверждает заявку после нажатия кнопки.

## Быстрый запуск

1. Создайте бота через [@BotFather](https://t.me/BotFather) и скопируйте токен.
2. Нажмите Deploy to Cloudflare выше. Репозиторий должен быть публичным.
3. В диалоге Cloudflare введите токен в поле `TELEGRAM_BOT_TOKEN` как Secret.
4. Откройте URL созданного Worker один раз. Worker зарегистрирует Telegram webhook и вернет статус `ready`.
5. Добавьте бота в группу администратором с правом приглашать пользователей и включите заявки на вступление.

## Локальная разработка

Требуются Python, `uv` и Node.js. Скопируйте `.dev.vars.example` в `.dev.vars` и заполните токен:

```text
TELEGRAM_BOT_TOKEN=123456:replace-me
```

```bash
uv sync
uv run pywrangler dev
```

Деплой:

```bash
uv run pywrangler deploy
```

## Endpoints

- `GET /` — регистрирует webhook и показывает статус.
- `POST /telegram/webhook` — endpoint Telegram webhook.
- `GET /join_request` — Telegram Mini App.
- `POST /answer_join_request` — подтверждает заявку после проверки `initData`.

Токен хранится только в Cloudflare Secret `TELEGRAM_BOT_TOKEN`; не добавляйте `.dev.vars` или реальные токены в Git.
