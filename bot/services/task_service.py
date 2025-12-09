"""
Сервис для создания и управления задачами.
См. SPEC.md раздел 5.1 "Создание задач по расписанию"
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChildTaskReward, Task, TaskStatus, User


class TaskService:
    """Сервис для работы с задачами"""

    @staticmethod
    async def create_task_for_child(
        session: AsyncSession,
        child_id: int,
        task_type_id: int,
        scheduled_date: date,
        chat_id: int,
        message_id: int,
    ) -> Task:
        """
        Создание задачи для ребёнка.
        См. SPEC.md раздел 5.1, шаг 2:
        - Проверка, нет ли уже задачи на сегодня
        - Получение reward_amount из child_task_rewards (если нет - 0)
        - Создание записи в tasks
        """
        # Проверка существования задачи на этот день
        existing_task = await session.execute(
            select(Task).where(
                Task.child_id == child_id,
                Task.task_type_id == task_type_id,
                Task.scheduled_date == scheduled_date,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.DONE]),
            )
        )
        if existing_task.scalar_one_or_none():
            raise ValueError("Задача на этот день уже существует")

        # Получение ставки из child_task_rewards
        reward_result = await session.execute(
            select(ChildTaskReward).where(
                ChildTaskReward.child_id == child_id,
                ChildTaskReward.task_type_id == task_type_id,
            )
        )
        reward = reward_result.scalar_one_or_none()
        reward_amount = reward.reward_amount if reward else Decimal("0.00")
        currency = reward.currency if reward else "ARS"

        # Создание задачи
        task = Task(
            child_id=child_id,
            task_type_id=task_type_id,
            scheduled_date=scheduled_date,
            status=TaskStatus.PENDING,
            reward_amount=reward_amount,  # Снапшот ставки на момент создания
            currency=currency,
            chat_id=chat_id,
            message_id=message_id,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def get_task_by_message(
        session: AsyncSession, chat_id: int, message_id: int
    ) -> Task | None:
        """
        Получение задачи по chat_id и message_id.
        Используется при обработке callback от кнопки "✅ Выполнил"
        """
        result = await session.execute(
            select(Task).where(Task.chat_id == chat_id, Task.message_id == message_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_task_as_done(
        session: AsyncSession, task_id: int, completed_at: datetime | None = None
    ) -> Task:
        """
        Отметить задачу как выполненную.
        См. SPEC.md раздел 5.2 - обновление статуса на done
        """
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Задача уже имеет статус {task.status}")

        task.status = TaskStatus.DONE
        task.completed_at = completed_at or datetime.utcnow()
        await session.commit()
        await session.refresh(task)
        return task

    @staticmethod
    async def close_expired_tasks(
        session: AsyncSession, target_date: date, status: TaskStatus = TaskStatus.FAILED
    ) -> int:
        """
        Закрытие просроченных задач.
        См. SPEC.md раздел 6.1 "Закрытие задач в конце дня"
        
        Возвращает количество закрытых задач.
        """
        result = await session.execute(
            select(Task).where(
                Task.scheduled_date == target_date, Task.status == TaskStatus.PENDING
            )
        )
        tasks = result.scalars().all()
        count = 0
        for task in tasks:
            task.status = status
            count += 1
        await session.commit()
        return count


