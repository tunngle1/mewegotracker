"""Habit tracking handlers - updated with multiple habits support."""
from datetime import datetime, date
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from bot.database import async_session
from bot.models import User, Habit, HabitLog, LogStatus
from bot.messages import get_check_in_message, HABITS, CHECKIN_BUTTON
from bot.keyboards import main_menu_keyboard, get_habits_tracking_keyboard


def get_user_today(timezone: str) -> date:
    """Get current date in user's timezone."""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = ZoneInfo("Europe/Moscow")
    
    return datetime.now(tz).date()


async def get_user(telegram_id: int) -> User:
    """Get user by telegram ID."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def calculate_days_skipped(user: User) -> int:
    """Calculate how many days were skipped since last check-in."""
    if not user.last_check_in:
        return 0
    
    last_check_in = user.last_check_in
    now = datetime.utcnow()
    
    # Calculate difference in days
    days_diff = (now.date() - last_check_in.date()).days
    
    # If checked in today already, no skip
    if days_diff == 0:
        return 0
    
    return days_diff


# =============================================================================
# SHOW TODAY'S HABITS FOR TRACKING
# =============================================================================

async def show_today_habits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of active habits for today's tracking."""
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
                "Привет! Нажми /start чтобы начать.",
                reply_markup=main_menu_keyboard(update.effective_user.username)
            )
            return
        
        if not user.onboarding_completed:
            await update.message.reply_text(
                "Давай сначала завершим знакомство. Нажми /start"
            )
            return
        
        # Get active habits
        active_habits = [h for h in user.habits if h.is_active] if user.habits else []
        
        if not active_habits:
            await update.message.reply_text(
                "😕 У тебя нет активных привычек.\n\n"
                "Нажми «➕ Добавить привычку» для создания.",
                reply_markup=main_menu_keyboard(update.effective_user.username)
            )
            return
        
        # Get today's date in user's timezone
        today = get_user_today(user.timezone)
        
        # Collect today's statuses
        logs_today = {}
        for habit in active_habits:
            for log in habit.logs:
                if log.log_date == today:
                    logs_today[habit.id] = log.status
                    break
        
        await update.message.reply_text(
            f"📅 <b>Отметки за {today.strftime('%d.%m.%Y')}</b>\n\n"
            "Нажми кнопку чтобы отметить статус:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_habits_tracking_keyboard(active_habits, logs_today),
        )


# =============================================================================
# TRACK HABIT (done / not_done / skipped)
# =============================================================================

async def track_habit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark habit status for today."""
    query = update.callback_query
    
    parts = query.data.split(":")
    habit_id = int(parts[1])
    status_str = parts[2]
    
    # Convert string to status enum
    status_map = {
        "done": LogStatus.DONE,
        "not_done": LogStatus.NOT_DONE,
        "skipped": LogStatus.SKIPPED,
    }
    status = status_map.get(status_str)
    
    if status is None:
        await query.answer("Неизвестный статус", show_alert=True)
        return
    
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.habits).selectinload(Habit.logs)
            )
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            await query.answer("Пользователь не найден", show_alert=True)
            return
        
        # Get today's date in user's timezone
        today = get_user_today(user.timezone)
        
        # Find or create log for this habit and date
        result = await session.execute(
            select(HabitLog).where(
                and_(HabitLog.habit_id == habit_id, HabitLog.log_date == today)
            )
        )
        log = result.scalar_one_or_none()
        
        if log is None:
            # Calculate days skipped for day cycle phrases
            days_skipped = await calculate_days_skipped(user)
            new_day_cycle = ((user.day_cycle) % 30) + 1
            
            log = HabitLog(
                user_id=user.id,
                habit_id=habit_id,
                log_date=today,
                status=status,
                day_cycle=new_day_cycle,
            )
            session.add(log)
            
            # Update user's day cycle and last check-in only for DONE status
            if status == LogStatus.DONE:
                user.day_cycle = new_day_cycle
                user.last_check_in = datetime.utcnow()
        else:
            log.status = status
        
        await session.commit()
        
        # Refresh habits for keyboard update
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.habits).selectinload(Habit.logs)
            )
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        active_habits = [h for h in user.habits if h.is_active] if user.habits else []
        
        # Collect updated statuses
        logs_today = {}
        for habit in active_habits:
            for habit_log in habit.logs:
                if habit_log.log_date == today:
                    logs_today[habit.id] = habit_log.status
                    break
        
        # Update message with new keyboard
        try:
            await query.message.edit_reply_markup(
                reply_markup=get_habits_tracking_keyboard(active_habits, logs_today),
            )
        except Exception:
            # Keyboard unchanged (same button clicked twice)
            pass
        
        # Show popup notification
        status_text = {
            LogStatus.DONE: "✅ Выполнено!",
            LogStatus.NOT_DONE: "❌ Не сделал",
            LogStatus.SKIPPED: "⏭ Пропущено",
        }
        await query.answer(status_text.get(status, "Сохранено"))
        
        # Send motivational message for DONE status
        if status == LogStatus.DONE:
            # Get the habit name for the message
            habit_obj = next((h for h in active_habits if h.id == habit_id), None)
            habit_name = habit_obj.name if habit_obj else "привычка"
            
            # Calculate days skipped for appropriate message
            days_skipped = await calculate_days_skipped(user)
            
            # Get motivational message
            message = get_check_in_message(
                day_cycle=user.day_cycle,
                days_skipped=days_skipped,
                user_name=user.name
            )
            
            # Send full message
            await query.message.reply_text(
                f"🎯 <b>{habit_name}</b>\n\n{message}",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(query.from_user.username)
            )
        
        # Send message for NOT_DONE or SKIPPED
        elif status == LogStatus.NOT_DONE:
            await query.message.reply_text(
                f"Ничего страшного! Завтра новый день 💪",
                reply_markup=main_menu_keyboard(query.from_user.username)
            )
        elif status == LogStatus.SKIPPED:
            await query.message.reply_text(
                f"Пропуск засчитан. Иногда нужна пауза 🤍",
                reply_markup=main_menu_keyboard(query.from_user.username)
            )


async def habit_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show hint when clicking on habit name."""
    await update.callback_query.answer(
        "💡 Используй кнопки ниже для отметки статуса",
        show_alert=False,
    )


# =============================================================================
# LEGACY CHECK-IN (single button "Я здесь" for backward compatibility)
# =============================================================================

async def handle_check_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle legacy check-in button press (for users without habits yet)."""
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.habits))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text(
                "Привет! Нажми /start чтобы начать.",
                reply_markup=main_menu_keyboard(update.effective_user.username)
            )
            return
        
        if not user.onboarding_completed:
            await update.message.reply_text(
                "Давай сначала завершим знакомство. Нажми /start"
            )
            return
        
        # If user has habits, redirect to proper tracking
        if user.habits and len(user.habits) > 0:
            await show_today_habits(update, context)
            return
        
        # Legacy behavior for users without separate habits
        days_skipped = await calculate_days_skipped(user)
        
        # Check if already checked in today
        if user.last_check_in:
            last_date = user.last_check_in.date()
            today = datetime.utcnow().date()
            if last_date == today:
                await update.message.reply_text(
                    f"Ты уже отметился сегодня, {user.name or 'друг'}! 🤍\n"
                    "Увидимся завтра!",
                    reply_markup=main_menu_keyboard(update.effective_user.username)
                )
                return
        
        # Update day cycle
        new_day_cycle = ((user.day_cycle) % 30) + 1
        
        user.day_cycle = new_day_cycle
        user.last_check_in = datetime.utcnow()
        
        # Create legacy habit log
        habit_name = user.custom_habit if user.current_habit == "custom" else user.current_habit
        log = HabitLog(
            user_id=user.id,
            habit_name=habit_name,
            day_cycle=new_day_cycle,
            status=LogStatus.DONE,
            log_date=datetime.utcnow().date(),
        )
        session.add(log)
        await session.commit()
        
        # Get appropriate message
        message = get_check_in_message(
            day_cycle=new_day_cycle,
            days_skipped=days_skipped,
            user_name=user.name
        )
        
        await update.message.reply_text(
            message,
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )


# =============================================================================
# TEXT MESSAGE HANDLER
# =============================================================================

async def check_in_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - route to appropriate handler."""
    text = update.message.text.strip()
    
    if text == CHECKIN_BUTTON or text == "✅ Я здесь":
        await handle_check_in(update, context)
    elif text == "✅ Отметить сегодня":
        await show_today_habits(update, context)
    else:
        # Unknown message - show current status
        user = await get_user(update.effective_user.id)
        if user and user.onboarding_completed:
            habit_display = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, user.current_habit)
            await update.message.reply_text(
                f"Привет, {user.name or 'друг'}! 🤍\n\n"
                f"Твоя привычка: {habit_display}\n"
                f"День цикла: {user.day_cycle}/30\n\n"
                "Используй меню внизу для управления.",
                reply_markup=main_menu_keyboard(update.effective_user.username)
            )
        else:
            await update.message.reply_text(
                "Привет! Нажми /start чтобы начать."
            )
