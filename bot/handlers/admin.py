"""Admin panel handlers."""
import csv
import io
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from bot.database import async_session
from bot.models import User, HabitLog
from bot.config import ADMIN_USERNAMES
from bot.messages import HABITS


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели с кнопками команд."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin:users")],
        [InlineKeyboardButton("📁 Экспорт пользователей", callback_data="admin:export")],
        [InlineKeyboardButton("📋 Экспорт привычек", callback_data="admin:export_habits")],
    ])


def is_admin(username: str) -> bool:
    """Check if user is admin by username."""
    if not username or not ADMIN_USERNAMES:
        return False
    return username.lower() in ADMIN_USERNAMES


async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel with buttons. Command: /admin or button 🔐 Админ-панель"""
    # Support both message and callback query
    if update.callback_query:
        user = update.callback_query.from_user
        reply_func = update.callback_query.message.reply_text
        await update.callback_query.answer()
    else:
        user = update.effective_user
        reply_func = update.message.reply_text
    
    if not is_admin(user.username):
        if update.callback_query:
            await update.callback_query.answer("❌ Нет доступа", show_alert=True)
        else:
            await reply_func("❌ Нет доступа")
        return
    
    await reply_func(
        "🔐 <b>Админ-панель MeWeGo</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin panel button clicks."""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.username):
        await query.answer("❌ Нет доступа", show_alert=True)
        return
    
    action = query.data.split(":")[1]
    
    if action == "stats":
        await show_stats(query)
    elif action == "users":
        await show_users(query)
    elif action == "export":
        await do_export_users(query)
    elif action == "export_habits":
        await do_export_habits(query)


async def show_stats(query) -> None:
    """Show bot statistics."""
    async with async_session() as session:
        # Total users
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        # Completed onboarding
        completed = await session.execute(
            select(func.count(User.id)).where(User.onboarding_completed == True)
        )
        completed = completed.scalar()
        
        # Total check-ins
        total_checkins = await session.execute(select(func.count(HabitLog.id)))
        total_checkins = total_checkins.scalar()
        
        # Today's check-ins
        today = datetime.utcnow().date()
        today_checkins = await session.execute(
            select(func.count(HabitLog.id)).where(
                func.date(HabitLog.completed_at) == today
            )
        )
        today_checkins = today_checkins.scalar()
    
    stats_text = (
        "📊 <b>Статистика MeWeGo</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Прошли онбординг: {completed}\n"
        f"📝 Всего отметок: {total_checkins}\n"
        f"📅 Отметок сегодня: {today_checkins}\n"
    )
    
    await query.message.reply_text(
        stats_text, 
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )


async def show_users(query) -> None:
    """Show users list."""
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(50)
        )
        users = result.scalars().all()
    
    if not users:
        await query.message.reply_text("Пользователей пока нет")
        return
    
    text = "👥 <b>Последние пользователи:</b>\n\n"
    
    for user in users:
        status = "✅" if user.onboarding_completed else "⏳"
        habit = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, "-")
        text += (
            f"{status} <b>{user.name or 'Без имени'}</b>\n"
            f"   📍 {user.city or '-'} | 🎯 {user.goal or '-'}\n"
            f"   🔄 День {user.day_cycle}/30 | ⏰ {user.reminder_time or '-'}\n\n"
        )
    
    await query.message.reply_text(
        text, 
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )


async def users_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all users. Command: /users"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Нет доступа")
        return
    
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(50)
        )
        users = result.scalars().all()
    
    if not users:
        await update.message.reply_text("Пользователей пока нет")
        return
    
    text = "👥 <b>Последние пользователи:</b>\n\n"
    
    for user in users:
        status = "✅" if user.onboarding_completed else "⏳"
        habit = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, "-")
        text += (
            f"{status} <b>{user.name or 'Без имени'}</b>\n"
            f"   📍 {user.city or '-'} | 🎯 {user.goal or '-'}\n"
            f"   🔄 День {user.day_cycle}/30 | ⏰ {user.reminder_time or '-'}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode="HTML")


async def do_export_users(query) -> None:
    """Export users via callback button."""
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    if not users:
        await query.message.reply_text("Нет данных для экспорта")
        return
    
    from zoneinfo import ZoneInfo
    from datetime import timezone
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    
    MSK = ZoneInfo("Europe/Moscow")
    
    def to_msk(dt):
        if not dt:
            return ""
        utc_dt = dt.replace(tzinfo=timezone.utc)
        msk_dt = utc_dt.astimezone(MSK)
        return msk_dt.strftime("%Y-%m-%d %H:%M")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    
    headers = [
        "ID", "Telegram ID", "Username", "Имя", "Возраст", "Город",
        "Активность", "Цель", "Привычка", "Своя привычка",
        "День цикла", "Время напоминания", "Онбординг",
        "Самоопознавание", "Дата регистрации (МСК)", "Последняя отметка (МСК)"
    ]
    ws.append(headers)
    
    for user in users:
        habit_display = dict(HABITS).get(user.current_habit, user.current_habit)
        ws.append([
            user.id,
            user.telegram_id,
            user.username or "",
            user.name or "",
            user.age or "",
            user.city or "",
            user.activity_level or "",
            user.goal or "",
            habit_display or "",
            user.custom_habit or "",
            user.day_cycle,
            user.reminder_time or "",
            "Да" if user.onboarding_completed else "Нет",
            user.self_identification or "",
            to_msk(user.created_at),
            to_msk(user.last_check_in)
        ])
    
    for col_idx, column in enumerate(ws.columns, 1):
        max_length = 0
        column_letter = get_column_letter(col_idx)
        for cell in column:
            try:
                cell_length = len(str(cell.value)) if cell.value else 0
                if cell_length > max_length:
                    max_length = cell_length
            except:
                pass
        ws.column_dimensions[column_letter].width = max_length + 2
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"mewego_users_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    await query.message.reply_document(
        document=output,
        filename=filename,
        caption=f"📊 Экспорт {len(users)} пользователей"
    )


async def do_export_habits(query) -> None:
    """Export habits via callback button."""
    from sqlalchemy.orm import selectinload
    from bot.models import Habit, ScheduleType, LogStatus
    
    async with async_session() as session:
        result = await session.execute(
            select(User).options(
                selectinload(User.habits).selectinload(Habit.logs)
            )
        )
        users = result.scalars().all()
    
    if not users:
        await query.message.reply_text("Нет данных для экспорта")
        return
    
    from zoneinfo import ZoneInfo
    from datetime import timezone
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    
    MSK = ZoneInfo("Europe/Moscow")
    
    def to_msk(dt):
        if not dt:
            return ""
        utc_dt = dt.replace(tzinfo=timezone.utc)
        msk_dt = utc_dt.astimezone(MSK)
        return msk_dt.strftime("%Y-%m-%d %H:%M")
    
    wb = Workbook()
    ws_habits = wb.active
    ws_habits.title = "Привычки"
    
    habits_headers = [
        "ID привычки", "ID пользователя", "Telegram ID", "Имя пользователя",
        "Название привычки", "Тип", "Цель (раз/нед)", "Активна",
        "Всего выполнений", "Дата создания (МСК)"
    ]
    ws_habits.append(habits_headers)
    
    total_habits = 0
    for user in users:
        if not user.habits:
            continue
        for habit in user.habits:
            total_habits += 1
            done_count = sum(1 for log in habit.logs if log.status == LogStatus.DONE) if habit.logs else 0
            schedule_type = "Ежедневно" if habit.schedule_type == ScheduleType.DAILY else f"{habit.weekly_target}x в неделю"
            
            ws_habits.append([
                habit.id, user.id, user.telegram_id, user.name or user.username or "",
                habit.name, schedule_type, habit.weekly_target,
                "Да" if habit.is_active else "Нет", done_count, to_msk(habit.created_at),
            ])
    
    ws_logs = wb.create_sheet("Логи")
    logs_headers = [
        "ID лога", "ID привычки", "Название привычки", "ID пользователя",
        "Имя пользователя", "Дата", "Статус", "День цикла", "Время отметки (МСК)"
    ]
    ws_logs.append(logs_headers)
    
    total_logs = 0
    for user in users:
        if not user.habits:
            continue
        for habit in user.habits:
            if not habit.logs:
                continue
            for log in habit.logs:
                total_logs += 1
                status_text = {
                    LogStatus.DONE: "Выполнено",
                    LogStatus.NOT_DONE: "Не сделал",
                    LogStatus.SKIPPED: "Пропуск",
                }.get(log.status, str(log.status))
                
                ws_logs.append([
                    log.id, habit.id, habit.name, user.id, user.name or user.username or "",
                    log.log_date.strftime("%Y-%m-%d") if log.log_date else "",
                    status_text, log.day_cycle or "", to_msk(log.completed_at),
                ])
    
    for ws in [ws_habits, ws_logs]:
        for col_idx, column in enumerate(ws.columns, 1):
            max_length = 0
            column_letter = get_column_letter(col_idx)
            for cell in column:
                try:
                    cell_length = len(str(cell.value)) if cell.value else 0
                    if cell_length > max_length:
                        max_length = cell_length
                except:
                    pass
            ws.column_dimensions[column_letter].width = max_length + 2
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"mewego_habits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    await query.message.reply_document(
        document=output,
        filename=filename,
        caption=f"📊 Экспорт: {total_habits} привычек, {total_logs} логов"
    )


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all users to Excel. Command: /export"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Нет доступа")
        return
    
    async with async_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    if not users:
        await update.message.reply_text("Нет данных для экспорта")
        return
    
    # Moscow timezone
    from zoneinfo import ZoneInfo
    from datetime import timezone
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    
    MSK = ZoneInfo("Europe/Moscow")
    
    def to_msk(dt):
        """Convert UTC datetime to Moscow time string."""
        if not dt:
            return ""
        utc_dt = dt.replace(tzinfo=timezone.utc)
        msk_dt = utc_dt.astimezone(MSK)
        return msk_dt.strftime("%Y-%m-%d %H:%M")
    
    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    
    # Header
    headers = [
        "ID", "Telegram ID", "Username", "Имя", "Возраст", "Город",
        "Активность", "Цель", "Привычка", "Своя привычка",
        "День цикла", "Время напоминания", "Онбординг",
        "Самоопознавание", "Дата регистрации (МСК)", "Последняя отметка (МСК)"
    ]
    ws.append(headers)
    
    # Data
    for user in users:
        habit_display = dict(HABITS).get(user.current_habit, user.current_habit)
        ws.append([
            user.id,
            user.telegram_id,
            user.username or "",
            user.name or "",
            user.age or "",
            user.city or "",
            user.activity_level or "",
            user.goal or "",
            habit_display or "",
            user.custom_habit or "",
            user.day_cycle,
            user.reminder_time or "",
            "Да" if user.onboarding_completed else "Нет",
            user.self_identification or "",
            to_msk(user.created_at),
            to_msk(user.last_check_in)
        ])
    
    # Auto-size columns
    for col_idx, column in enumerate(ws.columns, 1):
        max_length = 0
        column_letter = get_column_letter(col_idx)
        for cell in column:
            try:
                cell_length = len(str(cell.value)) if cell.value else 0
                if cell_length > max_length:
                    max_length = cell_length
            except:
                pass
        ws.column_dimensions[column_letter].width = max_length + 2
    
    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"mewego_users_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    await update.message.reply_document(
        document=output,
        filename=filename,
        caption=f"📊 Экспорт {len(users)} пользователей"
    )


async def export_habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all habits and logs to Excel. Command: /export_habits"""
    if not is_admin(update.effective_user.username):
        await update.message.reply_text("❌ Нет доступа")
        return
    
    from sqlalchemy.orm import selectinload
    from bot.models import Habit, ScheduleType, LogStatus
    
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.habits).selectinload(Habit.logs)
            )
        )
        users = result.scalars().all()
    
    if not users:
        await update.message.reply_text("Нет данных для экспорта")
        return
    
    # Moscow timezone
    from zoneinfo import ZoneInfo
    from datetime import timezone
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    
    MSK = ZoneInfo("Europe/Moscow")
    
    def to_msk(dt):
        """Convert UTC datetime to Moscow time string."""
        if not dt:
            return ""
        utc_dt = dt.replace(tzinfo=timezone.utc)
        msk_dt = utc_dt.astimezone(MSK)
        return msk_dt.strftime("%Y-%m-%d %H:%M")
    
    # Create Excel workbook
    wb = Workbook()
    
    # ========== Sheet 1: Habits ==========
    ws_habits = wb.active
    ws_habits.title = "Привычки"
    
    habits_headers = [
        "ID привычки", "ID пользователя", "Telegram ID", "Имя пользователя",
        "Название привычки", "Тип", "Цель (раз/нед)", "Активна",
        "Всего выполнений", "Дата создания (МСК)"
    ]
    ws_habits.append(habits_headers)
    
    total_habits = 0
    for user in users:
        if not user.habits:
            continue
        for habit in user.habits:
            total_habits += 1
            done_count = sum(1 for log in habit.logs if log.status == LogStatus.DONE) if habit.logs else 0
            schedule_type = "Ежедневно" if habit.schedule_type == ScheduleType.DAILY else f"{habit.weekly_target}x в неделю"
            
            ws_habits.append([
                habit.id,
                user.id,
                user.telegram_id,
                user.name or user.username or "",
                habit.name,
                schedule_type,
                habit.weekly_target,
                "Да" if habit.is_active else "Нет",
                done_count,
                to_msk(habit.created_at),
            ])
    
    # ========== Sheet 2: Logs ==========
    ws_logs = wb.create_sheet("Логи")
    
    logs_headers = [
        "ID лога", "ID привычки", "Название привычки", "ID пользователя",
        "Имя пользователя", "Дата", "Статус", "День цикла", "Время отметки (МСК)"
    ]
    ws_logs.append(logs_headers)
    
    total_logs = 0
    for user in users:
        if not user.habits:
            continue
        for habit in user.habits:
            if not habit.logs:
                continue
            for log in habit.logs:
                total_logs += 1
                status_text = {
                    LogStatus.DONE: "Выполнено",
                    LogStatus.NOT_DONE: "Не сделал",
                    LogStatus.SKIPPED: "Пропуск",
                }.get(log.status, str(log.status))
                
                ws_logs.append([
                    log.id,
                    habit.id,
                    habit.name,
                    user.id,
                    user.name or user.username or "",
                    log.log_date.strftime("%Y-%m-%d") if log.log_date else "",
                    status_text,
                    log.day_cycle or "",
                    to_msk(log.completed_at),
                ])
    
    # Auto-size columns for both sheets
    for ws in [ws_habits, ws_logs]:
        for col_idx, column in enumerate(ws.columns, 1):
            max_length = 0
            column_letter = get_column_letter(col_idx)
            for cell in column:
                try:
                    cell_length = len(str(cell.value)) if cell.value else 0
                    if cell_length > max_length:
                        max_length = cell_length
                except:
                    pass
            ws.column_dimensions[column_letter].width = max_length + 2
    
    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"mewego_habits_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    await update.message.reply_document(
        document=output,
        filename=filename,
        caption=f"📊 Экспорт: {total_habits} привычек, {total_logs} логов"
    )


async def notify_admin_new_user(bot, user: User) -> None:
    """Send notification to all admins about new user."""
    if not ADMIN_USERNAMES:
        return
    
    try:
        # Find all admins by username
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username.in_(ADMIN_USERNAMES))
            )
            admins = result.scalars().all()
            
            if not admins:
                return
        
        habit_display = user.custom_habit if user.current_habit == "custom" else dict(HABITS).get(user.current_habit, user.current_habit)
        
        text = (
            "🆕 <b>Новый пользователь!</b>\n\n"
            f"👤 Имя: {user.name}\n"
            f"🎂 Возраст: {user.age}\n"
            f"📍 Город: {user.city}\n"
            f"💪 Активность: {user.activity_level}\n"
            f"🎯 Цель: {user.goal}\n"
            f"🏃 Привычка: {habit_display}\n"
            f"⏰ Напоминания: {user.reminder_time}\n"
            f"📊 Самоопознавание: {user.self_identification}\n"
        )
        
        # Send to all admins
        for admin in admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=text,
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception:
        pass  # Ignore errors

