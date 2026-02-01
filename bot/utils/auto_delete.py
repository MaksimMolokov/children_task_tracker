"""
Утилита для отложенного удаления сообщений бота.
Используется для автоудаления настроечных сообщений через 15 секунд.
"""
import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

AUTO_DELETE_DELAY = 15


async def schedule_message_delete(bot: "Bot", chat_id: int, message_id: int, delay: int = AUTO_DELETE_DELAY) -> None:
    """
    Планирует удаление сообщения бота через заданное количество секунд.
    Запускается в фоне, не блокирует обработчик.
    """
    async def _delete():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.debug(f"Could not delete message {message_id}: {e}")

    asyncio.create_task(_delete())
