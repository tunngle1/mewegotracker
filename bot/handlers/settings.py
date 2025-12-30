"""Settings handlers."""
import logging
import re
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.keyboards import (
    main_menu_keyboard,
    get_cancel_keyboard,
    get_settings_keyboard,
    get_timezone_keyboard,
    reminder_time_keyboard,
)

logger = logging.getLogger(__name__)

# States for settings
(
    WAITING_SETTINGS_REMINDER_TIME,
    WAITING_CUSTOM_TIMEZONE,
) = range(200, 202)


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user settings."""
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            await update.message.reply_text(
                "Привет! Нажми /start чтобы начать."
            )
            return
        
        reminder_status = "выключены 🔕"
        if user.reminders_enabled and user.reminder_time:
            reminder_status = f"включены 🔔 в {user.reminder_time}"
        elif user.reminders_enabled:
            reminder_status = "включены 🔔 (время не задано)"
        
        await update.message.reply_text(
            "⚙️ <b>Настройки</b>\n\n"
            f"🌍 Часовой пояс: <b>{user.timezone}</b>\n"
            f"🔔 Напоминания: {reminder_status}\n",
            parse_mode=ParseMode.HTML,
            reply_markup=get_settings_keyboard(user.reminders_enabled),
        )


# =============================================================================
# REMINDER TIME
# =============================================================================

async def ask_reminder_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for new reminder time."""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🕐 Выбери время напоминания:",
        reply_markup=reminder_time_keyboard(),
    )
    return WAITING_SETTINGS_REMINDER_TIME


async def process_reminder_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process reminder time from callback."""
    query = update.callback_query
    await query.answer()
    
    time_value = query.data.replace("reminder_", "")
    
    if time_value == "custom":
        await query.message.edit_text(
            "🕐 Введи время напоминания в формате <b>ЧЧ:ММ</b>\n"
            "(например, 09:00 или 21:30):",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_SETTINGS_REMINDER_TIME
    
    # Save time
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.reminder_time = time_value
            user.reminders_enabled = True
            await session.commit()
    
    await query.message.edit_text(
        f"✅ Время напоминания установлено: <b>{time_value}</b>",
        parse_mode=ParseMode.HTML,
    )
    
    await query.message.reply_text(
        "Настройки обновлены.",
        reply_markup=main_menu_keyboard(query.from_user.username),
    )
    
    return ConversationHandler.END


async def process_reminder_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process custom reminder time from message."""
    if update.message.text == "❌ Отмена":
        await update.message.reply_text(
            "Изменение отменено.",
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )
        return ConversationHandler.END
    
    time_text = update.message.text.strip()
    
    # Validate format HH:MM
    pattern = r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$"
    match = re.match(pattern, time_text)
    
    if not match:
        await update.message.reply_text(
            "❌ Неверный формат! Введи время в формате <b>ЧЧ:ММ</b>\n"
            "Например: 09:00, 21:30, 08:45",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_SETTINGS_REMINDER_TIME
    
    # Normalize to HH:MM
    hours, minutes = int(match.group(1)), int(match.group(2))
    time_value = f"{hours:02d}:{minutes:02d}"
    
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.reminder_time = time_value
            user.reminders_enabled = True
            await session.commit()
    
    await update.message.reply_text(
        f"✅ Время напоминания установлено: <b>{time_value}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(update.effective_user.username),
    )
    
    return ConversationHandler.END


# =============================================================================
# TIMEZONE
# =============================================================================

async def show_timezone_options_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show timezone selection."""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🌍 Выбери часовой пояс:",
        reply_markup=get_timezone_keyboard(),
    )
    return WAITING_CUSTOM_TIMEZONE


async def process_timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process timezone selection."""
    query = update.callback_query
    await query.answer()
    
    timezone = query.data.split(":", 1)[1]
    
    if timezone == "custom":
        # Manual input
        await query.message.edit_text(
            "⌨️ Введи название часового пояса в формате IANA\n"
            "(например: Europe/London, Asia/Tokyo, America/New_York):\n\n"
            "Список зон: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        )
        return WAITING_CUSTOM_TIMEZONE
    
    # Validate timezone
    try:
        ZoneInfo(timezone)
    except Exception:
        await query.answer("Неизвестный часовой пояс", show_alert=True)
        return WAITING_CUSTOM_TIMEZONE
    
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.timezone = timezone
            await session.commit()
    
    await query.message.edit_text(
        f"✅ Часовой пояс установлен: <b>{timezone}</b>",
        parse_mode=ParseMode.HTML,
    )
    
    await query.message.reply_text(
        "Настройки обновлены.",
        reply_markup=main_menu_keyboard(query.from_user.username),
    )
    
    return ConversationHandler.END


async def process_custom_timezone_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process manual timezone input."""
    if update.message.text == "❌ Отмена":
        await update.message.reply_text(
            "Изменение отменено.",
            reply_markup=main_menu_keyboard(update.effective_user.username)
        )
        return ConversationHandler.END
    
    timezone = update.message.text.strip()
    
    # Validate timezone
    try:
        ZoneInfo(timezone)
    except Exception:
        await update.message.reply_text(
            f"❌ Часовой пояс <b>{timezone}</b> не найден.\n"
            "Проверь правильность написания.\n\n"
            "Примеры: Europe/London, Asia/Tokyo, America/New_York",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_CUSTOM_TIMEZONE
    
    telegram_id = update.effective_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.timezone = timezone
            await session.commit()
    
    await update.message.reply_text(
        f"✅ Часовой пояс установлен: <b>{timezone}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(update.effective_user.username),
    )
    
    return ConversationHandler.END


# =============================================================================
# TOGGLE REMINDERS
# =============================================================================

async def enable_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable reminders."""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.reminders_enabled = True
            await session.commit()
            
            if user.reminder_time:
                await query.message.edit_text(
                    f"🔔 Напоминания включены!\n"
                    f"Время: {user.reminder_time}",
                    reply_markup=get_settings_keyboard(True),
                )
            else:
                await query.message.edit_text(
                    "🔔 Напоминания включены!\n"
                    "⚠️ Не забудь установить время напоминания.",
                    reply_markup=get_settings_keyboard(True),
                )
    
    await query.answer("Напоминания включены 🔔")


async def disable_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable reminders."""
    query = update.callback_query
    telegram_id = query.from_user.id
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.reminders_enabled = False
            await session.commit()
    
    await query.message.edit_text(
        "🔕 Напоминания выключены.",
        reply_markup=get_settings_keyboard(False),
    )
    await query.answer("Напоминания выключены 🔕")
