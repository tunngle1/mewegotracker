"""Onboarding handlers for new users."""
import asyncio
from datetime import datetime
from pathlib import Path

from telegram import Update, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Habit, ScheduleType
from bot.messages import (
    WELCOME_MESSAGES,
    WHY_MEWEGO,
    SELF_IDENTIFICATION_QUESTION,
    SELF_IDENTIFICATION_OPTIONS,
    NORMALIZATION_MESSAGE,
    HABIT_CHOICE_MESSAGE,
    HABIT_HINT,
    HABITS,
    CUSTOM_HABIT_PROMPT,
    FIRST_CHECK_IN_MESSAGE,
    CHECK_IN_CONFIRMATION,
    PROFILE_INTRO,
    PROFILE_QUESTIONS,
    ONBOARDING_COMPLETE,
    CHANNEL_PROMO
)
from bot.keyboards import (
    start_keyboard,
    self_identification_keyboard,
    habit_choice_keyboard,
    check_in_keyboard,
    activity_level_keyboard,
    goal_keyboard,
    reminder_time_keyboard,
    channel_keyboard,
    main_menu_keyboard
)
from bot.handlers.admin import notify_admin_new_user

# Conversation states
(
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
) = range(12)


async def get_or_create_user(telegram_id: int, username: str = None, 
                              first_name: str = None, last_name: str = None) -> User:
    """Get existing user or create a new one."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                onboarding_step="start"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # Update Telegram info
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
        
        return user


async def update_user(telegram_id: int, **kwargs) -> User:
    """Update user fields."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            for key, value in kwargs.items():
                setattr(user, key, value)
            await session.commit()
            await session.refresh(user)
        
        return user


async def get_user_by_telegram_id(telegram_id: int) -> User:
    """Get user by telegram ID."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def create_first_habit(telegram_id: int) -> None:
    """Create the first habit from onboarding choice."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.current_habit:
            return
        
        # Get habit name from onboarding choice
        if user.current_habit == "custom" and user.custom_habit:
            habit_name = user.custom_habit
        else:
            # Map habit IDs to names
            habit_names = {
                "walk": "🚶‍♀️ 5 минут движения",
                "water": "💧 Выпить воду",
                "outdoor": "🌿 Прогулка",
                "yoga": "🧘‍♀️ Любое движение",
            }
            habit_name = habit_names.get(user.current_habit, user.current_habit)
        
        # Check if habit already exists
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(User)
            .options(selectinload(User.habits))
            .where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Only create if no habits exist
        if not user.habits:
            habit = Habit(
                user_id=user.id,
                name=habit_name,
                schedule_type=ScheduleType.DAILY,
                weekly_target=7,
                is_active=True,
            )
            session.add(habit)
            await session.commit()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start command - begin onboarding."""
    user_data = update.effective_user
    
    # Create or get user
    user = await get_or_create_user(
        telegram_id=user_data.id,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    
    # If already completed onboarding, show main menu
    if user.onboarding_completed:
        habit_name = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, "")
        await update.message.reply_text(
            f"С возвращением, {user.name or 'друг'}! 🤍\n\n"
            f"Твоя привычка: {habit_name}\n"
            f"День цикла: {user.day_cycle}/30",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Assets directory
    assets_dir = Path(__file__).parent.parent / "assets"
    
    # Send first photo with welcome messages
    photo_1 = assets_dir / "Сообщение 1.png"
    if photo_1.exists():
        with open(photo_1, 'rb') as f:
            await update.message.reply_photo(photo=f)
    
    # Send welcome messages with 3-second pauses
    for message in WELCOME_MESSAGES:
        await update.message.reply_text(message)
        await asyncio.sleep(3)
    
    # Send WHY MEWEGO with photo and caption
    photo_mewego = assets_dir / "ПОЧЕМУ MeWeGo.png"
    if photo_mewego.exists():
        with open(photo_mewego, 'rb') as f:
            await update.message.reply_photo(photo=f, caption=WHY_MEWEGO[0])
    else:
        await update.message.reply_text(WHY_MEWEGO[0])
    await asyncio.sleep(3)
    
    # Send photo of Natalya with caption
    photo_natalya = assets_dir / "Я Наталья Мелихова.png"
    if photo_natalya.exists():
        with open(photo_natalya, 'rb') as f:
            await update.message.reply_photo(photo=f, caption=WHY_MEWEGO[1])
    else:
        await update.message.reply_text(WHY_MEWEGO[1])
    await asyncio.sleep(3)
    
    # Show start button
    await update.message.reply_text(
        "👇",
        reply_markup=start_keyboard()
    )
    
    await update_user(user_data.id, onboarding_step="waiting_start")
    return WAITING_START


async def start_journey_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle 'Начать' button click."""
    query = update.callback_query
    await query.answer()
    
    # Send self-identification photo with question
    assets_dir = Path(__file__).parent.parent / "assets"
    photo_self_id = assets_dir / "САМООПОЗНАВАНИЕ.png"
    if photo_self_id.exists():
        with open(photo_self_id, 'rb') as f:
            await query.message.reply_photo(photo=f, caption=SELF_IDENTIFICATION_QUESTION)
    else:
        await query.message.reply_text(SELF_IDENTIFICATION_QUESTION)
    
    await asyncio.sleep(3)
    await query.message.reply_text(
        "Выбери вариант ниже:",
        reply_markup=self_identification_keyboard()
    )
    
    await update_user(query.from_user.id, onboarding_step="self_identification")
    return WAITING_SELF_ID


async def self_identification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle self-identification choice."""
    query = update.callback_query
    await query.answer()
    
    # Extract choice index
    choice_idx = int(query.data.split("_")[-1])
    choice = SELF_IDENTIFICATION_OPTIONS[choice_idx]
    
    # Save choice
    await update_user(query.from_user.id, 
                      self_identification=choice,
                      onboarding_step="habit_choice")
    
    # Send normalization photo with message
    assets_dir = Path(__file__).parent.parent / "assets"
    photo_norm = assets_dir / "НОРМАЛИЗАЦИЯ.png"
    if photo_norm.exists():
        with open(photo_norm, 'rb') as f:
            await query.message.reply_photo(photo=f, caption=NORMALIZATION_MESSAGE)
    else:
        await query.message.reply_text(NORMALIZATION_MESSAGE)
    await asyncio.sleep(3)
    
    # Send habit choice photo with message
    photo_habit = assets_dir / "ПРОСТОЙ СТАРТ.png"
    if photo_habit.exists():
        with open(photo_habit, 'rb') as f:
            await query.message.reply_photo(photo=f, caption=HABIT_CHOICE_MESSAGE)
    else:
        await query.message.reply_text(HABIT_CHOICE_MESSAGE)
    
    await asyncio.sleep(3)
    # Send habit choice buttons
    await query.message.reply_text(
        HABIT_HINT,
        reply_markup=habit_choice_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    return WAITING_HABIT


async def habit_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle habit choice."""
    query = update.callback_query
    await query.answer()
    
    habit_id = query.data.split("_")[1]
    
    if habit_id == "custom":
        # Ask for custom habit
        await query.message.reply_text(CUSTOM_HABIT_PROMPT)
        await update_user(query.from_user.id, 
                          current_habit="custom",
                          onboarding_step="custom_habit")
        return WAITING_CUSTOM_HABIT
    
    # Save habit
    await update_user(query.from_user.id, 
                      current_habit=habit_id,
                      onboarding_step="first_checkin")
    
    # Show first check-in message
    await query.message.reply_text(
        FIRST_CHECK_IN_MESSAGE,
        reply_markup=check_in_keyboard()
    )
    
    return WAITING_FIRST_CHECKIN


async def custom_habit_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom habit text input."""
    custom_habit = update.message.text.strip()
    
    await update_user(update.effective_user.id,
                      custom_habit=custom_habit,
                      onboarding_step="first_checkin")
    
    await update.message.reply_text(
        FIRST_CHECK_IN_MESSAGE,
        reply_markup=check_in_keyboard()
    )
    
    return WAITING_FIRST_CHECKIN


async def first_checkin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle first check-in."""
    query = update.callback_query
    await query.answer()
    
    # Record first check-in
    await update_user(query.from_user.id,
                      last_check_in=datetime.utcnow(),
                      day_cycle=1,
                      onboarding_step="profile_name")
    
    await query.message.reply_text(CHECK_IN_CONFIRMATION)
    await asyncio.sleep(3)
    
    # Send profile photo with intro message
    assets_dir = Path(__file__).parent.parent / "assets"
    photo_profile = assets_dir / "Чтобы поддерживать тебя дальше.png"
    if photo_profile.exists():
        with open(photo_profile, 'rb') as f:
            await query.message.reply_photo(photo=f, caption=PROFILE_INTRO)
    else:
        await query.message.reply_text(PROFILE_INTRO)
    
    await asyncio.sleep(3)
    await query.message.reply_text(PROFILE_QUESTIONS[0][1])  # "Как тебя зовут?"
    
    return WAITING_NAME


async def name_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle name input."""
    name = update.message.text.strip()
    
    await update_user(update.effective_user.id,
                      name=name,
                      onboarding_step="profile_age")
    
    await update.message.reply_text(PROFILE_QUESTIONS[1][1])  # "Сколько тебе лет?"
    return WAITING_AGE


async def age_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle age input."""
    age_text = update.message.text.strip()
    
    try:
        age = int(age_text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число.")
        return WAITING_AGE
    
    await update_user(update.effective_user.id,
                      age=age,
                      onboarding_step="profile_city")
    
    await update.message.reply_text(PROFILE_QUESTIONS[2][1])  # "Из какого ты города?"
    return WAITING_CITY


async def city_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle city input."""
    city = update.message.text.strip()
    
    await update_user(update.effective_user.id,
                      city=city,
                      onboarding_step="profile_activity")
    
    await update.message.reply_text(
        PROFILE_QUESTIONS[3][1],  # "Какая у тебя активность?"
        reply_markup=activity_level_keyboard()
    )
    return WAITING_ACTIVITY


async def activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle activity level choice."""
    query = update.callback_query
    await query.answer()
    
    activity = query.data.replace("activity_", "")
    
    await update_user(query.from_user.id,
                      activity_level=activity,
                      onboarding_step="profile_goal")
    
    await query.message.reply_text(
        PROFILE_QUESTIONS[4][1],  # "Какая твоя цель?"
        reply_markup=goal_keyboard()
    )
    return WAITING_GOAL


async def goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle goal choice."""
    query = update.callback_query
    await query.answer()
    
    goal = query.data.replace("goal_", "")
    
    await update_user(query.from_user.id,
                      goal=goal,
                      onboarding_step="profile_reminder")
    
    await query.message.reply_text(
        PROFILE_QUESTIONS[5][1],  # "Когда удобно получать напоминания?"
        reply_markup=reminder_time_keyboard(),
        parse_mode=ParseMode.HTML
    )
    return WAITING_REMINDER_TIME


async def reminder_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle reminder time choice - finish onboarding."""
    query = update.callback_query
    await query.answer()
    
    reminder_time = query.data.replace("reminder_", "")
    
    if reminder_time == "custom":
        await query.message.reply_text("Напиши время в формате ЧЧ:ММ (например, 09:30 или 21:00)")
        return WAITING_CUSTOM_REMINDER
    
    await update_user(query.from_user.id,
                      reminder_time=reminder_time,
                      onboarding_completed=True,
                      onboarding_step="completed")
    
    # Create first habit from onboarding choice
    await create_first_habit(query.from_user.id)
    
    # Send final message
    await query.message.reply_text(
        ONBOARDING_COMPLETE,
        reply_markup=main_menu_keyboard(query.from_user.username)
    )
    
    # Schedule channel promo after 5-10 minutes
    context.job_queue.run_once(
        send_channel_promo,
        when=300,  # 5 minutes
        data=query.from_user.id,
        name=f"channel_promo_{query.from_user.id}"
    )
    
    # Notify admin about new user
    user = await get_user_by_telegram_id(query.from_user.id)
    if user:
        await notify_admin_new_user(context.bot, user)
    
    return ConversationHandler.END


async def custom_reminder_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom reminder time input."""
    time_text = update.message.text.strip()
    
    try:
        # Validate format
        datetime.strptime(time_text, "%H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пожалуйста, введи время как ЧЧ:ММ (например, 08:30).")
        return WAITING_CUSTOM_REMINDER
    
    await update_user(update.effective_user.id,
                      reminder_time=time_text,
                      onboarding_completed=True,
                      onboarding_step="completed")
    
    # Create first habit from onboarding choice
    await create_first_habit(update.effective_user.id)
    
    # Send final message
    await update.message.reply_text(
        ONBOARDING_COMPLETE,
        reply_markup=main_menu_keyboard(update.effective_user.username)
    )
    
    # Schedule channel promo after 5-10 minutes
    context.job_queue.run_once(
        send_channel_promo,
        when=300,  # 5 minutes
        data=update.effective_user.id,
        name=f"channel_promo_{update.effective_user.id}"
    )
    
    # Notify admin about new user
    user = await get_user_by_telegram_id(update.effective_user.id)
    if user:
        await notify_admin_new_user(context.bot, user)
    
    return ConversationHandler.END


async def send_channel_promo(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send channel promotion message after delay."""
    telegram_id = context.job.data
    
    await context.bot.send_message(
        chat_id=telegram_id,
        text=CHANNEL_PROMO,
        reply_markup=channel_keyboard()
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel onboarding."""
    await update.message.reply_text("Онбординг отменён. Нажми /start чтобы начать заново.")
    return ConversationHandler.END
