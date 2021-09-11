import pytest
from db.config import engine, Base, async_session
from db.model import User, Transaction, Balance
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload, Session
from db.dal import UserDAL, NonUniqueEmail, TransactionDAL, DAL, AttemptModifyResolved
from db.model import User


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


@pytest.fixture
async def dal(db: Session):
    yield DAL(db)


@pytest.mark.asyncio
async def test_userdal_create(user_dal: UserDAL):
    """
    Тест на создание пользователя
    """
    user1 = await user_dal.create("test@example.org", "secret")
    # пароль не хранится в открытом виде
    assert user1.password_hash != "secret"
    # для пользователя создан баланс
    assert user1.balance.amount == 0.0

    # проверка на дубль email
    with pytest.raises(NonUniqueEmail):
        await user_dal.create("test@example.org", "secret")


@pytest.mark.asyncio
async def test_userdal_get_with_balance(user_dal: UserDAL):
    """
    Тест на получение пользователя с балансом по id, email
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await user_dal.create(email1, "secret")
    user2 = await user_dal.create(email2, "secret")

    # получение пользователя с балансом по id
    user = await user_dal.get_with_balance(user1.id)
    assert user.email == "test1@example.org"
    assert user.balance.amount == 0.0

    user = await user_dal.get_with_balance(user2.id)
    assert user.email == "test2@example.org"
    assert user.balance.amount == 0.0

    # получение пользователя с балансом по email
    user = await user_dal.get_with_balance(email=email1)
    assert user.id == user1.id
    assert user.balance.amount == 0.0

    user = await user_dal.get_with_balance(email=email2)
    assert user.id == user2.id
    assert user.balance.amount == 0.0


@pytest.mark.asyncio
async def test_create_refill_transaction(dal: DAL):
    """
    Проверка прямой транзакции
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await dal.users.create(email1, "secret")
    user2 = await dal.users.create(email2, "secret")
    await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.create_refill(user2, 40.0)

    # проверка, что транзакция закреплена за своим пользователем
    user1 = await dal.users.get_with_transactions(user1.id)
    assert len(user1.transactions) == 1
    assert user1.transactions[0].amount == 35.0
    user2 = await dal.users.get_with_transactions(user2.id)
    assert len(user2.transactions) == 1
    assert user2.transactions[0].amount == 40.0


@pytest.mark.asyncio
async def test_create_transfer_transaction(dal: DAL):
    """
    Проверка прямой транзакции
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await dal.users.create(email1, "secret")
    user2 = await dal.users.create(email2, "secret")
    await dal.transactions.create_transfer(user1, user2, 35.0)

    # проверка, что транзакция перевод находится в коллекции обоих пользователей
    user1 = await dal.users.get_with_transactions(user1.id)
    assert len(user1.transactions) == 1
    assert user1.transactions[0].amount == 35.0
    user2 = await dal.users.get_with_transactions(user2.id)
    assert len(user2.transactions) == 1
    assert user2.transactions[0].amount == 35.0


@pytest.mark.asyncio
async def test_userdal_get_full(dal: DAL):
    """
    Тест на получение пользователя с балансом по id, email
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")

    await dal.transactions.create_refill(user1, 35.0)
    # получение пользователя с балансом по id
    user = await dal.users.get_full(user1.id)
    assert user.email == "test1@example.org"
    assert user.balance.amount == 0.0
    assert len(user.transactions) == 1


@pytest.mark.asyncio
async def test_commit_transaction(dal: DAL):
    """
    Проверка подтверждения транзакции
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await dal.users.create(email1, "secret")
    user2 = await dal.users.create(email2, "secret")

    assert user1.balance.amount == 0.0
    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.commit(transaction)

    user1 = await dal.users.get_full(user1.id)
    assert user1.balance.amount == 35.0
    transaction = await dal.transactions.create_transfer(user1, user2,  20.0)
    await dal.transactions.commit(transaction)

    user1 = await dal.users.get_full(user1.id)
    user2 = await dal.users.get_full(user2.id)
    assert user1.balance.amount == 15.0
    assert user2.balance.amount == 20.0


@pytest.mark.asyncio
async def test_reject_transaction(dal: DAL):
    """
    Проверка отклонения транзакции
    """
    email1 = "test1@example.org"
    email2 = "test2@example.org"
    user1 = await dal.users.create(email1, "secret")
    user2 = await dal.users.create(email2, "secret")

    assert user1.balance.amount == 0.0
    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.reject(transaction)

    user1 = await dal.users.get_full(user1.id)
    assert user1.balance.amount == 0.0
    transaction = await dal.transactions.create_transfer(user1, user2,  20.0)
    await dal.transactions.reject(transaction)

    user1 = await dal.users.get_full(user1.id)
    user2 = await dal.users.get_full(user2.id)
    assert user1.balance.amount == 0.0
    assert user2.balance.amount == 0.0


@pytest.mark.asyncio
async def test_commit_resolved_transaction(dal: DAL):
    """
    Проверка подтверждения транзакции
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")

    assert user1.balance.amount == 0.0
    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.commit(transaction)
    with pytest.raises(AttemptModifyResolved):
        await dal.transactions.commit(transaction)

    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.reject(transaction)
    with pytest.raises(AttemptModifyResolved):
        await dal.transactions.commit(transaction)


@pytest.mark.asyncio
async def test_reject_resolved_transaction(dal: DAL):
    """
    Проверка подтверждения транзакции
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")

    assert user1.balance.amount == 0.0
    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.commit(transaction)
    with pytest.raises(AttemptModifyResolved):
        await dal.transactions.reject(transaction)

    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.reject(transaction)
    with pytest.raises(AttemptModifyResolved):
        await dal.transactions.reject(transaction)


# TODO: нужен тест, который проверит одновременный коммит транзакции
