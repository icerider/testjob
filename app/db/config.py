"""
Модуль конфигурации к базе данных
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    future=True,
    # echo=True,
    # isolation_level='REPEATABLE READ'
)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()
