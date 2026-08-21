"""Cloudflare Worker entrypoint for the Telegram join-request bot."""

import hashlib
import hmac
import json
from urllib.parse import parse_qsl, urlencode, urlsplit

from js import Request as JsRequest
from js import fetch
from workers import Response, WorkerEntrypoint


TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def json_response(payload: dict, status: int = 200) -> Response:
    return Response(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def text_response(body: str, status: int = 200, content_type: str = "text/plain") -> Response:
    return Response(body, status=status, headers={"Content-Type": content_type})


def webhook_secret(token: str) -> str:
    """Create a stable Telegram webhook secret without another user setting."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_web_app_init_data(init_data: str, token: str, max_age: int = 86400) -> bool:
    """Validate Telegram Mini App initData according to Telegram's HMAC scheme."""
    if not init_data:
        return False

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        return False

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(values.items())
    )
    secret_key = hmac.new(
        b"WebAppData", token.encode("utf-8"), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        return False

    auth_date = values.get("auth_date")
    if auth_date:
        try:
            if __import__("time").time() - int(auth_date) > max_age:
                return False
        except ValueError:
            return False
    return True


async def telegram_call(token: str, method: str, payload: dict) -> dict:
    response = await fetch(
        TELEGRAM_API.format(token=token, method=method),
        {
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload),
        },
    )
    result = await response.json()
    if not result.get("ok"):
        description = result.get("description", "Telegram API request failed")
        raise RuntimeError(description)
    return result


def mini_app_url(request_url: str, query_id: str, title: str) -> str:
    parts = urlsplit(request_url)
    path = "/join_request"
    return f"{parts.scheme}://{parts.netloc}{path}?{urlencode({'query_id': query_id, 'title': title})}"


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        token = getattr(self.env, "TELEGRAM_BOT_TOKEN", None)
        if not token:
            return json_response({"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}, 500)

        method = request.method.upper()
        path = urlsplit(request.url).path.rstrip("/") or "/"

        if method == "GET" and path == "/":
            return await self._setup(request, token)
        if method == "GET" and path == "/join_request":
            asset_request = JsRequest(request.url.replace("/join_request", "/join_request.html"))
            return await self.env.ASSETS.fetch(asset_request)
        if method == "POST" and path == "/telegram/webhook":
            return await self._webhook(request, token)
        if method == "POST" and path == "/answer_join_request":
            return await self._answer_join_request(request, token)
        return json_response({"ok": False, "error": "Not found"}, 404)

    async def _setup(self, request, token: str) -> Response:
        webhook_url = f"{urlsplit(request.url).scheme}://{urlsplit(request.url).netloc}/telegram/webhook"
        try:
            info = await telegram_call(token, "getWebhookInfo", {})
            current_url = info.get("result", {}).get("url", "")
            if current_url != webhook_url:
                await telegram_call(
                    token,
                    "setWebhook",
                    {
                        "url": webhook_url,
                        "secret_token": webhook_secret(token),
                        "allowed_updates": ["chat_join_request"],
                    },
                )
            return json_response({"ok": True, "status": "ready", "webhook": webhook_url})
        except Exception as error:
            return json_response({"ok": False, "error": str(error)}, 502)

    async def _webhook(self, request, token: str) -> Response:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != webhook_secret(token):
            return json_response({"ok": False, "error": "Unauthorized"}, 401)

        try:
            update = await request.json()
            join_request = update.get("chat_join_request")
            if not join_request or not join_request.get("query_id"):
                return json_response({"ok": True})

            query_id = join_request["query_id"]
            chat = join_request.get("chat") or {}
            await telegram_call(
                token,
                "sendChatJoinRequestWebApp",
                {
                    "chat_join_request_query_id": query_id,
                    "web_app_url": mini_app_url(
                        request.url, query_id, chat.get("title", "")
                    ),
                },
            )
            return json_response({"ok": True})
        except (ValueError, KeyError, RuntimeError) as error:
            return json_response({"ok": False, "error": str(error)}, 400)
        except Exception:
            return json_response({"ok": False, "error": "Internal server error"}, 500)

    async def _answer_join_request(self, request, token: str) -> Response:
        try:
            data = await request.json()
            if not validate_web_app_init_data(data.get("_auth", ""), token):
                return json_response({"ok": False, "error": "Unauthorized"}, 401)
            query_id = data.get("query_id")
            if not query_id:
                return json_response({"ok": False, "error": "query_id is required"}, 400)
            await telegram_call(
                token,
                "answerChatJoinRequestQuery",
                {"chat_join_request_query_id": query_id, "result": "approve"},
            )
            return json_response({"ok": True})
        except (ValueError, KeyError):
            return json_response({"ok": False, "error": "Invalid JSON"}, 400)
        except RuntimeError as error:
            return json_response({"ok": False, "error": str(error)}, 502)
