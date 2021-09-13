"""
Основной модуль запуска сервиса
"""

from fastapi import FastAPI

from db.config import engine, Base
from endpoints import user, transaction

app = FastAPI()
app.include_router(user.router)
app.include_router(transaction.router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
