"""
Схемы обмена данными
"""

from typing import Optional
from enum import Enum
from pydantic import BaseModel, EmailStr


class TransactionStatus(Enum):
    """
    Статус транзакции
    """
    New = "new"
    Commited = "commited"
    Rejected = "rejected"


class UserBase(BaseModel):
    """
    Базовый параметры пользователя
    """
    first_name: Optional[str]
    surname: Optional[str]
    email: EmailStr


class UserCreate(UserBase):
    """
    Объект для создания пользователя
    """
    password: str


class User(UserBase):
    """
    Возвращаемый объект пользователя
    """
    id: int
    balance: float
    href: str

    class Config:
        orm_mode = True


class UserRef(BaseModel):
    """
    Ссылка на пользователя
    """
    # id в базе
    id: int
    # ссылка для получения информации о пользователе
    href: str


class TransactionDirectCreate(BaseModel):
    """
    Объект для создания прямой транзакции
    """
    user_id: int
    amount: float


class TransactionTransferCreate(BaseModel):
    """
    Объект для создания транзакции перевода
    """
    user_id: int
    receiver_id: int
    amount: float


class TransactionRef(BaseModel):
    """
    Ссылка на транзакцию
    """
    id: int
    href: str


class Transaction(TransactionRef):
    """
    Возвращаемый объект транзакции
    """
    user: UserRef
    amount: float
    receiver: Optional[UserRef]
    status: TransactionStatus
    refunded: Optional[TransactionRef]
    refund: Optional[TransactionRef]
