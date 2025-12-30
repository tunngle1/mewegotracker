"""Habit management handlers."""
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.database import async_session
from bot.models import User, Habit, ScheduleType
from bot.keyboards import (
    main_menu_keyboard,
    get_cancel_keyboard,
    get_habit_management_keyboard,
    get_habit_actions_keyboard,
    get_confirmation_keyboard,
    get_schedule_type_keyboard,
    get_weekly_target_keyboard,
)

logger = logging.getLogger(__name__)

# States for adding habit
(
    WAITING_HABIT_NAME,
    WAITING_SCHEDULE_TYPE,
    WAITING_WEEKLY_TARGET,
    WAITING_RENAME,
) = range(100, 104)


# =============================================================================
# MY HABITS - List and Manage
# =============================================================================

async def show_my_habits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of habits with management options."""
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
                "Привет! Нажми /start чтобы начать."
            )
            return
        
        habits = user.habits if user.habits else []
    
    if not habits:
        await update.message.reply_text(
            "📋 У тебя пока нет привычек.\n\n"
            "Нажми «➕ Добавить привычку» чтобы создать первую!",
        )
        return
    
    await update.message.reply_text(
        "📋 <b>Твои привычки:</b>\n\n"
        "🟢 — активна, 🔴 — выключена\n"
        "Нажми на привычку для управления:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_habit_management_keyboard(habits),
    )


async def back_to_habits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to habits list."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(selectinload(User.habits))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        habits = user.habits if user else []
    
    await query.message.edit_text(
        "📋 <b>Твои привычки:</b>\n\n"
        "🟢 — активна, 🔴 — выключена\n"
        "Нажми на привычку для управления:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_habit_management_keyboard(habits),
    )


async def manage_habit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show actions for a specific habit."""
    query = update.callback_query
    await query.answer()
    
    habit_id = int(query.data.split(":")[1])
    
    async with async_session() as session:
        result = await session.execute(
            select(Habit).where(Habit.id == habit_id)
        )
        habit = result.scalar_one_or_none()
        
        if habit is None:
            await query.answer("Привычка не найдена", show_alert=True)
            return
        
        schedule_info = ""
        if habit.schedule_type == ScheduleType.WEEKLY:
            schedule_info = f"\n📆 Частота: {habit.weekly_target} раз(а) в неделю"
        else:
            schedule_info = "\n📅 Частота: ежедневно"
        
        status = "🟢 Активна" if habit.is_active else "🔴 Выключена"
        
        await query.message.edit_text(
            f"<b>{habit.name}</b>\n\n"
            f"Статус: {status}{schedule_info}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_habit_actions_keyboard(habit_id, habit.is_active),
        )


# =============================================================================
# TOGGLE HABIT ON/OFF
# =============================================================================

async def toggle_habit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle habit on/off."""
    query = update.callback_query
    
    parts = query.data.split(":")
    habit_id = int(parts[1])
    action = parts[2]  # on or off
    
    new_status = action == "on"
    
    async with async_session() as session:
        result = await session.execute(
            select(Habit).where(Habit.id == habit_id)
        )
        habit = result.scalar_one_or_none()
        
        if habit is None:
            await query.answer("Привычка не найдена", show_alert=True)
            return
        
        habit.is_active = new_status
        await session.commit()
        
        status_text = "включена 🟢" if new_status else "выключена 🔴"
        await query.answer(f"Привычка {status_text}")
        
        # Update message
        schedule_info = ""
        if habit.schedule_type == ScheduleType.WEEKLY:
            schedule_info = f"\n📆 Частота: {habit.weekly_target} раз(а) в неделю"
        else:
            schedule_info = "\n📅 Частота: ежедневно"
        
        status = "🟢 Активна" if habit.is_active else "🔴 Выключена"
        
        await query.message.edit_text(
            f"<b>{habit.name}</b>\n\n"
            f"Статус: {status}{schedule_info}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_habit_actions_keyboard(habit_id, habit.is_active),
        )


# =============================================================================
# DELETE HABIT
# =============================================================================

async def confirm_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm habit deletion."""
    query = update.callback_query
    await query.answer()
    
    habit_id = int(query.data.split(":")[1])
    
    async with async_session() as session:
        result = await session.execute(
            select(Habit).where(Habit.id == habit_id)
        )
        habit = result.scalar_one_or_none()
        
        if habit is None:
            await query.answer("Привычка не найдена", show_alert=True)
            return
        
        await query.message.edit_text(
            f"⚠️ Ты уверен, что хочешь удалить привычку <b>{habit.name}</b>?\n\n"
            "Вся статистика будет потеряна!",
            parse_mode=ParseMode.HTML,
            reply_markup=get_confirmation_keyboard("delete", habit_id),
        )


async def do_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete habit."""
    query = update.callback_query
    
    habit_id = int(query.data.split(":")[1])
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(Habit).where(Habit.id == habit_id)
        )
        habit = result.scalar_one_or_none()
        
        if habit is None:
            await query.answer("Привычка не найдена", show_alert=True)
            return
        
        await session.delete(habit)
        await session.commit()
        
        await query.answer("Привычка удалена 🗑")
        
        # Show updated list
        result = await session.execute(
            select(User)
            .options(selectinload(User.habits))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        habits = user.habits if user else []
        
        if habits:
            await query.message.edit_text(
                "📋 <b>Твои привычки:</b>\n\n"
                "🟢 — активна, 🔴 — выключена\n"
                "Нажми на привычку для управления:",
                parse_mode=ParseMode.HTML,
                reply_markup=get_habit_management_keyboard(habits),
            )
        else:
            await query.message.edit_text(
                "📋 У тебя больше нет привычек.\n\n"
                "Нажми «➕ Добавить привычку» чтобы создать новую!",
            )


# =============================================================================
# RENAME HABIT
# =============================================================================

async def start_rename_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start renaming habit."""
    query = update.callback_query
    await query.answer()
    
    habit_id = int(query.data.split(":")[1])
    context.user_data["rename_habit_id"] = habit_id
    
    await query.message.edit_text(
        "✏️ Введи новое название привычки (до 50 символов):",
    )
    
    return WAITING_RENAME


async def process_rename_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process new habit name."""
    new_name = update.message.text.strip()
    
    if new_name == "❌ Отмена":
        context.user_data.pop("rename_habit_id", None)
        await update.message.reply_text(
            "Переименование отменено.",
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )
        return ConversationHandler.END
    
    if len(new_name) > 50:
        await update.message.reply_text(
            "❌ Название слишком длинное! Максимум 50 символов.\n"
            "Попробуй ещё раз:"
        )
        return WAITING_RENAME
    
    if len(new_name) < 1:
        await update.message.reply_text("❌ Название не может быть пустым. Попробуй ещё раз:")
        return WAITING_RENAME
    
    habit_id = context.user_data.get("rename_habit_id")
    
    async with async_session() as session:
        result = await session.execute(
            select(Habit).where(Habit.id == habit_id)
        )
        habit = result.scalar_one_or_none()
        
        if habit is None:
            await update.message.reply_text("Привычка не найдена.")
            context.user_data.pop("rename_habit_id", None)
            return ConversationHandler.END
        
        habit.name = new_name
        await session.commit()
    
    context.user_data.pop("rename_habit_id", None)
    await update.message.reply_text(
        f"✅ Привычка переименована в <b>{new_name}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(update.effective_user.username),
    )
    return ConversationHandler.END


# =============================================================================
# ADD HABIT
# =============================================================================

async def start_add_habit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding a new habit."""
    await update.message.reply_text(
        "➕ Введи название новой привычки (до 50 символов):",
        reply_markup=get_cancel_keyboard(),
    )
    return WAITING_HABIT_NAME


async def start_add_habit_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start adding habit from inline button."""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "➕ Введи название новой привычки (до 50 символов):",
    )
    return WAITING_HABIT_NAME


async def process_habit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process new habit name."""
    habit_name = update.message.text.strip()
    
    if habit_name == "❌ Отмена":
        await update.message.reply_text(
            "Добавление отменено.",
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )
        return ConversationHandler.END
    
    if len(habit_name) > 50:
        await update.message.reply_text(
            "❌ Название слишком длинное! Максимум 50 символов.\n"
            "Попробуй ещё раз:"
        )
        return WAITING_HABIT_NAME
    
    if len(habit_name) < 1:
        await update.message.reply_text("❌ Название не может быть пустым. Попробуй ещё раз:")
        return WAITING_HABIT_NAME
    
    context.user_data["new_habit_name"] = habit_name
    
    await update.message.reply_text(
        f"✅ Привычка: <b>{habit_name}</b>\n\n"
        "Выбери частоту:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_schedule_type_keyboard(),
    )
    return WAITING_SCHEDULE_TYPE


async def process_schedule_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process schedule type selection."""
    query = update.callback_query
    await query.answer()
    
    schedule_type = query.data.split(":")[1]
    context.user_data["schedule_type"] = schedule_type
    
    if schedule_type == "weekly":
        await query.message.edit_text(
            "📆 Сколько раз в неделю нужно выполнять?",
            reply_markup=get_weekly_target_keyboard(),
        )
        return WAITING_WEEKLY_TARGET
    else:
        # Create habit immediately for daily
        await create_new_habit(query, context, weekly_target=7)
        return ConversationHandler.END


async def process_weekly_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process weekly target selection."""
    query = update.callback_query
    await query.answer()
    
    target = int(query.data.split(":")[1])
    await create_new_habit(query, context, weekly_target=target)
    return ConversationHandler.END


async def create_new_habit(query, context: ContextTypes.DEFAULT_TYPE, weekly_target: int) -> None:
    """Create new habit in database."""
    habit_name = context.user_data.get("new_habit_name", "Привычка")
    schedule_type = context.user_data.get("schedule_type", "daily")
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        # Get user
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await query.message.edit_text("Ошибка: пользователь не найден")
            return
        
        # Create habit
        habit = Habit(
            user_id=user.id,
            name=habit_name,
            schedule_type=ScheduleType.DAILY if schedule_type == "daily" else ScheduleType.WEEKLY,
            weekly_target=weekly_target,
        )
        session.add(habit)
        await session.commit()
    
    # Clean up user data
    context.user_data.pop("new_habit_name", None)
    context.user_data.pop("schedule_type", None)
    
    schedule_text = "ежедневно" if schedule_type == "daily" else f"{weekly_target} раз(а) в неделю"
    
    await query.message.edit_text(
        f"🎉 Привычка <b>{habit_name}</b> создана!\n"
        f"📅 Частота: {schedule_text}",
        parse_mode=ParseMode.HTML,
    )
    
    # Send message with menu
    await query.message.reply_text(
        "Используй меню для управления.",
        reply_markup=main_menu_keyboard(query.from_user.username),
    )


async def no_habits_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle empty habits list click."""
    await update.callback_query.answer("Нажми «➕ Добавить привычку» чтобы создать первую!")
