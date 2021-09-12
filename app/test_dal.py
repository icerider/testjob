import pytest
from db.config import engine, Base, async_session
from db.model import User, Transaction, Balance
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload, Session
from db.dal import UserDAL, NonUniqueEmail, TransactionDAL, DAL, \
        AttemptModifyResolved, RefundError, RefundErrorType, DataRange
from db.model import User, TransactionResolve, TransactionStatus
from contextlib import asynccontextmanager


@pytest.fixture
async def db():
    async with engine.begin() as conn:
        #await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        async with session.begin():
            await session.execute("DELETE from users;")
            await session.execute("DELETE from transactions;")
            await session.execute("DELETE from balances;")
            await session.execute("DELETE from transactions_refund;")
            await session.execute("DELETE from transactions_resolve;")
    async with async_session() as session:
        async with session.begin():
            yield session


@pytest.fixture
async def user_dal(db: Session):
    yield UserDAL(db)


@pytest.fixture
async def dal(db: Session):
    yield DAL(db)


@asynccontextmanager
async def newdal():
    async with async_session() as session:
        async with session.begin():
            yield DAL(session)


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


@pytest.mark.asyncio
async def test_status_refund_refunded(dal: DAL):
    """
    Проверка корректного полчения списка транзакций
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")
    transaction = await dal.transactions.create_refill(user1, 35.0)
    transaction.resolve = None
    assert transaction.status == TransactionStatus.New
    transaction.resolve = TransactionResolve(
        transaction=transaction,
        status=TransactionStatus.Commited
    )
    await dal.db_session.commit()
    assert transaction.status == TransactionStatus.Commited

    async with newdal() as other_dal:
        assert dal.db_session != other_dal.db_session
        user = await other_dal.users.get_full(user1.id)
        assert user.balance.amount == 0.0
        print(user.transactions[0].status)
        print(user.transactions[0].refund)
        print(user.transactions[0].refunded)


@pytest.mark.asyncio
async def test_refund_transaction(dal: DAL):
    """
    Проверка транзакции возврата
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")

    transaction = await dal.transactions.create_refill(user1, 35.0)
    await dal.transactions.commit(transaction)

    refund = await dal.transactions.refund(transaction)
    assert refund

    transaction = await dal.transactions.get(transaction.id)
    assert transaction.refunded
    transaction = await dal.transactions.get(refund.id)
    assert transaction.refund


@pytest.mark.asyncio
async def test_err_refund_not_commit(dal: DAL):
    """
    Проверка выполнить возврат неподтверждённой транзакции
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")
    transaction = await dal.transactions.create_refill(user1, 35.0)

    with pytest.raises(RefundError) as ex:
        await dal.transactions.refund(transaction)
    assert ex.value.err == RefundErrorType.AttemptRefundNotResolved

    await dal.transactions.reject(transaction)
    with pytest.raises(RefundError) as ex:
        await dal.transactions.refund(transaction)
    assert ex.value.err == RefundErrorType.AttemptRefundRejected


@pytest.mark.asyncio
async def test_err_refund_transfer(dal: DAL):
    """
    Проверка выполнить возврат неподтверждённой транзакции
    """
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")
    email2 = "test2@example.org"
    user2 = await dal.users.create(email2, "secret")
    transaction = await dal.transactions.create_transfer(user1, user2, 35.0)
    await dal.transactions.commit(transaction)

    with pytest.raises(RefundError) as ex:
        await dal.transactions.refund(transaction)
    assert ex.value.err == RefundErrorType.AttemptRefundTransfer


@pytest.mark.asyncio
async def test_err_refund_refunded(dal: DAL):
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")
    transaction = await dal.transactions.create_refill(user1, 35.0)

    await dal.transactions.commit(transaction)
    refund_transaction = await dal.transactions.refund(transaction)

    with pytest.raises(RefundError) as ex:
        await dal.transactions.refund(transaction)
    assert ex.value.err == RefundErrorType.AttemptRefundRefunded

    await dal.transactions.commit(refund_transaction)
    with pytest.raises(RefundError) as ex:
        await dal.transactions.refund(refund_transaction)
    assert ex.value.err == RefundErrorType.AttemptRefundToRefund


@pytest.mark.asyncio
async def test_get_transactions(dal: DAL):
    email1 = "test1@example.org"
    user1 = await dal.users.create(email1, "secret")
    email2 = "test2@example.org"
    user2 = await dal.users.create(email2, "secret")

    transaction1 = await dal.transactions.create_refill(user1, 35.0)
    transaction2 = await dal.transactions.create_refill(user1, 40.0)
    transaction3 = await dal.transactions.create_refill(user2, 20.0)
    transaction4 = await dal.transactions.create_transfer(user1, user2, 20)

    # проверка у пользователя 2 прямых и перевод
    transactions = await dal.transactions.getall(user1)
    assert len(transactions) == 3

    # проверка range
    transactions = await dal.transactions.getall(user1, DataRange(offset=1))
    assert len(transactions) == 2
    assert transactions[0].id == transaction2.id
    assert transactions[1].id == transaction4.id
    transactions = await dal.transactions.getall(user1, DataRange(count=1))
    assert len(transactions) == 1
    assert transactions[0].id == transaction1.id

    # проверка у пользователя прямая и перевод от user1
    transactions = await dal.transactions.getall(user2)
    assert len(transactions) == 2
    assert transactions[0].id == transaction3.id
    assert transactions[1].id == transaction4.id


# TODO: нужен тест, который проверит одновременный коммит транзакции
# TODO: нужен тест, который проверит одновременный refund транзакции
