#!/usr/bin/env python3
"""Entry point for bothost.ru and similar platforms."""
import sys
import os
import asyncio

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def run_import_once():
    """
    Import users from Excel file if it exists and hasn't been imported yet.
    This runs once on first startup after deploy.
    """
    from pathlib import Path
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from openpyxl import load_workbook
    from sqlalchemy import select
    from bot.database import async_session, init_db
    from bot.models import User
    
    # Check if Excel file exists
    excel_path = Path("database old/mewego_users_20260115_1122.xlsx")
    if not excel_path.exists():
        print("No Excel file to import, skipping...")
        return
    
    # Check if we already imported (marker file)
    marker_path = Path(".import_complete")
    if marker_path.exists():
        print("Import already completed previously, skipping...")
        return
    
    print("=" * 50)
    print("RUNNING ONE-TIME USER IMPORT FROM EXCEL")
    print("=" * 50)
    
    MSK = ZoneInfo("Europe/Moscow")
    
    def parse_datetime(dt_str):
        if not dt_str or dt_str == "":
            return None
        try:
            msk_dt = datetime.strptime(str(dt_str), "%Y-%m-%d %H:%M")
            msk_dt = msk_dt.replace(tzinfo=MSK)
            return msk_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        except Exception:
            return None
    
    def safe_int(value, default=None):
        if value is None or value == "" or value == "None":
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Initialize database
    await init_db()
    
    # Load Excel
    wb = load_workbook(excel_path)
    ws = wb.active
    
    headers = [cell.value for cell in ws[1]]
    col_map = {h: i for i, h in enumerate(headers)}
    print(f"Found columns: {list(col_map.keys())}")
    
    imported = 0
    skipped = 0
    
    async with async_session() as session:
        for row in ws.iter_rows(min_row=2, values_only=True):
            try:
                telegram_id_val = row[col_map.get("Telegram ID", 1)]
                if not telegram_id_val:
                    continue
                
                telegram_id = int(telegram_id_val)
                
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                if result.scalar_one_or_none():
                    skipped += 1
                    continue
                
                def get_col(name, default=None):
                    idx = col_map.get(name)
                    if idx is not None and idx < len(row):
                        val = row[idx]
                        return val if val and val != "None" else default
                    return default
                
                user = User(
                    telegram_id=telegram_id,
                    username=get_col("Username"),
                    name=get_col("Имя"),
                    age=safe_int(get_col("Возраст")),
                    city=get_col("Город"),
                    activity_level=get_col("Активность"),
                    goal=get_col("Цель"),
                    current_habit=get_col("Привычка"),
                    custom_habit=get_col("Своя привычка"),
                    day_cycle=safe_int(get_col("День цикла"), 1),
                    reminder_time=get_col("Время напоминания"),
                    onboarding_completed=(get_col("Онбординг") == "Да"),
                    self_identification=get_col("Самоопознавание"),
                    created_at=parse_datetime(get_col("Дата регистрации (МСК)")),
                    last_check_in=parse_datetime(get_col("Последняя отметка (МСК)")),
                )
                
                session.add(user)
                imported += 1
                print(f"Imported: {user.name} ({telegram_id})")
                
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        await session.commit()
    
    # Create marker file so we don't import again
    marker_path.write_text(f"Import completed at {datetime.now()}")
    
    print(f"\n=== Import Complete ===")
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print("=" * 50)


# Now import and run the bot
from bot.main import main

if __name__ == "__main__":
    # Run import first
    asyncio.run(run_import_once())
    # Then start bot
    main()
