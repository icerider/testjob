from fastapi import APIRouter, Depends, HTTPException, Query
from schemas import User, UserCreate, Transaction, TransactionRef, UserRef, \
        TransactionDirectCreate, TransactionStatus, TransactionTransferCreate
from db.dal import DAL, NonUniqueEmail, DALError, RefundError, RefundErrorType, \
        TransactionStatus as DALTransactionStatus, AttemptModifyResolved, \
        DataRange
from typing import List, Optional
from db import model
import deps
import logging

log = logging.getLogger("endpoints")

router = APIRouter()


def url_path_for_user(user_id: int) -> str:
    return router.url_path_for(
        'fetch_user', **{
            "user_id": user_id
        }
    )


def url_path_for_transaction(transaction_id: int) -> str:
    return router.url_path_for(
        'fetch_transaction', **{
            "transaction_id": transaction_id
        }
    )


def get_user_ref(user_id: int) -> UserRef:
    return UserRef(
        id=user_id,
        href=url_path_for_user(user_id)
    )


def get_transaction_ref(transaction_id: int) -> TransactionRef:
    return TransactionRef(
        id=transaction_id,
        href=url_path_for_transaction(transaction_id)
    )


def get_transaction_status(transaction_status: DALTransactionStatus) -> TransactionStatus:
    return {
        DALTransactionStatus.New: TransactionStatus.New,
        DALTransactionStatus.Commited: TransactionStatus.Commited,
        DALTransactionStatus.Rejected: TransactionStatus.Rejected
    }.get(transaction_status)


def dbuser_to_user(user: model.User) -> User:
    """
    Преобразовать модель User в schemas.User
    """
    return User(
        id=user.id,
        email=user.email,
        surname=user.surname,
        first_name=user.first_name,
        balance=user.balance.amount,
        href=url_path_for_user(user.id)
    )


def dbtransaction_to_transaction(transaction: model.Transaction) -> Transaction:
    """
    Преобразовать db.Transaction в schemas.Transaction
    """
    out_transaction = Transaction(
        id=transaction.id,
        user=get_user_ref(transaction.user.id),
        amount=transaction.amount,
        status=get_transaction_status(transaction.status),
        href=url_path_for_transaction(transaction.id)
    )
    if transaction.receiver:
        out_transaction.receiver = get_user_ref(transaction.receiver.id)
    if transaction.refunded:
        out_transaction.refunded = get_transaction_ref(transaction.refunded.linked_transaction_id)
    if transaction.refund:
        out_transaction.refund = get_transaction_ref(transaction.refund.transaction_id)
    return out_transaction


@router.post("/user", status_code=201, response_model=User)
async def create_user(
        *, user_in: UserCreate, dal: DAL = Depends(deps.get_db)
) -> dict:
    try:
        user = await dal.users.create(
            email=user_in.email,
            password=user_in.password,
            first_name=user_in.first_name,
            surname=user_in.surname
        )
    except NonUniqueEmail:
        raise HTTPException(409, "Email is already taken")
    return dbuser_to_user(user)


@router.get("/user/{user_id}", status_code=200, response_model=User)
async def fetch_user(*, user_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    user = await dal.users.get_with_balance(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return dbuser_to_user(user)


@router.get("/user/{user_id}/transactions", status_code=200, response_model=List[Transaction])
async def fetch_user_transactions(
    *, user_id: int,
    skip: Optional[int] = Query(0),
    count: Optional[int] = Query(None),
    dal: DAL = Depends(deps.get_db)
) -> List[Transaction]:
    user = await dal.users.get_with_balance(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    transactions = await dal.transactions.getall(user, datarange=DataRange(skip, count))
    return [
        dbtransaction_to_transaction(x) for x in transactions
    ]


@router.post("/transaction/direct", status_code=201, response_model=Transaction)
async def create_direct_trasaction(
        *, transaction_in: TransactionDirectCreate,
        dal: DAL = Depends(deps.get_db)
) -> dict:
    user = await dal.users.get_with_balance(transaction_in.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    try:
        transaction = await dal.transactions.create_refill(user, transaction_in.amount)
    except DALError:
        log.exception()
        raise HTTPException(500, "Failed to create transaction")
    return dbtransaction_to_transaction(transaction)


@router.post("/transaction/transfer", status_code=201, response_model=Transaction)
async def create_transfer_trasaction(
        *, transaction_in: TransactionTransferCreate,
        dal: DAL = Depends(deps.get_db)
) -> dict:
    user = await dal.users.get_with_balance(transaction_in.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    receiver = await dal.users.get_with_balance(transaction_in.receiver_id)
    if receiver is None:
        raise HTTPException(404, "Receiver user not found")
    try:
        transaction = await dal.transactions.create_transfer(
            user, receiver, transaction_in.amount,
        )
    except DALError:
        log.exception()
        raise HTTPException(500, "Failed to create transaction")
    return dbtransaction_to_transaction(transaction)


@router.get("/transaction/{transaction_id}", status_code=200, response_model=Transaction)
async def fetch_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    return dbtransaction_to_transaction(transaction)


@router.post("/transaction/{transaction_id}/commit", status_code=201, response_model=Transaction)
async def commit_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    try:
        await dal.transactions.commit(transaction)
    except AttemptModifyResolved:
        raise HTTPException(409, "Transaction was resolved already")
    return dbtransaction_to_transaction(transaction)


@router.post("/transaction/{transaction_id}/reject", status_code=201, response_model=Transaction)
async def reject_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    try:
        await dal.transactions.reject(transaction)
    except AttemptModifyResolved:
        raise HTTPException(409, "Transaction was resolved already")
    return dbtransaction_to_transaction(transaction)


@router.post("/transaction/{transaction_id}/refund", status_code=201, response_model=Transaction)
async def refund_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    try:
        transaction = await dal.transactions.refund(transaction)
    except RefundError as e:
        err_msg = {
            RefundErrorType.AttemptRefundNotResolved: "Transaction is not resolved",
            RefundErrorType.AttemptRefundRejected: "Transaction is rejected",
            RefundErrorType.AttemptRefundTransfer: "Transaction is transfer",
            RefundErrorType.AttemptRefundRefunded: "Transaction already refunded",
            RefundErrorType.AttemptRefundToRefund: "Transaction is refund"
        }.get(e.err)
        raise HTTPException(409, err_msg)
    return dbtransaction_to_transaction(transaction)
