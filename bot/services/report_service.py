"""
Сервис для формирования отчётов.
См. SPEC.md раздел 6 "Автоматическое закрытие задач и отчёты"
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db.models import Task, TaskMedia, TaskStatus, User, UserRole

logger = logging.getLogger(__name__)


class ReportService:
    """Сервис для формирования отчётов"""

    @staticmethod
    async def generate_daily_report(
        session: AsyncSession, report_date: date
    ) -> Dict[int, Dict]:
        """
        Формирование ежедневного отчёта за указанную дату.
        См. SPEC.md раздел 6.2 "Ежедневный отчёт админу"
        
        Возвращает словарь: {child_id: {tasks: [{task_type_name, status, reward_amount, execution_time, has_media}], total, total_time, child_name}}
        """
        result = await session.execute(
            select(Task)
            .options(joinedload(Task.child), joinedload(Task.task_type))
            .where(Task.scheduled_date == report_date)
        )
        tasks = result.scalars().all()
        
        logger.info(f"generate_daily_report: report_date={report_date}, found {len(tasks)} tasks")

        report: Dict[int, Dict] = {}

        for task in tasks:
            child_id = task.child_id

            if child_id not in report:
                report[child_id] = {
                    "tasks": [],
                    "total": Decimal("0.00"),
                    "total_time": 0,  # Общее время выполнения в минутах
                    "child_name": task.child.display_name or f"Ребёнок {child_id}",
                }

            reward = task.reward_amount if task.status == TaskStatus.DONE else Decimal("0.00")
            execution_time = task.task_type.execution_time or 0
            
            # Проверяем наличие медиа для задания
            media_result = await session.execute(
                select(TaskMedia).where(TaskMedia.task_id == task.id)
            )
            has_media = media_result.scalar_one_or_none() is not None

            # Добавляем информацию о задании
            task_info = {
                "task_type_name": task.task_type.name,
                "status": task.status.value,
                "reward_amount": reward,
                "execution_time": execution_time if task.status == TaskStatus.DONE else 0,
                "has_media": has_media,
            }
            report[child_id]["tasks"].append(task_info)

            if task.status == TaskStatus.DONE:
                report[child_id]["total"] += reward
                report[child_id]["total_time"] += execution_time

        return report

    @staticmethod
    async def format_daily_report_text(
        session: AsyncSession, report_date: date
    ) -> str:
        """
        Форматирование ежедневного отчёта в текстовый формат для отправки.
        См. SPEC.md раздел 6.2, шаг 5 - пример формата текста
        """
        report = await ReportService.generate_daily_report(session, report_date)

        lines = [f"Отчёт за {report_date.strftime('%Y-%m-%d')}", ""]

        for child_id, child_data in report.items():
            lines.append(f"👦 {child_data['child_name']}")
            for task_info in child_data["tasks"]:
                status_emoji = "✅" if task_info["status"] == "done" else "❌"
                media_icon = "📸" if task_info["has_media"] else ""
                time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 and task_info["status"] == "done" else ""
                lines.append(
                    f"– {task_info['task_type_name']} — {status_emoji} "
                    f"{task_info['reward_amount']} ARS{time_text} {media_icon}"
                )
            total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
            lines.append(f"⏱ Общее время выполнения: {total_time_text}")
            lines.append(f"💰 Итого за день: {child_data['total']} ARS")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    async def generate_weekly_report(
        session: AsyncSession, week_start: date, week_end: date
    ) -> Dict[int, Dict]:
        """
        Формирование еженедельного отчёта за период.
        См. SPEC.md раздел 6.3 "Еженедельный отчёт"
        
        Возвращает словарь: {child_id: {tasks_by_date: {date: [tasks]}, grand_total, total_time, child_name}}
        """
        result = await session.execute(
            select(Task)
            .options(joinedload(Task.child), joinedload(Task.task_type))
            .where(
                Task.scheduled_date >= week_start,
                Task.scheduled_date <= week_end,
                Task.status == TaskStatus.DONE,
            )
        )
        tasks = result.scalars().all()

        report: Dict[int, Dict] = {}

        for task in tasks:
            child_id = task.child_id
            task_date = task.scheduled_date

            if child_id not in report:
                report[child_id] = {
                    "tasks_by_date": {},
                    "grand_total": Decimal("0.00"),
                    "total_time": 0,  # Общее время выполнения за период
                    "child_name": task.child.display_name or f"Ребёнок {child_id}",
                }

            if task_date not in report[child_id]["tasks_by_date"]:
                report[child_id]["tasks_by_date"][task_date] = []

            execution_time = task.task_type.execution_time or 0
            
            # Проверяем наличие медиа для задания
            media_result = await session.execute(
                select(TaskMedia).where(TaskMedia.task_id == task.id)
            )
            has_media = media_result.scalar_one_or_none() is not None

            task_info = {
                "task_type_name": task.task_type.name,
                "reward_amount": task.reward_amount,
                "execution_time": execution_time,
                "has_media": has_media,
            }
            report[child_id]["tasks_by_date"][task_date].append(task_info)
            report[child_id]["grand_total"] += task.reward_amount
            report[child_id]["total_time"] += execution_time

        return report

    @staticmethod
    async def format_weekly_report_text(
        session: AsyncSession, week_start: date, week_end: date
    ) -> str:
        """
        Форматирование еженедельного отчёта в текстовый формат.
        См. SPEC.md раздел 6.3, шаг 5 - пример формата текста
        """
        report = await ReportService.generate_weekly_report(session, week_start, week_end)

        lines = [
            f"Еженедельный отчёт ({week_start.strftime('%Y-%m-%d')} — {week_end.strftime('%Y-%m-%d')})",
            "",
        ]

        for child_id, child_data in report.items():
            lines.append(f"👦 {child_data['child_name']}")
            
            # Группируем по датам
            for task_date in sorted(child_data["tasks_by_date"].keys()):
                lines.append(f"📅 {task_date.strftime('%d.%m.%Y')}")
                day_total = Decimal("0.00")
                day_total_time = 0
                
                for task_info in child_data["tasks_by_date"][task_date]:
                    media_icon = "📸" if task_info["has_media"] else ""
                    time_text = f" ({task_info['execution_time']} мин)" if task_info["execution_time"] > 0 else ""
                    lines.append(
                        f"– {task_info['task_type_name']}: "
                        f"{task_info['reward_amount']} ARS{time_text} {media_icon}"
                    )
                    day_total += task_info["reward_amount"]
                    day_total_time += task_info["execution_time"]
                
                day_time_text = f"{day_total_time} минут" if day_total_time > 0 else "0 минут"
                lines.append(f"⏱ Общее время за день: {day_time_text}")
                lines.append(f"💰 Итого за день: {day_total} ARS")
                lines.append("")
            
            total_time_text = f"{child_data['total_time']} минут" if child_data['total_time'] > 0 else "0 минут"
            lines.append(f"⏱ Общее время выполнения за неделю: {total_time_text}")
            lines.append(f"💰 Итого: {child_data['grand_total']} ARS")
            lines.append("")

        return "\n".join(lines)


