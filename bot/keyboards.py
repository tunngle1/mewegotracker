"""Keyboard builders for the bot."""
from typing import Sequence, Dict, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from bot.messages import (
    SELF_IDENTIFICATION_OPTIONS, 
    HABITS, 
    ACTIVITY_LEVELS, 
    GOALS, 
    REMINDER_TIMES,
    CHECKIN_BUTTON
)
from bot.config import CHANNEL_LINK, ADMIN_USERNAMES


# =============================================================================
# POPULAR TIMEZONES
# =============================================================================

POPULAR_TIMEZONES = [
    ("Europe/Moscow", "🇷🇺 Москва (UTC+3)"),
    ("Europe/Kiev", "🇺🇦 Киев (UTC+2)"),
    ("Europe/Minsk", "🇧🇾 Минск (UTC+3)"),
    ("Asia/Almaty", "🇰🇿 Алматы (UTC+6)"),
    ("Asia/Yekaterinburg", "🇷🇺 Екатеринбург (UTC+5)"),
]


# =============================================================================
# ONBOARDING KEYBOARDS (existing)
# =============================================================================

def start_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Начать' после приветствия."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 Начать", callback_data="start_journey")]
    ])


def self_identification_keyboard() -> InlineKeyboardMarkup:
    """Кнопки самоопознавания."""
    buttons = []
    for i, option in enumerate(SELF_IDENTIFICATION_OPTIONS):
        buttons.append([InlineKeyboardButton(option, callback_data=f"self_id_{i}")])
    return InlineKeyboardMarkup(buttons)


def habit_choice_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора привычки."""
    buttons = []
    for habit_id, habit_text in HABITS:
        buttons.append([InlineKeyboardButton(habit_text, callback_data=f"habit_{habit_id}")])
    return InlineKeyboardMarkup(buttons)


def check_in_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Я здесь' для отметки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Я здесь", callback_data="check_in")]
    ])


def activity_level_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора уровня активности."""
    buttons = []
    for level in ACTIVITY_LEVELS:
        buttons.append([InlineKeyboardButton(level, callback_data=f"activity_{level}")])
    return InlineKeyboardMarkup(buttons)


def goal_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора цели."""
    buttons = []
    for goal in GOALS:
        buttons.append([InlineKeyboardButton(goal, callback_data=f"goal_{goal}")])
    return InlineKeyboardMarkup(buttons)


def reminder_time_keyboard() -> InlineKeyboardMarkup:
    """Кнопки выбора времени напоминаний."""
    buttons = []
    row = []
    for i, time in enumerate(REMINDER_TIMES):
        row.append(InlineKeyboardButton(time, callback_data=f"reminder_{time}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    # Add custom time button
    buttons.append([InlineKeyboardButton("✍️ Своё время", callback_data="reminder_custom")])
    
    return InlineKeyboardMarkup(buttons)


def channel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка подписки на канал."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👉 Подписаться", url=CHANNEL_LINK)]
    ])


# =============================================================================
# MAIN MENU (UPDATED - expanded menu after onboarding)
# =============================================================================

def is_admin(username: str) -> bool:
    """Check if user is admin."""
    if not username or not ADMIN_USERNAMES:
        return False
    return username.lower() in [a.lower() for a in ADMIN_USERNAMES]


def main_menu_keyboard(username: str = None) -> ReplyKeyboardMarkup:
    """Главное меню после онбординга с расширенным функционалом."""
    buttons = [
        [KeyboardButton("✅ Отметить сегодня"), KeyboardButton("➕ Добавить привычку")],
        [KeyboardButton("📋 Мои привычки"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("⚙️ Настройки")],
    ]
    
    # Add admin button for admins
    if username and is_admin(username):
        buttons.append([KeyboardButton("🔐 Админ-панель")])
    
    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def simple_menu_keyboard() -> ReplyKeyboardMarkup:
    """Простое меню с одной кнопкой (для обратной совместимости)."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(CHECKIN_BUTTON)]],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ Отмена")]],
        resize_keyboard=True,
    )


# =============================================================================
# HABIT TRACKING KEYBOARDS (NEW from old tracker)
# =============================================================================

def get_habits_tracking_keyboard(
    habits: Sequence,
    logs_today: Dict[int, str],
) -> InlineKeyboardMarkup:
    """
    Клавиатура для отметки привычек за сегодня.
    
    Args:
        habits: List of active Habit objects
        logs_today: Dict {habit_id: status} for already marked today
    """
    from bot.models import LogStatus
    
    buttons = []
    
    for habit in habits:
        current_status = logs_today.get(habit.id)
        
        # Format name with current status indicator
        status_icon = ""
        if current_status == LogStatus.DONE.value or current_status == LogStatus.DONE:
            status_icon = "✅ "
        elif current_status == LogStatus.NOT_DONE.value or current_status == LogStatus.NOT_DONE:
            status_icon = "❌ "
        elif current_status == LogStatus.SKIPPED.value or current_status == LogStatus.SKIPPED:
            status_icon = "⏭ "
        
        habit_name = f"{status_icon}{habit.name}"
        
        # Habit name button
        buttons.append([
            InlineKeyboardButton(
                text=habit_name,
                callback_data=f"habit_info:{habit.id}",
            )
        ])
        
        # Status buttons
        buttons.append([
            InlineKeyboardButton(
                text="✅ Выполнено",
                callback_data=f"track:{habit.id}:done",
            ),
            InlineKeyboardButton(
                text="❌ Не сделал",
                callback_data=f"track:{habit.id}:not_done",
            ),
            InlineKeyboardButton(
                text="⏭ Пропуск",
                callback_data=f"track:{habit.id}:skipped",
            ),
        ])
    
    if not habits:
        buttons.append([
            InlineKeyboardButton(
                text="➕ Создать первую привычку",
                callback_data="add_habit_inline",
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def get_habit_management_keyboard(habits: Sequence) -> InlineKeyboardMarkup:
    """
    Клавиатура для управления привычками.
    
    Args:
        habits: List of all user habits
    """
    from bot.models import ScheduleType
    
    buttons = []
    
    for habit in habits:
        status_icon = "🟢" if habit.is_active else "🔴"
        schedule_info = ""
        if habit.schedule_type == ScheduleType.WEEKLY:
            schedule_info = f" ({habit.weekly_target}x/нед)"
        
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {habit.name}{schedule_info}",
                callback_data=f"manage:{habit.id}",
            )
        ])
    
    if not habits:
        buttons.append([
            InlineKeyboardButton(
                text="У вас пока нет привычек",
                callback_data="no_habits",
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def get_habit_actions_keyboard(habit_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """
    Клавиатура действий с конкретной привычкой.
    
    Args:
        habit_id: ID of the habit
        is_active: Is habit currently active
    """
    buttons = []
    
    # Toggle on/off
    if is_active:
        buttons.append([
            InlineKeyboardButton(
                text="🔴 Выключить",
                callback_data=f"toggle:{habit_id}:off",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🟢 Включить",
                callback_data=f"toggle:{habit_id}:on",
            )
        ])
    
    # Rename and delete
    buttons.append([
        InlineKeyboardButton(
            text="✏️ Переименовать",
            callback_data=f"rename:{habit_id}",
        ),
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete:{habit_id}",
        ),
    ])
    
    # Back button
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_habits",
        )
    ])
    
    return InlineKeyboardMarkup(buttons)


def get_confirmation_keyboard(action: str, habit_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="✅ Да",
                callback_data=f"confirm_{action}:{habit_id}",
            ),
            InlineKeyboardButton(
                text="❌ Нет",
                callback_data=f"manage:{habit_id}",
            ),
        ]
    ])


def get_schedule_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа расписания."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="📅 Ежедневно",
            callback_data="schedule:daily",
        )],
        [InlineKeyboardButton(
            text="📆 N раз в неделю",
            callback_data="schedule:weekly",
        )],
    ])


def get_weekly_target_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора количества раз в неделю."""
    buttons = []
    row = []
    for i in range(1, 8):
        row.append(InlineKeyboardButton(
            text=str(i),
            callback_data=f"weekly_target:{i}",
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(buttons)


# =============================================================================
# SETTINGS KEYBOARDS (NEW from old tracker)
# =============================================================================

def get_settings_keyboard(reminders_enabled: bool) -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    buttons = [
        [InlineKeyboardButton(
            text="🕐 Время напоминания",
            callback_data="settings:reminder_time",
        )],
        [InlineKeyboardButton(
            text="🌍 Часовой пояс",
            callback_data="settings:timezone",
        )],
    ]
    
    # Toggle reminders
    if reminders_enabled:
        buttons.append([
            InlineKeyboardButton(
                text="🔕 Выключить напоминания",
                callback_data="settings:reminders_off",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🔔 Включить напоминания",
                callback_data="settings:reminders_on",
            )
        ])
    
    return InlineKeyboardMarkup(buttons)


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора таймзоны."""
    buttons = []
    
    for tz_name, tz_display in POPULAR_TIMEZONES:
        buttons.append([
            InlineKeyboardButton(
                text=tz_display,
                callback_data=f"tz:{tz_name}",
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="⌨️ Ввести вручную",
            callback_data="tz:custom",
        )
    ])
    
    return InlineKeyboardMarkup(buttons)
