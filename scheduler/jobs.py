"""
Планировщик задач (APScheduler).
См. SPEC.md раздел 6 "Автоматическое закрытие задач и отчёты"
и раздел 5.1 "Создание задач по расписанию"
"""
import logging
from datetime import date, datetime, time, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone

from bot.config import ADMIN_TELEGRAM_ID, TIMEZONE
from bot.keyboards.inline import get_task_completion_keyboard
from bot.services.report_service import ReportService
from bot.services.schedule_service import ScheduleService
from bot.services.task_service import TaskService
from db.database import AsyncSessionLocal
from db.models import TaskStatus

logger = logging.getLogger(__name__)

# Импорт Bot нужен для отправки сообщений из джобов
from aiogram import Bot

bot_instance: Bot | None = None


def set_bot_instance(bot: Bot):
    """Установка экземпляра бота для использования в джобах"""
    global bot_instance
    bot_instance = bot


async def create_daily_tasks():
    """
    Создание задач по расписанию (scheduler job).
    См. SPEC.md раздел 5.1 "Создание задач по расписанию"
    
    Запускается каждую минуту/5 минут для проверки активных расписаний.
    """
    if not bot_instance:
        logger.error("Bot instance не установлен")
        return

    async with AsyncSessionLocal() as session:
        try:
            # Получаем текущее локальное время
            tz = timezone(TIMEZONE)
            now = datetime.now(tz)
            current_time = now.time().replace(second=0, microsecond=0)
            current_date = now.date()

            # Получаем активные расписания для текущего времени
            schedules = await ScheduleService.get_active_schedules_for_time(
                session, current_time, current_date
            )

            if not schedules:
                return

            logger.info(f"Найдено {len(schedules)} активных расписаний на {current_time}")

            for schedule in schedules:
                # Получаем целевых детей для этого расписания
                children = await ScheduleService.get_target_children_for_schedule(
                    session, schedule
                )

                for child in children:
                    try:
                        # Отправляем только в личные сообщения ребёнка
                        if not child.telegram_user_id:
                            logger.warning(
                                f"Не указан Telegram ID для ребёнка {child.display_name}, пропускаем"
                            )
                            continue
                        target_chat_id = child.telegram_user_id

                        # Проверка существования задачи уже делается в TaskService
                        task = await TaskService.create_task_for_child(
                            session=session,
                            child_id=child.id,
                            task_type_id=schedule.task_type_id,
                            scheduled_date=current_date,
                            chat_id=target_chat_id,
                            message_id=0,  # Будет заполнено после отправки сообщения
                        )

                        # Отправка сообщения ребёнку
                        task_type = schedule.task_type
                        message_text = (
                            f"{child.display_name}, твоё задание на сегодня:\n"
                            f"📖 {task_type.name}\n"
                            f"Награда: {task.reward_amount} {task.currency}\n\n"
                            f"Когда выполнишь — нажми кнопку ниже и "
                            f"(если нужно) пришли фото/видео ответом на это сообщение."
                        )

                        try:
                            sent_message = await bot_instance.send_message(
                                chat_id=target_chat_id,
                                text=message_text,
                                reply_markup=get_task_completion_keyboard(),
                            )
                        except Exception as send_error:
                            error_msg = str(send_error).lower()
                            if "can't initiate conversation" in error_msg or "forbidden" in error_msg:
                                logger.error(
                                    f"Не удалось отправить задание для {child.display_name}: "
                                    f"ребёнок не начинал разговор с ботом. "
                                    f"Попросите ребёнка отправить /start боту в личные сообщения."
                                )
                            else:
                                logger.error(
                                    f"Ошибка при отправке задания для {child.display_name}: {send_error}"
                                )
                            continue  # Пропускаем этого ребёнка и переходим к следующему

                        # Обновляем message_id в задаче (chat_id уже задан при создании)
                        task.message_id = sent_message.message_id
                        await session.commit()

                        logger.info(
                            f"Создана задача {task.id} для ребёнка {child.display_name}"
                        )

                    except ValueError as e:
                        # Задача уже существует или другая ошибка
                        logger.debug(f"Пропуск создания задачи: {e}")
                        continue

        except Exception as e:
            logger.error(f"Ошибка при создании ежедневных задач: {e}", exc_info=True)


async def close_expired_tasks():
    """
    Закрытие просроченных задач в конце дня.
    См. SPEC.md раздел 6.1 "Закрытие задач в конце дня"
    
    Запускается каждый день в 23:59 или 00:10.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Закрываем задачи за вчерашний день
            tz = timezone(TIMEZONE)
            yesterday = (datetime.now(tz) - timedelta(days=1)).date()

            count = await TaskService.close_expired_tasks(
                session, yesterday, TaskStatus.FAILED
            )

            logger.info(f"Закрыто {count} просроченных задач за {yesterday}")

        except Exception as e:
            logger.error(f"Ошибка при закрытии просроченных задач: {e}", exc_info=True)


async def send_daily_report():
    """
    Отправка ежедневного отчёта админу.
    См. SPEC.md раздел 6.2 "Ежедневный отчёт админу"
    
    Запускается каждый день утром (например, в 08:00).
    """
    if not bot_instance:
        logger.error("Bot instance не установлен")
        return

    async with AsyncSessionLocal() as session:
        try:
            # Отчёт за вчерашний день
            tz = timezone(TIMEZONE)
            yesterday = (datetime.now(tz) - timedelta(days=1)).date()

            report_text = await ReportService.format_daily_report_text(session, yesterday)

            await bot_instance.send_message(chat_id=ADMIN_TELEGRAM_ID, text=report_text)
            logger.info(f"Отправлен ежедневный отчёт за {yesterday}")

        except Exception as e:
            logger.error(f"Ошибка при отправке ежедневного отчёта: {e}", exc_info=True)


async def send_weekly_report():
    """
    Отправка еженедельного отчёта админу.
    См. SPEC.md раздел 6.3 "Еженедельный отчёт"
    
    Запускается раз в неделю (например, воскресенье в 20:00).
    """
    if not bot_instance:
        logger.error("Bot instance не установлен")
        return

    async with AsyncSessionLocal() as session:
        try:
            tz = timezone(TIMEZONE)
            now = datetime.now(tz)

            # Понедельник = 0, Воскресенье = 6
            # Если сегодня воскресенье, берём понедельник недели назад
            days_since_monday = now.weekday()
            week_start = (now - timedelta(days=days_since_monday + 7)).date()
            week_end = (now - timedelta(days=days_since_monday + 1)).date()

            report_text = await ReportService.format_weekly_report_text(
                session, week_start, week_end
            )

            await bot_instance.send_message(chat_id=ADMIN_TELEGRAM_ID, text=report_text)
            logger.info(
                f"Отправлен еженедельный отчёт за {week_start} - {week_end}"
            )

        except Exception as e:
            logger.error(f"Ошибка при отправке еженедельного отчёта: {e}", exc_info=True)


def setup_scheduler() -> AsyncIOScheduler:
    """
    Настройка и запуск планировщика.
    См. SPEC.md раздел 2.2 "Компоненты" - Scheduler
    
    Возвращает настроенный экземпляр планировщика.
    """
    tz = timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Создание задач по расписанию - каждые 5 минут
    scheduler.add_job(
        create_daily_tasks,
        trigger=IntervalTrigger(minutes=5),
        id="create_daily_tasks",
        name="Создание ежедневных задач",
        replace_existing=True,
    )

    # Закрытие просроченных задач - каждый день в 23:59
    scheduler.add_job(
        close_expired_tasks,
        trigger=CronTrigger(hour=23, minute=59, timezone=tz),
        id="close_expired_tasks",
        name="Закрытие просроченных задач",
        replace_existing=True,
    )

    # Ежедневный отчёт - каждый день в 08:00
    scheduler.add_job(
        send_daily_report,
        trigger=CronTrigger(hour=8, minute=0, timezone=tz),
        id="send_daily_report",
        name="Ежедневный отчёт",
        replace_existing=True,
    )

    # Еженедельный отчёт - каждое воскресенье в 20:00
    scheduler.add_job(
        send_weekly_report,
        trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=tz),
        id="send_weekly_report",
        name="Еженедельный отчёт",
        replace_existing=True,
    )

    logger.info("Планировщик настроен")
    return scheduler

