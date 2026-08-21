# guard-bot

Telegram-бот для подтверждения заявок на вступление в чат (join requests), развёрнутый на **Cloudflare Workers** (serverless).

Проект переписан с self-hosted (aiogram long-polling + aiohttp + Docker) → Vercel (aiogram webhook + FastAPI) → **Cloudflare Workers (TypeScript)**.

## Структура

```
src/
  index.ts                  # Основной обработчик Worker (fetch + scheduled)
  validation.ts             # Валидация Telegram Web App initData (HMAC-SHA256)
wrangler.toml               # Конфигурация Cloudflare Worker + Cron Triggers
package.json                # Скрипты и зависимости Node.js
tsconfig.json               # Настройки TypeScript
```

## Эндпоинты

| Метод | Путь                  | Описание |
|-------|-----------------------|----------|
| GET   | `/join_request`        | HTML Web App, показываемый пользователю |
| POST  | `/answer_join_request` | Подтверждает заявку из Web App |
| POST  | `/webhook`             | Приём апдейтов Telegram (`chat_join_request`) |
| POST  | `/setup-webhook`       | (Пере)регистрация URL вебхука |
| GET   | `/`                    | health-check |

## Переменные окружения (Cloudflare Dashboard → Workers → Settings → Variables)

| Переменная   | Обязательно | Описание |
|--------------|-------------|----------|
| `TOKEN`      | да          | Токен бота от @BotFather |
| `CF_WORKER_URL` | нет      | URL Worker (напр. `https://guard-bot.your-subdomain.workers.dev`). Нужен только для перерегистрации вебхука из Cron-обработчика (scheduled). В fetch-запросах базовый URL определяется автоматически из `request.url` |

## Как это работает

1. Пользователь запрашивает вступление в закрытый чат.
2. Telegram доставляет апдейт `chat_join_request` на `POST /webhook`.
3. Бот отправляет пользователю сообщение с кнопкой Web App (`/join_request?query_id=...&title=...`).
4. Пользователь открывает Web App и жмёт «Войти».
5. Web App вызывает `POST /answer_join_request` с подписанными `initData` и `query_id`.
6. Сервер проверяет подпись через HMAC-SHA256 (см. `src/validation.ts`) и подтверждает заявку через Telegram API.

Вебхук автоматически настраивается через `POST /setup-webhook` или в Cron Trigger (раз в час, `wrangler.toml` → `[triggers]`). Для Cron нужно задать `CF_WORKER_URL` (без него scheduled-обработчик пропустит перерегистрацию).

## Локальный запуск

```bash
# установка зависимостей
npm install

# создание .dev.vars с переменными окружения
cp .env.example .dev.vars

# локальный запуск
npm run dev
```

Для полного локального теста вебхука Telegram нужен публичный адрес (например, через `ngrok`/`localtunnel`): вызовите `POST /setup-webhook` — базовый URL определится автоматически из запроса.

## Деплой на Cloudflare Workers

1. Импортируйте репозиторий в Cloudflare Pages/Dashboard (или `npx wrangler deploy` из CLI).
2. Задайте переменную окружения `TOKEN`. При необходимости задайте `CF_WORKER_URL` для перерегистрации вебхука по расписанию.
3. Включите Cron Trigger в настройках Worker.
4. Вызовите `POST /setup-webhook` один раз — базовый URL определится автоматически из запроса.

### Команды

| Команда        | Описание |
|----------------|----------|
| `npm install`  | Установка зависимостей |
| `npm run dev`  | Локальный запуск (wrangler dev) |
| `npm run deploy` | Деплой на Cloudflare |
| `npm run typecheck` | Проверка типов TypeScript |