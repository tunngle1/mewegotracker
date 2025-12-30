"""Main entry point for the MeWeGo bot."""
import logging
import asyncio

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from bot.config import BOT_TOKEN
from bot.database import init_db

# Onboarding handlers
from bot.handlers.onboarding import (
    start_command,
    start_journey_callback,
    self_identification_callback,
    habit_choice_callback,
    custom_habit_message,
    first_checkin_callback,
    name_message,
    age_message,
    city_message,
    activity_callback,
    goal_callback,
    reminder_time_callback,
    custom_reminder_message,
    cancel_command,
    WAITING_START,
    WAITING_SELF_ID,
    WAITING_HABIT,
    WAITING_CUSTOM_HABIT,
    WAITING_FIRST_CHECKIN,
    WAITING_NAME,
    WAITING_AGE,
    WAITING_CITY,
    WAITING_ACTIVITY,
    WAITING_GOAL,
    WAITING_REMINDER_TIME,
    WAITING_CUSTOM_REMINDER,
)

# Tracking handlers
from bot.handlers.tracking import (
    check_in_text_handler,
    show_today_habits,
    track_habit_callback,
    habit_info_callback,
)

# Profile handlers
from bot.handlers.profile import profile_command, stats_command

# Stats handlers
from bot.handlers.stats import show_statistics

# Habit management handlers
from bot.handlers.habits import (
    show_my_habits,
    back_to_habits_callback,
    manage_habit_callback,
    toggle_habit_callback,
    confirm_delete_callback,
    do_delete_callback,
    start_add_habit,
    start_add_habit_inline,
    process_habit_name,
    process_schedule_type,
    process_weekly_target,
    start_rename_callback,
    process_rename_message,
    no_habits_callback,
    WAITING_HABIT_NAME,
    WAITING_SCHEDULE_TYPE,
    WAITING_WEEKLY_TARGET,
    WAITING_RENAME,
)

# Settings handlers
from bot.handlers.settings import (
    show_settings,
    ask_reminder_time_callback,
    process_reminder_time_callback,
    process_reminder_time_message,
    show_timezone_options_callback,
    process_timezone_callback,
    process_custom_timezone_message,
    enable_reminders_callback,
    disable_reminders_callback,
    WAITING_SETTINGS_REMINDER_TIME,
    WAITING_CUSTOM_TIMEZONE,
)

# Admin handlers
from bot.handlers.admin import (
    admin_stats_command, users_list_command, export_command, 
    export_habits_command, admin_callback_handler
)

# Scheduler
from bot.scheduler import setup_scheduler

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the bot."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ==========================================================================
    # ONBOARDING CONVERSATION HANDLER
    # ==========================================================================
    onboarding_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            WAITING_START: [
                CallbackQueryHandler(start_journey_callback, pattern="^start_journey$")
            ],
            WAITING_SELF_ID: [
                CallbackQueryHandler(self_identification_callback, pattern="^self_id_")
            ],
            WAITING_HABIT: [
                CallbackQueryHandler(habit_choice_callback, pattern="^habit_")
            ],
            WAITING_CUSTOM_HABIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_habit_message)
            ],
            WAITING_FIRST_CHECKIN: [
                CallbackQueryHandler(first_checkin_callback, pattern="^check_in$")
            ],
            WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_message)
            ],
            WAITING_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, age_message)
            ],
            WAITING_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, city_message)
            ],
            WAITING_ACTIVITY: [
                CallbackQueryHandler(activity_callback, pattern="^activity_")
            ],
            WAITING_GOAL: [
                CallbackQueryHandler(goal_callback, pattern="^goal_")
            ],
            WAITING_REMINDER_TIME: [
                CallbackQueryHandler(reminder_time_callback, pattern="^reminder_")
            ],
            WAITING_CUSTOM_REMINDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_reminder_message)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True
    )
    
    # ==========================================================================
    # ADD HABIT CONVERSATION HANDLER
    # ==========================================================================
    add_habit_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Добавить привычку$"), start_add_habit),
            CallbackQueryHandler(start_add_habit_inline, pattern="^add_habit_inline$"),
        ],
        states={
            WAITING_HABIT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_habit_name)
            ],
            WAITING_SCHEDULE_TYPE: [
                CallbackQueryHandler(process_schedule_type, pattern="^schedule:")
            ],
            WAITING_WEEKLY_TARGET: [
                CallbackQueryHandler(process_weekly_target, pattern="^weekly_target:")
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_command),
        ],
        allow_reentry=True
    )
    
    # ==========================================================================
    # RENAME HABIT CONVERSATION HANDLER
    # ==========================================================================
    rename_habit_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_rename_callback, pattern="^rename:"),
        ],
        states={
            WAITING_RENAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_rename_message)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_command),
        ],
        allow_reentry=True
    )
    
    # ==========================================================================
    # SETTINGS CONVERSATION HANDLER
    # ==========================================================================
    settings_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_reminder_time_callback, pattern="^settings:reminder_time$"),
            CallbackQueryHandler(show_timezone_options_callback, pattern="^settings:timezone$"),
        ],
        states={
            WAITING_SETTINGS_REMINDER_TIME: [
                CallbackQueryHandler(process_reminder_time_callback, pattern="^reminder_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_reminder_time_message),
            ],
            WAITING_CUSTOM_TIMEZONE: [
                CallbackQueryHandler(process_timezone_callback, pattern="^tz:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_custom_timezone_message),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_command),
        ],
        allow_reentry=True
    )
    
    # ==========================================================================
    # REGISTER HANDLERS (ORDER MATTERS!)
    # ==========================================================================
    
    # Conversation handlers first
    application.add_handler(onboarding_handler)
    application.add_handler(add_habit_handler)
    application.add_handler(rename_habit_handler)
    application.add_handler(settings_handler)
    
    # Command handlers
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admin", admin_stats_command))
    application.add_handler(CommandHandler("users", users_list_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("export_habits", export_habits_command))
    
    # Menu button handlers (text messages)
    application.add_handler(MessageHandler(
        filters.Regex("^✅ Отметить сегодня$"),
        show_today_habits
    ))
    application.add_handler(MessageHandler(
        filters.Regex("^📋 Мои привычки$"),
        show_my_habits
    ))
    application.add_handler(MessageHandler(
        filters.Regex("^📊 Статистика$"),
        show_statistics
    ))
    application.add_handler(MessageHandler(
        filters.Regex("^⚙️ Настройки$"),
        show_settings
    ))
    application.add_handler(MessageHandler(
        filters.Regex("^🔐 Админ-панель$"),
        admin_stats_command
    ))
    
    # Callback query handlers for tracking
    application.add_handler(CallbackQueryHandler(
        track_habit_callback,
        pattern="^track:"
    ))
    application.add_handler(CallbackQueryHandler(
        habit_info_callback,
        pattern="^habit_info:"
    ))
    
    # Callback query handlers for habit management
    application.add_handler(CallbackQueryHandler(
        back_to_habits_callback,
        pattern="^back_to_habits$"
    ))
    application.add_handler(CallbackQueryHandler(
        manage_habit_callback,
        pattern="^manage:"
    ))
    application.add_handler(CallbackQueryHandler(
        toggle_habit_callback,
        pattern="^toggle:"
    ))
    application.add_handler(CallbackQueryHandler(
        confirm_delete_callback,
        pattern="^delete:"
    ))
    application.add_handler(CallbackQueryHandler(
        do_delete_callback,
        pattern="^confirm_delete:"
    ))
    application.add_handler(CallbackQueryHandler(
        no_habits_callback,
        pattern="^no_habits$"
    ))
    
    # Callback query handlers for settings
    application.add_handler(CallbackQueryHandler(
        enable_reminders_callback,
        pattern="^settings:reminders_on$"
    ))
    application.add_handler(CallbackQueryHandler(
        disable_reminders_callback,
        pattern="^settings:reminders_off$"
    ))
    
    # Callback query handlers for admin panel
    application.add_handler(CallbackQueryHandler(
        admin_callback_handler,
        pattern="^admin:"
    ))
    
    # Fallback text message handler (must be last)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        check_in_text_handler
    ))
    
    # Setup scheduler for reminders
    setup_scheduler(application)
    
    # Initialize database on startup
    async def post_init(application: Application) -> None:
        await init_db()
        logger.info("Database initialized")
    
    application.post_init = post_init
    
    # Start the bot
    logger.info("Starting MeWeGo bot...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
