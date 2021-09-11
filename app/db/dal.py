import typing as t
from sqlalchemy.exc import IntegrityError
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime

from db.model import User, Balance, Transaction, TransactionStatus


class DALError(Exception):
    """
    Общая ошибка взаимодействия с моделями
    """


class NonUniqueEmail(DALError):
    """
    Попытка создания пользователя с уже существующим почтовым адресом
    """


class AttemptModifyResolved(DALError):
    """
    Попытка принять/отклонить уже выполненную транзакцию
    """


class RefundError(DALError):
    """
    Ошибки связанные с возвратом
    """


class AttemptRefundNotResolved(RefundError):
    """
    Попытка выполнить возврат ещё не принятой транзакции
    """


class AttemptRefundRejected(RefundError):
    """
    Попытка выполнить возврат отклонённой транзакции
    """


class AttemptRefundTransfer(RefundError):
    """
    Попытка выполнить возврат отклонённой транзакции
    """


class AttemptRefundRefunded(RefundError):
    """
    Попытка выполнить возврат уже возвращённой транзакции
    """


class UserDAL:
    """
    Data access layer для пользователей
    """
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def make_password_hash(self, password):
        return "hash({})".format(password)

    async def create(
        self, email: str, password: str,
        first_name: t.Optional[str] = None,
        surname: t.Optional[str] = None
    ) -> User:
        """
        Создать пользователя
        """
        new_user = User(
            first_name=first_name, surname=surname,
            email=email, password_hash=self.make_password_hash(password),
        )
        user_balance = Balance(user=new_user)
        self.db_session.add(new_user)
        self.db_session.add(user_balance)
        try:
            await self.db_session.flush()
        except IntegrityError:
            raise NonUniqueEmail()

        return new_user

    def _filter(self, q, user_id, email):
        """
        Отфильтровать выборку по параметрам
        """
        if user_id is None and email is None:
            raise TypeError("one of the parameters must be specified: email user_id")
        if user_id:
            return q.filter(User.id == user_id)
        elif email:
            return q.filter(User.email == email)

    async def get_with_balance(
            self,
            user_id: t.Optional[int] = None,
            email: t.Optional[int] = None,
    ) -> t.List[User]:
        """
        Получить пользователя
        """
        q = await self.db_session.execute(
            self._filter(
                select(User).options(joinedload(User.balance)),
                user_id, email
            )
        )
        return q.unique().scalar()

    async def get_with_transactions(
            self,
            user_id: t.Optional[int] = None,
            email: t.Optional[int] = None,
    ) -> t.List[User]:
        """
        Получить пользователя
        """
        q = await self.db_session.execute(
            self._filter(
                select(User).options(selectinload(User.transactions)),
                user_id, email
            )
        )
        return q.scalar()

    async def get_full(
            self,
            user_id: t.Optional[int] = None,
            email: t.Optional[int] = None,
    ) -> t.List[User]:
        """
        Получить пользователя
        """
        q = await self.db_session.execute(
            self._filter(
                select(User).options(
                    selectinload(User.transactions),
                    selectinload(User.balance)
                ),
                user_id, email
            )
        )
        return q.scalar()


class TransactionDAL:
    """
    Data access layer для транзакций
    """
    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def create_refill(self, user: User, amount: float) -> Transaction:
        """
        Создать пополнение
        """
        new_transaction = Transaction(
            user=user, amount=amount, created_at=datetime.now()
        )

        self.db_session.add(new_transaction)
        await self.db_session.flush()

        return new_transaction

    async def create_transfer(
        self, user_from: User, user_to: User, amount: float
    ) -> Transaction:
        """
        Создать перевод
        """
        new_transaction = Transaction(
            user=user_from, receiver=user_to, amount=amount,
            created_at=datetime.now()
        )

        self.db_session.add(new_transaction)
        await self.db_session.flush()

        return new_transaction

    async def commit(self, transaction: Transaction):
        """
        Подтвердить транзакцию
        """
        if transaction.status is not TransactionStatus.New:
            raise AttemptModifyResolved()
        transaction.status = TransactionStatus.Commited
        transaction.resolved_at = datetime.now()

        # q.execution_options(synchronize_session="fetch", isolation_level="SERIALIZABLE")
        try:
            if transaction.receiver:
                transaction.receiver.balance.amount = Balance.amount + transaction.amount
                transaction.user.balance.amount = Balance.amount - transaction.amount
            else:
                transaction.user.balance.amount = Balance.amount + transaction.amount
            await self.db_session.flush()
        except IntegrityError:
            raise AttemptModifyResolved()

    async def reject(self, transaction: Transaction):
        """
        Подтвердить транзакцию
        """
        if transaction.status is not TransactionStatus.New:
            raise AttemptModifyResolved()
        transaction.status = TransactionStatus.Rejected
        transaction.resolved_at = datetime.now()

        # q.execution_options(synchronize_session="fetch", isolation_level="SERIALIZABLE")
        try:
            await self.db_session.flush()
        except IntegrityError:
            raise AttemptModifyResolved()

    async def refund(self, transaction: Transaction):
        """
        Выполнить возврат

        Запрещено выполнять возврат неподтверждённых и отклонённых
        Запрещено??? выполнять возврат переводов
        """
        wrong_state = {
            TransactionStatus.New: AttemptRefundNotResolved,
            TransactionStatus.Rejected: AttemptRefundRejected
            TransactionStatus.Refunded: AttemptRefundRefunded
        }
        if transaction.status in wrong_state:
            raise wrong_state[transaction.status]

        if transaction.receiver:
            raise AttemptRefundTransfer()

        await self.create_refill(transaction.user, -transaction.amount)


class DAL:
    users: UserDAL
    transactions: TransactionDAL

    def __init__(self, db_session: Session):
        self.users = UserDAL(db_session)
        self.transactions = TransactionDAL(db_session)
