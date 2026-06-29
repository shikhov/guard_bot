from pathlib import Path

from aiohttp.web_fileresponse import FileResponse
from aiohttp.web_request import Request
from aiohttp.web_response import json_response

from aiogram import Bot
from aiogram.utils.web_app import safe_parse_webapp_init_data


async def join_request_handler(request: Request):
    return FileResponse(Path(__file__).parent.resolve() / 'html/join_request.html')


async def answer_request_handler(request: Request):
    bot: Bot = request.app["bot"]
    jsondata = await request.json()
    
    try:
        webapp_data = safe_parse_webapp_init_data(token=bot.token, init_data=jsondata['_auth'])
    except ValueError:
        return json_response({"ok": False, "error": "Unauthorized"}, status=401)

    try:
        await bot.answer_chat_join_request_query(
            chat_join_request_query_id=jsondata['query_id'],
            result='approve'
        )
    except Exception:
        return json_response({"ok": False, "error": "Unknown error"}, status=500)
    
    
    return json_response({"ok": True})
