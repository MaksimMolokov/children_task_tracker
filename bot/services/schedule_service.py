"""
Сервис для работы с расписанием заданий.
См. SPEC.md раздел 3.5 "Расписание" и раздел 5.1 "Создание задач по расписанию"
"""
from datetime import date, time
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Schedule, TargetScope, User, UserRole


class ScheduleService:
    """Сервис для работы с расписанием"""

    @staticmethod
    async def get_active_schedules_for_time(
        session: AsyncSession, current_time: time, current_date: date
    ) -> List[Schedule]:
        """
        Получение активных расписаний для текущего времени и дня недели.
        См. SPEC.md раздел 5.1, шаг 1:
        - Выбор всех активных schedules, где time_of_day == текущему времени
        - И сегодня входит в days_of_week
        """
        # Получаем день недели (MON, TUE, WED, etc.)
        weekday_name = current_date.strftime("%a").upper()[:3]  # MON, TUE, etc.

        result = await session.execute(
            select(Schedule).where(
                Schedule.is_active == True,
                Schedule.time_of_day == current_time,
            )
        )
        schedules = result.scalars().all()

        # Фильтр по дням недели в Python; при росте числа расписаний можно перенести в SQL
        # (например, проверка вхождения weekday_name в строку days_of_week на стороне БД)
        matching_schedules = []
        for schedule in schedules:
            if weekday_name in schedule.days_of_week:
                matching_schedules.append(schedule)

        return matching_schedules

    @staticmethod
    async def get_target_children_for_schedule(
        session: AsyncSession, schedule: Schedule
    ) -> List[User]:
        """
        Получение списка детей-целей для расписания.
        См. SPEC.md раздел 3.5 - target_scope и target_children_ids
        """
        if schedule.target_scope == TargetScope.ALL_CHILDREN:
            # Все активные дети
            result = await session.execute(
                select(User).where(User.role == UserRole.CHILD, User.is_active == True)
            )
            return list(result.scalars().all())
        elif schedule.target_scope == TargetScope.SPECIFIC_CHILDREN:
            # Конкретные дети из target_children_ids
            if not schedule.target_children_ids:
                return []
            result = await session.execute(
                select(User).where(
                    User.id.in_(schedule.target_children_ids),
                    User.is_active == True,
                )
            )
            return list(result.scalars().all())
        return []



