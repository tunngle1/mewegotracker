"""Database models for MeWeGo bot."""
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime, 
    ForeignKey, Text, Enum, Date, Time
)
from sqlalchemy.orm import relationship

from bot.database import Base


# =============================================================================
# ENUMS
# =============================================================================

class ScheduleType(str, enum.Enum):
    """Type of habit schedule."""
    DAILY = "daily"
    WEEKLY = "weekly"


class LogStatus(str, enum.Enum):
    """Status of habit completion for a day."""
    DONE = "done"
    NOT_DONE = "not_done"
    SKIPPED = "skipped"


# =============================================================================
# USER MODEL
# =============================================================================

class User(Base):
    """User model for storing user data and preferences."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Profile data (введённые пользователем)
    name = Column(String(255), nullable=True)  # Как тебя зовут?
    age = Column(Integer, nullable=True)  # Сколько тебе лет?
    city = Column(String(255), nullable=True)  # Из какого ты города?
    activity_level = Column(String(255), nullable=True)  # Какая у тебя активность?
    goal = Column(String(255), nullable=True)  # Какая твоя цель?
    reminder_time = Column(String(10), nullable=True)  # Время напоминаний (HH:MM)
    
    # Timezone and reminders (NEW from old tracker)
    timezone = Column(String(50), default="Europe/Moscow")
    reminders_enabled = Column(Boolean, default=True)
    
    # Habit tracking (for onboarding compatibility)
    current_habit = Column(String(255), nullable=True)  # Текущая выбранная привычка из онбординга
    custom_habit = Column(Text, nullable=True)  # Своя привычка (если выбрал "Своё")
    day_cycle = Column(Integer, default=1)  # Номер дня в цикле (1-30)
    
    # Onboarding state
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String(50), default="start")  # Текущий шаг онбординга
    self_identification = Column(String(255), nullable=True)  # Ответ на самоопознавание
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check_in = Column(DateTime, nullable=True)  # Последняя отметка
    
    # Relationships
    habits = relationship("Habit", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    habit_logs = relationship("HabitLog", back_populates="user", lazy="selectin")


# =============================================================================
# HABIT MODEL (NEW - from old tracker)
# =============================================================================

class Habit(Base):
    """Habit model for multiple habits per user."""
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(50), nullable=False)
    schedule_type = Column(Enum(ScheduleType), default=ScheduleType.DAILY)
    weekly_target = Column(Integer, default=7)  # For weekly: how many times per week
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan", lazy="selectin")
    
    def __repr__(self) -> str:
        return f"<Habit(id={self.id}, name={self.name}, type={self.schedule_type})>"


# =============================================================================
# HABIT LOG MODEL (UPDATED - combined old + new)
# =============================================================================

class HabitLog(Base):
    """Log of habit check-ins."""
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Link to specific habit (NEW - for multiple habits)
    habit_id = Column(Integer, ForeignKey("habits.id", ondelete="CASCADE"), nullable=True)
    
    # Habit info (kept for backward compatibility with onboarding)
    habit_name = Column(String(255), nullable=True)  # Name of habit (legacy field)
    
    # Date and status (NEW from old tracker)
    log_date = Column(Date, nullable=True)  # Date in user's timezone
    status = Column(Enum(LogStatus), default=LogStatus.DONE)
    
    # Day cycle (kept for 30-day phrases)
    day_cycle = Column(Integer, nullable=True)  # Day number in cycle
    
    # Timestamps
    completed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="habit_logs")
    habit = relationship("Habit", back_populates="logs")
    
    def __repr__(self) -> str:
        return f"<HabitLog(habit_id={self.habit_id}, date={self.log_date}, status={self.status})>"


# =============================================================================
# ADMIN MODEL (for dynamic admins)
# =============================================================================

class Admin(Base):
    """Model for dynamically added admins."""
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True)  # Telegram user_id
    added_by = Column(BigInteger)  # Who added this admin
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Admin(user_id={self.user_id}, added_by={self.added_by})>"
