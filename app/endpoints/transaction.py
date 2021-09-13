"""
Endpoints для управления транзакциями
"""

from fastapi import Depends, HTTPException
import logging

import deps
from .router import router, helper
from schemas import (
        Transaction,
        TransactionDirectCreate,
        TransactionTransferCreate
)
from db.dal import (
        DAL,
        DALError,
        RefundError,
        RefundErrorType,
        AttemptModifyResolved
)

log = logging.getLogger("endpoints.transaction")


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
    return helper.dbtransaction_to_transaction(transaction)


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
    return helper.dbtransaction_to_transaction(transaction)


@router.get("/transaction/{transaction_id}", status_code=200, response_model=Transaction)
async def fetch_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    return helper.dbtransaction_to_transaction(transaction)


@router.post("/transaction/{transaction_id}/commit", status_code=201, response_model=Transaction)
async def commit_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    try:
        await dal.transactions.commit(transaction)
    except AttemptModifyResolved:
        raise HTTPException(409, "Transaction was resolved already")
    return helper.dbtransaction_to_transaction(transaction)


@router.post("/transaction/{transaction_id}/reject", status_code=201, response_model=Transaction)
async def reject_transaction(*, transaction_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    transaction = await dal.transactions.get(transaction_id)
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    try:
        await dal.transactions.reject(transaction)
    except AttemptModifyResolved:
        raise HTTPException(409, "Transaction was resolved already")
    return helper.dbtransaction_to_transaction(transaction)


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
    return helper.dbtransaction_to_transaction(transaction)
