"""
Вспомогательный модуль для преобразования данных из DAL в Scheme
"""
from fastapi import APIRouter

from db.dal import TransactionStatus as DALTransactionStatus
from db import model
from schemas import (
        User,
        Transaction,
        TransactionRef,
        UserRef,
        TransactionStatus
)


class Helper:
    """
    Объект для выполнения преобразования данных DAL в Schema
    """
    def __init__(self, router: APIRouter):
        self.router = router

    def url_path_for_user(self, user_id: int) -> str:
        """
        Получить url для пользователя по его id
        """
        return self.router.url_path_for(
            'fetch_user', **{
                "user_id": user_id
            }
        )

    def url_path_for_transaction(self, transaction_id: int) -> str:
        """
        Получить url для транзакции по её id
        """
        return self.router.url_path_for(
            'fetch_transaction', **{
                "transaction_id": transaction_id
            }
        )

    def get_user_ref(self, user_id: int) -> UserRef:
        """
        Получить объект ссылки на пользователя
        """
        return UserRef(
            id=user_id,
            href=self.url_path_for_user(user_id)
        )

    def get_transaction_ref(self, transaction_id: int) -> TransactionRef:
        """
        Получить объект ссылки на транзакцию
        """
        return TransactionRef(
            id=transaction_id,
            href=self.url_path_for_transaction(transaction_id)
        )

    def get_transaction_status(self, transaction_status: DALTransactionStatus) -> TransactionStatus:
        """
        Получить статус транзакции
        """
        return {
            DALTransactionStatus.New: TransactionStatus.New,
            DALTransactionStatus.Commited: TransactionStatus.Commited,
            DALTransactionStatus.Rejected: TransactionStatus.Rejected
        }.get(transaction_status)

    def dbuser_to_user(self, user: model.User) -> User:
        """
        Преобразовать модель User в schemas.User
        """
        return User(
            id=user.id,
            email=user.email,
            surname=user.surname,
            first_name=user.first_name,
            balance=user.balance.amount,
            href=self.url_path_for_user(user.id)
        )

    def dbtransaction_to_transaction(self, transaction: model.Transaction) -> Transaction:
        """
        Преобразовать db.Transaction в schemas.Transaction
        """
        out_transaction = Transaction(
            id=transaction.id,
            user=self.get_user_ref(transaction.user.id),
            amount=transaction.amount,
            status=self.get_transaction_status(transaction.status),
            href=self.url_path_for_transaction(transaction.id)
        )
        if transaction.receiver:
            out_transaction.receiver = self.get_user_ref(transaction.receiver.id)
        if transaction.refunded:
            out_transaction.refunded = self.get_transaction_ref(transaction.refunded.linked_transaction_id)
        if transaction.refund:
            out_transaction.refund = self.get_transaction_ref(transaction.refund.transaction_id)
        return out_transaction
