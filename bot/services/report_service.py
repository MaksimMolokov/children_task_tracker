"""
Сервис для формирования отчётов.
См. SPEC.md раздел 6 "Автоматическое закрытие задач и отчёты"
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, TaskStatus, User, UserRole


class ReportService:
    """Сервис для формирования отчётов"""

    @staticmethod
    async def generate_daily_report(
        session: AsyncSession, report_date: date
    ) -> Dict[int, Dict]:
        """
        Формирование ежедневного отчёта за указанную дату.
        См. SPEC.md раздел 6.2 "Ежедневный отчёт админу"
        
        Возвращает словарь: {child_id: {task_type_id: {status, reward_amount}, total: ...}}
        """
        result = await session.execute(
            select(Task).where(Task.scheduled_date == report_date)
        )
        tasks = result.scalars().all()

        report: Dict[int, Dict] = {}

        for task in tasks:
            child_id = task.child_id
            task_type_id = task.task_type_id

            if child_id not in report:
                report[child_id] = {
                    "tasks": {},
                    "total": Decimal("0.00"),
                    "child_name": task.child.display_name or f"Ребёнок {child_id}",
                }

            reward = task.reward_amount if task.status == TaskStatus.DONE else Decimal("0.00")

            if task_type_id not in report[child_id]["tasks"]:
                report[child_id]["tasks"][task_type_id] = {
                    "task_type_name": task.task_type.name,
                    "status": task.status.value,
                    "reward_amount": reward,
                }
            else:
                # Если несколько задач одного типа (маловероятно, но возможно)
                report[child_id]["tasks"][task_type_id]["reward_amount"] += reward

            report[child_id]["total"] += reward

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
            for task_type_id, task_data in child_data["tasks"].items():
                status_emoji = "✅" if task_data["status"] == "done" else "❌"
                lines.append(
                    f"– {task_data['task_type_name']} — {status_emoji} ({task_data['reward_amount']} ARS)"
                )
            lines.append(f"Итого за день: {child_data['total']} ARS")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    async def generate_weekly_report(
        session: AsyncSession, week_start: date, week_end: date
    ) -> Dict[int, Dict]:
        """
        Формирование еженедельного отчёта за период.
        См. SPEC.md раздел 6.3 "Еженедельный отчёт"
        
        Возвращает словарь: {child_id: {task_type_id: {count, total_reward}, grand_total: ...}}
        """
        result = await session.execute(
            select(Task).where(
                Task.scheduled_date >= week_start,
                Task.scheduled_date <= week_end,
                Task.status == TaskStatus.DONE,
            )
        )
        tasks = result.scalars().all()

        report: Dict[int, Dict] = {}

        for task in tasks:
            child_id = task.child_id
            task_type_id = task.task_type_id

            if child_id not in report:
                report[child_id] = {
                    "tasks": {},
                    "grand_total": Decimal("0.00"),
                    "child_name": task.child.display_name or f"Ребёнок {child_id}",
                }

            if task_type_id not in report[child_id]["tasks"]:
                report[child_id]["tasks"][task_type_id] = {
                    "task_type_name": task.task_type.name,
                    "count": 0,
                    "total_reward": Decimal("0.00"),
                }

            report[child_id]["tasks"][task_type_id]["count"] += 1
            report[child_id]["tasks"][task_type_id]["total_reward"] += task.reward_amount
            report[child_id]["grand_total"] += task.reward_amount

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
            for task_type_id, task_data in child_data["tasks"].items():
                lines.append(
                    f"– {task_data['task_type_name']}: {task_data['count']} шт ({task_data['total_reward']} ARS)"
                )
            lines.append(f"Итого: {child_data['grand_total']} ARS")
            lines.append("")

        return "\n".join(lines)


