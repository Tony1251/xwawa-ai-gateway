"""初始化数据库表：通过 app 内核直接创建所有表"""
import asyncio
import os
import sys
from pathlib import Path

# Set database URL before importing app
os.environ["DATABASE_URL"] = "postgresql+asyncpg://xwawa:xwawa_secure_pass@localhost:5433/xwawa_db"
os.environ["REDIS_URL"] = "redis://localhost:6381"
os.environ["APP_SECRET_KEY"] = "dev_secret_key_for_initialization_at_least_32_chars_needed"
os.environ["APP_ENV"] = "development"

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE)

async def init_tables():
    from src.db import init_db, engine
    await init_db()

    # Verify tables were created
    from sqlalchemy import inspect
    async with engine.begin() as conn:
        inspector = inspect(conn.sync_connection)
        tables = await conn.run_sync(lambda conn: inspector.get_table_names())
        print(f"Tables created: {tables}")
        print("Database initialization complete!")

if __name__ == "__main__":
    asyncio.run(init_tables())
