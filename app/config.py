"""
Настройки приложения
"""

from pydantic import BaseSettings


class Settings(BaseSettings):
    SQLALCHEMY_DATABASE_URI: str = "sqlite+aiosqlite:///main.db"


settings = Settings()
