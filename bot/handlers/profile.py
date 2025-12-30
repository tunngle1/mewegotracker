"""Profile management handlers."""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.messages import HABITS
from bot.keyboards import main_menu_keyboard


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile."""
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.onboarding_completed:
            await update.message.reply_text(
                "Сначала пройди онбординг. Нажми /start"
            )
            return
        
        habit_display = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, user.current_habit)
        
        # Count total check-ins
        total_checkins = len(user.habit_logs) if user.habit_logs else 0
        
        profile_text = (
            f"👤 <b>Профиль</b>\n\n"
            f"<b>Имя:</b> {user.name or 'Не указано'}\n"
            f"<b>Возраст:</b> {user.age or 'Не указан'}\n"
            f"<b>Город:</b> {user.city or 'Не указан'}\n"
            f"<b>Активность:</b> {user.activity_level or 'Не указана'}\n"
            f"<b>Цель:</b> {user.goal or 'Не указана'}\n"
            f"<b>Напоминания:</b> {user.reminder_time or 'Не установлены'} (МСК)\n\n"
            f"🎯 <b>Привычка:</b> {habit_display}\n"
            f"📊 <b>День цикла:</b> {user.day_cycle}/30\n"
            f"✅ <b>Всего отметок:</b> {total_checkins}"
        )
        
        await update.message.reply_text(
            profile_text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user stats."""
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.onboarding_completed:
            await update.message.reply_text(
                "Сначала пройди онбординг. Нажми /start"
            )
            return
        
        total_checkins = len(user.habit_logs) if user.habit_logs else 0
        
        stats_text = (
            f"📊 <b>Статистика</b>\n\n"
            f"✅ Всего отметок: {total_checkins}\n"
            f"🔄 День цикла: {user.day_cycle}/30\n"
        )
        
        await update.message.reply_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard()
        )
