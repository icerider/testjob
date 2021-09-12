"""
Модели данных
"""

from sqlalchemy import Integer, String, Column, Float, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
import enum

from db.config import Base


class User(Base):
    """
    Пользователь транзакций
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    # имя пользователя
    first_name = Column(String(256), nullable=True)
    # фамилия
    surname = Column(String(256), nullable=True)
    # почта как уникальный идентификатор
    email = Column(String(120), unique=True, index=True, nullable=False)
    # хэш пароля
    password_hash = Column(String(128))
    # связанные транзакции
    transactions = relationship(
        "Transaction",
        cascade="all,delete-orphan",
        uselist=True,
        primaryjoin="""or_(
            User.id == Transaction.user_id,
            User.id == Transaction.receiver_id
        )"""
    )
    balance = relationship(
        "Balance",
        cascade="all,delete-orphan",
        back_populates="user",
        uselist=False
    )


class TransactionStatus(enum.Enum):
    """
    Статус транзакции
    """
    # новая
    New = 0
    # подтверждённая
    Commited = 1
    # отклонённая
    Rejected = 2
    # возврат
    Refund = 3


class Transaction(Base):
    """
    Транзакции
    """
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # решение по транзакции
    resolve = relationship(
        "TransactionResolve",
        cascade="all,delete-orphan",
        uselist=False
    )

    # содержит refund если на неё осуществляется возврат
    refunded = relationship(
        "TransactionRefund",
        primaryjoin="Transaction.id == TransactionRefund.transaction_id",
        cascade="all,delete-orphan",
        back_populates="transaction",
        uselist=False
    )

    # содержит refund если с помощью неё осуществляется возврат
    refund = relationship(
        "TransactionRefund",
        primaryjoin="Transaction.id == TransactionRefund.linked_transaction_id",
        cascade="all,delete-orphan",
        back_populates="linked_transaction",
        uselist=False
    )

    # статус транзацкии Новая (New), Подтверждённая (Commited), Отклонённная (Rejected)
    @hybrid_property
    def status(self):
        if self.resolve:
            return self.resolve.status
        return TransactionStatus.New

    # пользователь для которого осуществляется транзакция
    user = relationship(
        "User",
        foreign_keys=[user_id],
        overlaps="transactions",
        uselist=False
    )

    # в случае транзакции перевода - получатель
    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        overlaps="transactions",
        uselist=False
    )


class TransactionResolve(Base):
    """
    Решение по транзакциям

    """
    __tablename__ = 'transactions_resolve'

    # транзакция для которой принято решение
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"),
        nullable=False,
        # уникальность transaction_id исключает принятие решения дважды
        unique=True,
        index=True,
        primary_key=True
    )
    # принятое решение
    status = Column(
        Enum(TransactionStatus),
        nullable=False
    )
    # время принятия решения
    resolved_at = Column(DateTime)
    transaction = relationship("Transaction", overlaps="resolve", uselist=False)


class TransactionRefund(Base):
    """
    Возвраты по транзакциям
    """
    __tablename__ = 'transactions_refund'

    transaction_id = Column(
        Integer, ForeignKey("transactions.id"),
        nullable=False, unique=True, index=True,
        primary_key=True
    )
    linked_transaction_id = Column(
        Integer, ForeignKey("transactions.id"),
        nullable=False, unique=True, index=True
    )
    # транзакция, для которой создаётся возврат
    transaction = relationship(
        "Transaction",
        foreign_keys=[transaction_id],
        uselist=False
    )
    # транзакция, с помощью которой осуществляется возврат
    linked_transaction = relationship(
        "Transaction",
        foreign_keys=[linked_transaction_id],
        uselist=False
    )


class Balance(Base):
    """
    Текщий баланс пользователей
    """
    __tablename__ = 'balances'

    # пользователь
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, primary_key=True)
    # баланс
    amount = Column(Float, nullable=False, default=0.0)
    user = relationship("User", back_populates="balance", uselist=False)
