import asyncio
import logging

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ChatJoinRequest
import urllib

import webapp.routes

from config import TOKEN, PORT, WEBAPP_URL


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logging.getLogger("aiogram.event").setLevel(logging.WARNING) 

dp = Dispatcher()

@dp.chat_join_request()
async def handle_join_request(request: ChatJoinRequest, bot: Bot):
    if request.query_id:
        params = {
            'query_id': request.query_id,
            'title': request.chat.title
        }
        query_string = urllib.parse.urlencode(params, doseq=True)
        await bot.send_chat_join_request_web_app(
            chat_join_request_query_id=request.query_id,
            web_app_url=f'{WEBAPP_URL}/join_request?{query_string}'
        )


def create_webapp_server():
    app = web.Application()
    app.router.add_get('/join_request', webapp.routes.join_request_handler)
    app.router.add_post('/answer_join_request', webapp.routes.answer_request_handler)
    
    return app



async def main():    
    botProperties = DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True)
    bot = Bot(token=TOKEN, default=botProperties)

    web_app = create_webapp_server()
    web_app['bot'] = bot
    web_runner = web.AppRunner(web_app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, '0.0.0.0', PORT)
    await site.start()

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
