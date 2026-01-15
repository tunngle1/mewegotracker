"""Scheduler for reminders and delayed messages."""
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import Application
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.messages import REMINDER_MESSAGE, REMINDER_WITH_HABIT, HABITS
from bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

# Moscow timezone (UTC+3)
MSK = ZoneInfo("Europe/Moscow")

# Messages for missed days
MISSED_DAY_MESSAGES = [
    "💭 Сегодня без отметки, но это не страшно. Завтра — новый день 🤍",
    "🌙 День без отметки. Не ругай себя, просто вернись завтра.",
    "⏰ Пропуск случается. Главное — не бросать совсем. До завтра!",
]

MISSED_MULTIPLE_DAYS = "🌿 Ты не отмечался уже {days} дн. Ничего страшного — возвращайся, когда будешь готов 🤍"


async def send_reminders(context) -> None:
    """Check users and send reminders at their scheduled time."""
    now = datetime.now(MSK)
    current_time = now.strftime("%H:%M")
    current_hour_minute = now.strftime("%H:%M")
    
    logger.info(f"Checking reminders at {current_time} MSK")
    
    async with async_session() as session:
        # Find users who need reminders at this time
        result = await session.execute(
            select(User).where(
                User.onboarding_completed == True,
                User.reminder_time == current_hour_minute
            )
        )
        users = result.scalars().all()
        
        for user in users:
            try:
                # Check if already checked in today
                if user.last_check_in:
                    last_date = user.last_check_in.date()
                    today = datetime.now(MSK).date()
                    if last_date == today:
                        # Already checked in today, skip reminder
                        continue
                
                # Build reminder message
                if user.name and user.current_habit:
                    habit_display = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, user.current_habit)
                    message = REMINDER_WITH_HABIT.format(
                        name=user.name,
                        habit=habit_display
                    )
                else:
                    message = REMINDER_MESSAGE
                
                # Send reminder
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=main_menu_keyboard()
                )
                logger.info(f"Sent reminder to user {user.telegram_id}")
                
            except Exception as e:
                logger.error(f"Failed to send reminder to {user.telegram_id}: {e}")


async def send_missed_day_notifications(context) -> None:
    """Send notifications to users who missed their check-in today. Runs at 22:00 MSK."""
    now = datetime.now(MSK)
    today = now.date()
    
    logger.info(f"Checking missed day notifications at {now.strftime('%H:%M')} MSK")
    
    async with async_session() as session:
        # Find all users with completed onboarding
        result = await session.execute(
            select(User).where(User.onboarding_completed == True)
        )
        users = result.scalars().all()
        
        for user in users:
            try:
                # Skip if checked in today
                if user.last_check_in:
                    last_date = user.last_check_in.date()
                    if last_date == today:
                        continue
                    
                    # Calculate days since last check-in
                    days_missed = (today - last_date).days
                else:
                    # Never checked in
                    days_missed = 1
                
                # Don't spam if missed more than 7 days (check every 3 days max)
                if days_missed > 7 and days_missed % 3 != 0:
                    continue
                
                # Build message based on days missed
                if days_missed == 1:
                    # Use random message for single day miss
                    import random
                    message = random.choice(MISSED_DAY_MESSAGES)
                    if user.name:
                        message = f"{user.name}, {message[0].lower()}{message[1:]}"
                else:
                    message = MISSED_MULTIPLE_DAYS.format(days=days_missed)
                    if user.name:
                        message = f"{user.name}, {message[0].lower()}{message[1:]}"
                
                # Send notification
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    reply_markup=main_menu_keyboard()
                )
                logger.info(f"Sent missed day notification to user {user.telegram_id} (missed {days_missed} days)")
                
            except Exception as e:
                logger.error(f"Failed to send missed day notification to {user.telegram_id}: {e}")


def setup_scheduler(application: Application) -> None:
    """Setup the reminder scheduler to run every minute."""
    job_queue = application.job_queue
    
    # Run reminder check every minute
    job_queue.run_repeating(
        send_reminders,
        interval=60,  # Every minute
        first=10  # Start after 10 seconds
    )
    
    # Run missed day check at 22:00 MSK every day
    job_queue.run_daily(
        send_missed_day_notifications,
        time=time(hour=22, minute=0, tzinfo=MSK),
        name="missed_day_check"
    )
    
    logger.info("Reminder scheduler started (reminders every minute, missed day check at 22:00 MSK)")
