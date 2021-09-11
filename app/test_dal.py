import pytest
from db.config import engine, Base, async_session
from db.model import User, Transaction, Balance
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload, Session
from db.dal import UserDAL, NonUniqueEmail, TransactionDAL, DAL


@pytest.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        async with session.begin():
            yield session


@pytest.fixture
async def user_dal(db: Session):
    yield UserDAL(db)


async def dal(db: Session):
    yield DAL(db)


@pytest.mark.asyncio
async def test_userdal_create(user_dal: UserDAL):
    """
    Тест на создание пользователя
    """
    user1 = await user_dal.create(
        "test@example.org",
        "secret"
    )
    # пароль не хранится в открытом виде
    assert user1.password_hash != "secret"
    # для пользователя создан баланс
    assert user1.balance.amount == 0.0

    # проверка на дубль email
    with pytest.raises(NonUniqueEmail):
        await user_dal.create(
            "test@example.org",
            "secret"
        )


@pytest.mark.asyncio
async def test_userdal_get_with_balance(user_dal: UserDAL):
    """
    Тест на получение пользователя с балансом по id, email
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await user_dal.create(
        email1,
        "secret"
    )
    user2 = await user_dal.create(
        email2,
        "secret"
    )

    user = await user_dal.get_with_balance(user1.id)
    assert user.email == "test1@example.org"
    assert user.balance.amount == 0.0

    user = await user_dal.get_with_balance(user2.id)
    assert user.email == "test2@example.org"
    assert user.balance.amount == 0.0

    user = await user_dal.get_with_balance(email=email1)
    assert user.id == user1.id
    assert user.balance.amount == 0.0

    user = await user_dal.get_with_balance(email=email2)
    assert user.id == user2.id
    assert user.balance.amount == 0.0


@pytest.mark.asyncio
async def test_refill_transaction(dal: DAL):
    email1 = "test1@example.org"
    user1 = await dal.users.create(
        email1,
        "secret"
    )
