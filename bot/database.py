"""Database connection and session management."""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from bot.config import DATABASE_URL

logger = logging.getLogger(__name__)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def run_migrations():
    """
    Run safe migrations to add missing columns and tables.
    This preserves existing data while adding new schema elements.
    """
    async with engine.begin() as conn:
        # Helper to check if column exists
        async def column_exists(table: str, column: str) -> bool:
            try:
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                columns = [row[1] for row in result.fetchall()]
                return column in columns
            except Exception:
                return False
        
        # Helper to check if table exists
        async def table_exists(table: str) -> bool:
            try:
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table"),
                    {"table": table}
                )
                return result.fetchone() is not None
            except Exception:
                return False
        
        logger.info("Running database migrations...")
        
        # =====================================================================
        # MIGRATION: Add training_preference column to users table
        # =====================================================================
        if await table_exists("users"):
            if not await column_exists("users", "training_preference"):
                logger.info("Adding column: users.training_preference")
                await conn.execute(text(
                    "ALTER TABLE users ADD COLUMN training_preference VARCHAR(50)"
                ))
        
        # =====================================================================
        # MIGRATION: Create polls table
        # =====================================================================
        if not await table_exists("polls"):
            logger.info("Creating table: polls")
            await conn.execute(text("""
                CREATE TABLE polls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    options TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    is_anonymous BOOLEAN DEFAULT 0,
                    allow_multiple BOOLEAN DEFAULT 0,
                    created_by INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    closed_at DATETIME
                )
            """))
        
        # =====================================================================
        # MIGRATION: Create poll_votes table
        # =====================================================================
        if not await table_exists("poll_votes"):
            logger.info("Creating table: poll_votes")
            await conn.execute(text("""
                CREATE TABLE poll_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    poll_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    option_index INTEGER NOT NULL,
                    voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(poll_id) REFERENCES polls(id) ON DELETE CASCADE
                )
            """))
        
        logger.info("Database migrations completed!")


async def init_db():
    """Create all tables and run migrations."""
    from bot import models  # noqa: F401
    
    # First, create any completely new tables via SQLAlchemy
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Then run migrations for existing tables (adding columns, etc.)
    await run_migrations()


async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session

