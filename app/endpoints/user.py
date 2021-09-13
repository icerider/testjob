"""
Endpoints для управления пользователями
"""

from fastapi import Depends, HTTPException, Query
from typing import List, Optional

from schemas import User, UserCreate, Transaction
from db.dal import DAL, NonUniqueEmail, DataRange
import deps
from .router import router, helper


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
    return helper.dbuser_to_user(user)


@router.get("/user/{user_id}", status_code=200, response_model=User)
async def fetch_user(*, user_id: int, dal: DAL = Depends(deps.get_db)) -> dict:
    user = await dal.users.get_with_balance(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return helper.dbuser_to_user(user)


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
        helper.dbtransaction_to_transaction(x) for x in transactions
    ]
