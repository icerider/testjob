import typing as t
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm import strategy_options
from sqlalchemy.sql import selectable, or_
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from db.model import User, Balance, Transaction, TransactionStatus, \
        TransactionResolve, TransactionRefund


@dataclass
class DataRange:
    """
    Интервал записей запроса
    """
    offset: int = 0
    count: t.Optional[int] = None


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


class RefundErrorType(Enum):
    # попытка выполнить возврат ещё не принятной транзакции
    AttemptRefundNotResolved = 0
    # попытка выполнить возврат отклонённой транзакции
    AttemptRefundRejected = 1
    # попытка выполнить возврат на перевод
    AttemptRefundTransfer = 2
    # попытка выполнить повторный возврат
    AttemptRefundRefunded = 3
    # попытка выполнить возврат на возврат
    AttemptRefundToRefund = 4


class RefundError(DALError):
    """
    Ошибки связанные с возвратом
    """
    def __init__(self, err: RefundErrorType, message: t.Optional[str] = None):
        self.err = err
        self.message = message

    def __str__(self):
        return f"{self.message} ({self.err})"


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

    def _filter(
            self, q: selectable.Select, user_id, email
    ) -> selectable.Select:
        """
        Отфильтровать выборку по параметрам
        """
        if user_id is None and email is None:
            raise TypeError("one of the parameters must be specified: email user_id")
        if user_id:
            ret = q.filter(User.id == user_id)
            return ret
        elif email:
            return q.filter(User.email == email)

    async def get_with_balance(
            self,
            user_id: t.Optional[int] = None,
            email: t.Optional[int] = None,
    ) -> User:
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
    ) -> User:
        """
        Получить пользователя
        """
        q = await self.db_session.execute(
            self._filter(
                select(User).options(
                    selectinload(User.transactions).options(
                        *TransactionDAL.full_load_transaction()
                    )
                ),
                user_id, email
            )
        )
        return q.scalar()

    async def get_full(
            self,
            user_id: t.Optional[int] = None,
            email: t.Optional[int] = None,
    ) -> User:
        """
        Получить пользователя
        """
        q = await self.db_session.execute(
            self._filter(
                select(User).options(
                    selectinload(
                        User.balance
                    ),
                    selectinload(User.transactions).options(
                        *TransactionDAL.full_load_transaction(),
                    )
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
            user=user, amount=amount, created_at=datetime.now(),
            resolve=None, refund=None, refunded=None
        )

        self.db_session.add(new_transaction)
        try:
            await self.db_session.flush()
        except IntegrityError:
            raise DALError()

        return new_transaction

    async def create_transfer(
            self, user_from: User, user_to: User, amount: float
    ) -> Transaction:
        """
        Создать перевод
        """
        new_transaction = Transaction(
            user=user_from, receiver=user_to, amount=amount,
            resolve=None, refund=None, refunded=None,
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
        transaction.resolve = TransactionResolve(
            transaction=transaction,
            status=TransactionStatus.Commited,
            resolved_at=datetime.now()
        )

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
        transaction.resolve = TransactionResolve(
            transaction=transaction,
            status=TransactionStatus.Rejected,
            resolved_at=datetime.now()
        )

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
            TransactionStatus.New: RefundErrorType.AttemptRefundNotResolved,
            TransactionStatus.Rejected: RefundErrorType.AttemptRefundRejected,
        }
        # попытка возврата на не подтверждённую
        if transaction.status in wrong_state:
            raise RefundError(wrong_state[transaction.status])

        # попытка возврата перевода
        if transaction.receiver:
            raise RefundError(RefundErrorType.AttemptRefundTransfer)

        # попытка повторного возврата
        if transaction.refunded:
            raise RefundError(RefundErrorType.AttemptRefundRefunded)

        # попытка возврата на возврат
        if transaction.refund:
            raise RefundError(RefundErrorType.AttemptRefundToRefund)

        refund_transaction = await self.create_refill(transaction.user, -transaction.amount)
        transaction.refunded = TransactionRefund(
            transaction=transaction,
            linked_transaction=refund_transaction
        )
        refund_transaction.refund = transaction.refunded

        try:
            await self.db_session.flush()
            return refund_transaction
        except IntegrityError:
            raise RefundError(RefundErrorType.AttemptRefundRefunded)

    @classmethod
    def full_load_transaction(self) -> t.Tuple[strategy_options.Load]:
        """
        Полная загрузка аттрибутов транзакции
        """
        return (
            selectinload(Transaction.resolve),
            selectinload(Transaction.refund),
            selectinload(Transaction.refunded)
        )

    def _filter(
            self, q: selectable.Select, user: User = None,
            transaction_id: int = None
    ) -> selectable.Select:
        """
        Отфильтровать выборку по параметрам
        """
        if user:
            return q.filter(or_(
                Transaction.user_id == user.id,
                Transaction.receiver_id == user.id,
            ))
        elif transaction_id:
            return q.filter(Transaction.id == transaction_id)

    def _range(
            self, q: selectable.Select, datarange: DataRange
    ) -> selectable.Select:
        """
        Выдать только запрошенные записи
        """
        if datarange:
            if datarange.offset:
                q = q.offset(datarange.offset)
            if datarange.count:
                q = q.limit(datarange.count)
        return q

    async def get(self, transaction_id: int) -> Transaction:
        """
        Получить транзакцию
        """
        q = await self.db_session.execute(
            self._filter(
                select(Transaction).options(
                    selectinload(Transaction.user).selectinload(User.balance),
                    selectinload(Transaction.receiver).selectinload(User.balance),
                    *self.full_load_transaction()),
                transaction_id=transaction_id
            )
        )
        return q.scalar()

    async def getall(
            self, user: User, datarange: t.Optional[DataRange] = None
    ) -> t.List[Transaction]:
        q = await self.db_session.execute(
            self._range(
                self._filter(
                    select(Transaction).options(*self.full_load_transaction()),
                    user=user
                ),
                datarange
            ).order_by(Transaction.created_at)
        )
        return q.scalars().all()


class DAL:
    users: UserDAL
    transactions: TransactionDAL

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.users = UserDAL(db_session)
        self.transactions = TransactionDAL(db_session)
