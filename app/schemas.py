"""
Схемы обмена данными через HTTP
"""
from typing import Optional
from enum import Enum
from pydantic import BaseModel, EmailStr


class TransactionStatus(Enum):
    New = "new"
    Commited = "commited"
    Rejected = "rejected"


class UserBase(BaseModel):
    first_name: Optional[str]
    surname: Optional[str]
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    balance: float
    href: str

    class Config:
        orm_mode = True


class UserRef(BaseModel):
    id: int
    href: str


class TransactionDirectCreate(BaseModel):
    user_id: int
    amount: float


class TransactionTransferCreate(BaseModel):
    user_id: int
    receiver_id: int
    amount: float


class TransactionRef(BaseModel):
    id: int
    href: str


class Transaction(TransactionRef):
    user: UserRef
    amount: float
    receiver: Optional[UserRef]
    status: TransactionStatus
    refunded: Optional[TransactionRef]
    refund: Optional[TransactionRef]
