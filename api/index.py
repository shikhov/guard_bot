"""guard-bot для Vercel.

Serverless-версия: вместо long-polling aiohttp-бота используем aiogram + FastAPI,
который Vercel запускает как Python/ASGI-функцию. Telegram работает с ботом через
webhook, а не через polling — это ключевое изменение по сравнению с исходной
self-hosted версией.

Всё приложение лежит в одной точке входа ``api/index.py``: Vercel маршрутизирует
все запросы в экземпляр этого FastAPI-приложения.
"""
import logging
import os
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ChatJoinRequest, Update
from aiogram.utils.web_app import safe_parse_webapp_init_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

# --- Настройки из переменных окружения (Vercel) ------------------------------
TOKEN = os.getenv("TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"{WEBAPP_URL}/webhook").strip().rstrip("/")

HTML_DIR = Path(__file__).resolve().parent / "html"

# Обрабатываем только апдейты заявок на вступление в чат.
ALLOWED_UPDATES = ["chat_join_request"]

dp = Dispatcher()


def create_bot() -> Bot:
    """Создаёт свежий инстанс Bot для каждого серверного запроса.

    В serverless-среде нельзя держать соединение между запросами, поэтому
    создаём/закрываем его на каждый вызов.
    """
    return Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
@dp.chat_join_request()
async def handle_join_request(request: ChatJoinRequest, bot: Bot):
    """Пользователь запросил вступление в чат — отправляем ему Web App для
    подтверждения своей подписки (то же поведение, что и в исходной версии).
    """
    if not request.query_id:
        return

    params = {
        "query_id": request.query_id,
        "title": request.chat.title,
    }
    query_string = urllib.parse.urlencode(params, doseq=True)

    await bot.send_chat_join_request_web_app(
        chat_join_request_query_id=request.query_id,
        web_app_url=f"{WEBAPP_URL}/join_request?{query_string}",
    )


async def setup_webhook() -> dict:
    """(Пере)регистрирует URL Telegram-вебхука. Идемпотентно: ничего не делает,
    если вебхук уже указывает на нужный адрес.
    """
    bot = create_bot()
    try:
        info = await bot.get_webhook_info()
        if info.url == WEBHOOK_URL:
            logging.info("Webhook already set: %s", WEBHOOK_URL)
            return {"ok": True, "changed": False, "url": info.url}

        await bot.set_webhook(
            WEBHOOK_URL,
            allowed_updates=ALLOWED_UPDATES,
            drop_pending_updates=True,
        )
        logging.info("Webhook set to %s", WEBHOOK_URL)
        return {"ok": True, "changed": True, "url": WEBHOOK_URL}
    except Exception as exc:
        logging.exception("Failed to configure webhook")
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Холодный старт каждого инстанса: перерегистрируем вебхук, если он не на месте.

    В serverless холодный старт случается при каждом новом инстансе, но проверка
    идемпотентна и стоит одного вызова getWebhookInfo. Часовой cron (crons.json)
    — страховка, чтобы вебхук не «протух» даже без входящего трафика.
    """
    if not TOKEN:
        logging.warning("TOKEN env var is not set; bot API calls will fail")
    elif not WEBHOOK_URL:
        logging.warning("WEBHOOK_URL is empty; cannot configure webhook")
    else:
        await setup_webhook()

    yield


app = FastAPI(
    title="guard-bot",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/")
async def index():
    return JSONResponse({"status": "ok", "service": "guard-bot"})


@app.get("/join_request")
async def join_request_page():
    """Отдаёт HTML Web App для подтверждения вступления в чат."""
    return FileResponse(HTML_DIR / "join_request.html")


@app.post("/answer_join_request")
async def answer_request(request: Request):
    """Подтверждает заявку на вступление (дёргается из Web App)."""
    if not TOKEN:
        return JSONResponse({"ok": False, "error": "TOKEN not configured"}, status_code=500)

    bot = create_bot()
    try:
        jsondata = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    try:
        safe_parse_webapp_init_data(
            token=bot.token,
            init_data=jsondata.get("_auth", ""),
        )
    except ValueError:
        return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

    query_id = jsondata.get("query_id")
    if not query_id:
        return JSONResponse({"ok": False, "error": "Missing query_id"}, status_code=400)

    try:
        await bot.answer_chat_join_request_query(
            chat_join_request_query_id=query_id,
            result="approve",
        )
    except Exception:
        return JSONResponse({"ok": False, "error": "Unknown error"}, status_code=500)
    finally:
        await bot.session.close()

    return JSONResponse({"ok": True})
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Точка приёма апдейтов Telegram (chat_join_request)."""
    if not TOKEN:
        return JSONResponse({"ok": False, "error": "TOKEN not configured"}, status_code=500)

    bot = create_bot()
    try:
        raw = await request.json()
        update = Update.model_validate(raw)
        await dp.feed_update(bot, update)
    except Exception:
        logging.exception("Failed to process webhook update")
        return JSONResponse({"ok": False}, status_code=400)
    finally:
        await bot.session.close()

    return JSONResponse({"ok": True})


@app.post("/setup-webhook")
async def setup_webhook_route():
    """Вручную перерегистрировать вебхук (также вызывает cron)."""
    if not WEBHOOK_URL:
        return JSONResponse({"ok": False, "error": "WEBHOOK_URL not configured"}, status_code=400)
    return JSONResponse(await setup_webhook())