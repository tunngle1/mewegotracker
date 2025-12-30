"""Bot configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./mewego.db")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+lOPMmFYpwMowYTZi")

# Список админов (через запятую)
ADMIN_USERNAMES_RAW = os.getenv("ADMIN_USERNAMES", "")
ADMIN_USERNAMES = [u.strip().lower() for u in ADMIN_USERNAMES_RAW.split(",") if u.strip()]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен! Добавьте его в .env файл.")
