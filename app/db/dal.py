import typing as t
from sqlalchemy.exc import IntegrityError
# from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime

from db.model import User, Balance, Transaction


class UserDALError(Exception):
    pass


class NonUniqueEmail(UserDALError):
    pass


class UserDAL:
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
        return q.unique().scalar()


class TransactionDAL:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def create_refill(self, user: User, amount: float) -> Transaction:
        new_transaction = Transaction(
            user=user, amount=amount, created_at=datetime.now()
        )

        self.db_session.add(new_transaction)
        await self.db_session.flush()

        return new_transaction


class DAL:
    users: UserDAL
    transactions: TransactionDAL

    def __init__(self, db_session: Session):
        self.users = UserDAL(db_session)
        self.transactions = TransactionDAL(db_session)
