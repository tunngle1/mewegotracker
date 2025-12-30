"""Scheduler for reminders and delayed messages."""
import logging
from datetime import datetime, time
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


def setup_scheduler(application: Application) -> None:
    """Setup the reminder scheduler to run every minute."""
    job_queue = application.job_queue
    
    # Run reminder check every minute
    job_queue.run_repeating(
        send_reminders,
        interval=60,  # Every minute
        first=10  # Start after 10 seconds
    )
    
    logger.info("Reminder scheduler started")
