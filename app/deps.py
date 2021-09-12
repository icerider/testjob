from db.config import async_session
from db.dal import DAL

async def get_db():
    """
    Получить DAL, настроенный на новую сессию
    """
    async with async_session() as session:
        async with session.begin():
            yield DAL(session)
