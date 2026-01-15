"""
Script to view all users in the database.
Run: python view_users.py
"""
import asyncio
from sqlalchemy import select

from bot.database import async_session, init_db
from bot.models import User


async def view_users():
    """View all users in database."""
    await init_db()
    
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.id)
        )
        users = result.scalars().all()
    
    print(f"\n{'='*60}")
    print(f"TOTAL USERS: {len(users)}")
    print(f"{'='*60}\n")
    
    for user in users:
        status = "✅" if user.onboarding_completed else "⏳"
        print(f"{status} ID: {user.id} | TG: {user.telegram_id}")
        print(f"   Имя: {user.name} | Возраст: {user.age} | Город: {user.city}")
        print(f"   Активность: {user.activity_level} | Цель: {user.goal}")
        print(f"   Привычка: {user.current_habit} | Своя: {user.custom_habit}")
        print(f"   День: {user.day_cycle}/30 | Напоминание: {user.reminder_time}")
        print(f"   Создан: {user.created_at}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(view_users())
