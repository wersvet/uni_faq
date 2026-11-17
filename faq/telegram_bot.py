"""Telegram is an adapter; all retrieval runs in the same server as the website."""
import asyncio
import logging
import os
from pathlib import Path
from telegram.ext import Application,CommandHandler,MessageHandler,filters
from .client import request,format_answer
logging.basicConfig(level=logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

class SafeFormatter(logging.Formatter):
    def format(self,record):
        value=super().format(record)
        token=os.getenv('TELEGRAM_BOT_TOKEN')
        return value.replace(token,'[TOKEN]') if token else value
for handler in logging.getLogger().handlers:handler.setFormatter(SafeFormatter('%(levelname)s: %(message)s'))

async def start(update,context):
    context.user_data.clear()
    await update.message.reply_text('Привет! Я учебный FAQ-помощник AITU. Спросите о поступлении, общежитии, экзаменах или обучении. Я ищу по материалам университета и показываю источники. /reset — новая тема. Переписка не записывается в базу.')

async def answer(update,context):
    try:
        result=await asyncio.to_thread(request,'/chat',{'text':update.message.text,'state':context.user_data.get('state',{})})
        context.user_data['state']=result['state']
        text=format_answer(result)
        for offset in range(0,len(text),3900):await update.message.reply_text(text[offset:offset+3900])
    except Exception:
        logging.error('Не удалось получить ответ от локального поиска')
        await update.message.reply_text('Не удалось выполнить поиск. Проверьте, что приложение запущено на компьютере; попробуйте ещё раз.')

async def ready(app):
    me=await app.bot.get_me()
    # Existing webhook is not deleted automatically: avoid disrupting another deployment.
    webhook=await app.bot.get_webhook_info()
    if webhook.url:raise RuntimeError('У бота активен webhook. Отключите прежнее размещение перед локальным запуском.')
    marker=os.getenv('FAQ_TELEGRAM_READY')
    if marker:Path(marker).write_text(me.username)


def main():
    token=os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:raise SystemExit('Нет токена: выполните python3 start.py')
    app=Application.builder().token(token).post_init(ready).build()
    app.add_handler(CommandHandler(['start','help','reset'],start))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,answer))
    app.run_polling(drop_pending_updates=False)

if __name__=='__main__':main()
