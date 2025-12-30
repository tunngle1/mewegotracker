"""Statistics handlers."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import async_session
from bot.models import User, Habit, HabitLog, ScheduleType
from bot.services.streak import get_habit_stats
from bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


def get_user_today(timezone: str):
    """Get current date in user's timezone."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    
    return datetime.now(tz).date()


async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics for all habits."""
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.habits).selectinload(Habit.logs)
            )
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text(
                "Привет! Нажми /start чтобы начать."
            )
            return
        
        habits = user.habits if user.habits else []
        
        if not habits:
            await update.message.reply_text(
                "📊 <b>Статистика</b>\n\n"
                "У тебя пока нет привычек.\n"
                "Создай первую, чтобы получить статистику!",
                parse_mode=ParseMode.HTML,
            )
            return
        
        today = get_user_today(user.timezone)
        
        stats_text = "📊 <b>Статистика привычек</b>\n\n"
        
        for habit in habits:
            # Get logs for this habit
            logs = habit.logs if habit.logs else []
            
            # Calculate statistics
            stats = get_habit_stats(
                logs=logs,
                schedule_type=habit.schedule_type,
                weekly_target=habit.weekly_target,
                today=today,
            )
            
            # Format text
            status_icon = "🟢" if habit.is_active else "🔴"
            schedule_emoji = "📅" if habit.schedule_type == ScheduleType.DAILY else "📆"
            
            stats_text += f"{status_icon} <b>{habit.name}</b>\n"
            stats_text += f"   {schedule_emoji} "
            
            if habit.schedule_type == ScheduleType.DAILY:
                stats_text += "Ежедневно\n"
            else:
                stats_text += f"{habit.weekly_target}x в неделю\n"
            
            stats_text += f"   🔥 Текущая серия: <b>{stats.current_streak}</b>\n"
            stats_text += f"   🏆 Лучшая серия: <b>{stats.best_streak}</b>\n"
            stats_text += f"   ✅ За 7 дней: {stats.done_7_days}\n"
            stats_text += f"   ✅ За 30 дней: {stats.done_30_days}\n"
            stats_text += f"   📈 Всего выполнено: {stats.total_done}\n\n"
        
        # Add 30-day cycle info
        stats_text += f"━━━━━━━━━━━━━━━━━━━━\n"
        stats_text += f"📆 День цикла: <b>{user.day_cycle}/30</b>\n"
        
        await update.message.reply_text(
            stats_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )
