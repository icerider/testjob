"""
Модели данных
"""

from sqlalchemy import Integer, String, Column, Float, ForeignKey, Enum, Datetime
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

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
    Refused = 2


class Transaction(Base):
    """
    Транзакции
    """
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    status = Column(
        Enum(TransactionStatus),
        nullable=False,
        default=TransactionStatus.New
    )
    created_at = Column(Datetime, nullable=False)
    resolved_at = Column(Datetime)

    user = relationship(
        "User",
        foreign_keys=[user_id],
        overlaps="transactions",
        uselist=False
    )
    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        overlaps="transactions",
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
