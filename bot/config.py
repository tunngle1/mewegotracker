"""Bot configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token - можно задать через переменную окружения или напрямую
BOT_TOKEN = os.getenv("BOT_TOKEN", "8500103835:AAGWq1FRvRy-W211TzqsxTUYQpiNY5cjI34")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./mewego.db")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+lOPMmFYpwMowYTZi")

# Список админов (прописаны напрямую для bothost.ru)
DEFAULT_ADMINS = ["tnngl", "melikhova_natalya"]
ADMIN_USERNAMES_RAW = os.getenv("ADMIN_USERNAMES", "")
if ADMIN_USERNAMES_RAW:
    ADMIN_USERNAMES = [u.strip().lower() for u in ADMIN_USERNAMES_RAW.split(",") if u.strip()]
else:
    ADMIN_USERNAMES = [u.lower() for u in DEFAULT_ADMINS]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен! Добавьте его в .env файл.")

