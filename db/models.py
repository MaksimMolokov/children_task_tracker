"""
SQLAlchemy модели для всех таблиц проекта.
См. SPEC.md раздел 3 "Сущности и модель данных"
"""
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""

    pass


class UserRole(PyEnum):
    """Роли пользователей"""

    ADMIN = "admin"
    CHILD = "child"


class TaskCategory(PyEnum):
    """Категории заданий"""

    READING = "reading"
    LANGUAGE = "language"
    SPORT = "sport"
    STUDY = "study"
    OTHER = "other"


class SchedulePeriodicity(PyEnum):
    """Периодичность расписания"""

    DAILY = "daily"
    WEEKLY = "weekly"


class TargetScope(PyEnum):
    """Область действия расписания"""

    ALL_CHILDREN = "all_children"
    SPECIFIC_CHILDREN = "specific_children"


class TaskStatus(PyEnum):
    """Статусы задачи"""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    EXPIRED = "expired"


class MediaFileType(PyEnum):
    """Типы медиа файлов"""

    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"


class User(Base):
    """
    Пользователь (админ или ребёнок)
    См. SPEC.md раздел 3.1
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=True)  # nullable для ручного добавления
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=True)  # Имя ребёнка для отчётов
    age: Mapped[int] = mapped_column(nullable=True)  # Возраст ребёнка
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    rewards: Mapped[list["ChildTaskReward"]] = relationship(back_populates="child")
    tasks: Mapped[list["Task"]] = relationship(back_populates="child")


class TaskType(Base):
    """
    Тип задания (шаблон)
    См. SPEC.md раздел 3.3
    """

    __tablename__ = "task_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "Чтение 30 минут", "Duolingo 1 урок"
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[TaskCategory] = mapped_column(Enum(TaskCategory), nullable=False)
    execution_time: Mapped[int] = mapped_column(nullable=True)  # Время выполнения в минутах
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)  # Стоимость выполнения
    requires_media: Mapped[bool] = mapped_column(Boolean, default=False)  # Необходимость прикладывать отчёт
    notify_on_completion: Mapped[bool] = mapped_column(Boolean, default=False)  # Уведомлять родителя при выполнении
    frequency: Mapped[str] = mapped_column(Text, nullable=True)  # Частотность выполнения (daily, weekly, custom)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    rewards: Mapped[list["ChildTaskReward"]] = relationship(back_populates="task_type")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="task_type")
    tasks: Mapped[list["Task"]] = relationship(back_populates="task_type")


class ChildTaskReward(Base):
    """
    Ставки (денежные коэффициенты) для ребёнка
    См. SPEC.md раздел 3.4
    """

    __tablename__ = "child_task_rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"), nullable=False)
    reward_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="ARS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    child: Mapped["User"] = relationship(back_populates="rewards")
    task_type: Mapped["TaskType"] = relationship(back_populates="rewards")


class Schedule(Base):
    """
    Расписание заданий
    См. SPEC.md раздел 3.5
    """

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"), nullable=False)
    periodicity: Mapped[SchedulePeriodicity] = mapped_column(Enum(SchedulePeriodicity), nullable=False)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)  # Локальное время
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)  # "MON,TUE,WED" или "MON,TUE,WED,THU,FRI,SAT,SUN"
    target_scope: Mapped[TargetScope] = mapped_column(Enum(TargetScope), nullable=False)
    target_children_ids: Mapped[list[int]] = mapped_column(
        JSONB, nullable=True
    )  # Массив child_id, если target_scope = SPECIFIC_CHILDREN
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    task_type: Mapped["TaskType"] = relationship(back_populates="schedules")


class Task(Base):
    """
    Инстанс задания (конкретный день/ребёнок)
    См. SPEC.md раздел 3.6
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)  # На какой день задание
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING)
    reward_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # Фиксированная сумма-снапшот из child_task_rewards
    currency: Mapped[str] = mapped_column(String(10), default="ARS")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # ID сообщения с заданием
    prompt_message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # ID сообщения с просьбой отчета
    reminder_message_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # ID напоминания (при ответе текстом/медиа без reply)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # В каком чате отправлено

    # Relationships
    child: Mapped["User"] = relationship(back_populates="tasks")
    task_type: Mapped["TaskType"] = relationship(back_populates="tasks")
    media: Mapped[list["TaskMedia"]] = relationship(back_populates="task")


class TaskMedia(Base):
    """
    Медиа по заданиям
    См. SPEC.md раздел 3.7
    """

    __tablename__ = "task_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    telegram_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[MediaFileType] = mapped_column(Enum(MediaFileType), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    task: Mapped["Task"] = relationship(back_populates="media")


class Feedback(Base):
    """
    Обратная связь от пользователей (команда /feedback).
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

