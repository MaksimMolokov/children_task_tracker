"""
Обработка действий детей: подтверждение выполнения заданий и отправка медиа.
См. SPEC.md раздел 5 "Выдача задач и подтверждение выполнения"
"""
from aiogram import Router
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import get_task_completion_keyboard

router = Router()


@router.callback_query(lambda c: c.data == "task_complete")
async def handle_task_complete_callback(callback: CallbackQuery):
    """
    Обработка нажатия кнопки "✅ Выполнил"
    См. SPEC.md раздел 5.2 "Обработка нажатия '✅ Выполнил'"
    
    Шаги:
    1. Находим task по chat_id + message_id
    2. Проверяем status = pending
    3. Если requires_media = false -> статус = done
    4. Если requires_media = true -> ожидаем медиа
    """
    # TODO: Реализовать логику обработки callback
    await callback.answer("Задание отмечено как выполненное!")


@router.message(lambda m: m.photo or m.video or m.document)
async def handle_media(message: Message):
    """
    Обработка медиа (фото/видео/документы) от детей
    См. SPEC.md раздел 5.3 "Обработка медиа"
    
    Шаги:
    1. Проверяем, есть ли ожидание медиа для этого ребёнка
    2. Проверяем, что это reply на сообщение с заданием
    3. Сохраняем task_media и обновляем статус задачи
    """
    # TODO: Реализовать логику обработки медиа
    if message.reply_to_message:
        await message.answer("Медиа получено! Задание засчитано 💪")
    else:
        await message.answer(
            "Пожалуйста, отправьте медиа ответом на сообщение с заданием "
            "(нажмите на сообщение и выберите 'Ответить')."
        )


