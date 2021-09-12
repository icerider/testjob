import pytest
from fastapi.testclient import TestClient
from db.config import engine, Base, async_session

from main import app
client = TestClient(app)


@pytest.fixture
async def prepare_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
def test_create_user(prepare_db):
    response = client.post(
        "/user",
        json={
            "email": "test@example.org",
            "password": "secret",
            "first_name": "Username",
            "surname": "User surname",
        }
    )
    assert response.status_code == 201, response.content
    assert response.json() == {
            "id": 1,
            "balance": 0.0,
            "email": "test@example.org",
            "first_name": "Username",
            "surname": "User surname",
            "href": "/user/1"
    }


def create_user1():
    return client.post(
        "/user",
        json={
            "email": "test@example.org",
            "password": "secret",
            "first_name": "Username",
            "surname": "User surname",
        }
    )


def create_user2():
    return client.post(
        "/user",
        json={
            "email": "test2@example.org",
            "password": "secret",
        }
    )


def create_direct_transaction(user, amount):
    return client.post(
        "/transaction/direct",
        json={
            "user_id": user["id"],
            "amount": amount
        }
    )

def create_transfer_transaction(user_from, user_to, amount):
    return client.post(
        "/transaction/transfer",
        json={
            "user_id": user_from["id"],
            "receiver_id": user_to["id"],
            "amount": amount
        }
    )


@pytest.mark.asyncio
def test_create_user_exists_email(prepare_db):
    response = create_user1()
    assert response.status_code == 201
    response = create_user1()
    assert response.status_code == 409


@pytest.mark.asyncio
def test_fetch_user(prepare_db):
    user1 = create_user1().json()
    user2 = create_user2().json()
    response = client.get(user1["href"])
    assert response.status_code == 200, response.content
    assert response.json() == {
            "id": 1,
            "balance": 0.0,
            "email": "test@example.org",
            "first_name": "Username",
            "surname": "User surname",
            "href": "/user/1"
    }
    response = client.get(user2["href"])
    assert response.status_code == 200, response.content
    assert response.json() == {
            "id": 2,
            "balance": 0.0,
            "email": "test2@example.org",
            "first_name": None,
            "surname": None,
            "href": "/user/2"
    }


@pytest.mark.asyncio
def test_fetch_user_not_found(prepare_db):
    response = client.get("/user/5")
    assert response.status_code == 404, response.content


@pytest.mark.asyncio
def test_create_direct_transaction(prepare_db):
    user1 = create_user1().json()

    response = client.post(
        "/transaction/direct",
        json={
            "user_id": user1["id"],
            "amount": 50.0
        }
    )
    assert response.status_code == 201, response.content
    assert response.json() == {
        'amount': 50.0,
        'href': '/transaction/1',
        'id': 1,
        'receiver': None,
        'refund': None,
        'refunded': None,
        'status': 'new',
        'user': {
            'href': '/user/1',
            'id': 1
        }
    }


@pytest.mark.asyncio
def test_create_transfer_transaction(prepare_db):
    user1 = create_user1().json()
    user2 = create_user2().json()

    response = client.post(
        "/transaction/transfer",
        json={
            "user_id": user1["id"],
            "receiver_id": user2["id"],
            "amount": 60.0
        }
    )
    assert response.status_code == 201, response.content
    assert response.json() == {
        'amount': 60.0,
        'href': '/transaction/1',
        'id': 1,
        'receiver': {
            'href': '/user/2',
            'id': 2
        },
        'refund': None,
        'refunded': None,
        'status': 'new',
        'user': {
            'href': '/user/1',
            'id': 1
        }
    }


@pytest.mark.asyncio
def test_commit_transaction(prepare_db):
    user1 = create_user1().json()

    transaction1 = create_direct_transaction(user1, 50.0).json()
    response = client.post(f'{transaction1["href"]}/commit')
    assert response.status_code == 201
    assert response.json() == {
        'amount': 50.0,
        'href': '/transaction/1',
        'id': 1,
        'receiver': None,
        'refund': None,
        'refunded': None,
        'status': 'commited',
        'user': {'href': '/user/1', 'id': 1}
    }


@pytest.mark.asyncio
def test_reject_transaction(prepare_db):
    user1 = create_user1().json()

    transaction1 = create_direct_transaction(user1, 50.0).json()
    response = client.post(f'{transaction1["href"]}/reject')
    assert response.status_code == 201
    assert response.json() == {
        'amount': 50.0,
        'href': '/transaction/1',
        'id': 1,
        'receiver': None,
        'refund': None,
        'refunded': None,
        'status': 'rejected',
        'user': {'href': '/user/1', 'id': 1}
    }


@pytest.mark.asyncio
def test_refund_transaction(prepare_db):
    user1 = create_user1().json()
    transaction1 = create_direct_transaction(user1, 50.0).json()
    client.post(f'{transaction1["href"]}/commit')
    response = client.post(f'{transaction1["href"]}/refund')
    assert response.status_code == 201
    assert response.json() == {
        'amount': -50.0,
        'href': '/transaction/2',
        'id': 2,
        'receiver': None,
        'refund': {"href": '/transaction/1', 'id': 1},
        'refunded': None,
        'status': 'new',
        'user': {'href': '/user/1', 'id': 1}
    }


@pytest.mark.asyncio
def test_errors_refund_transaction(prepare_db):
    user1 = create_user1().json()
    user2 = create_user2().json()
    transaction1 = create_direct_transaction(user1, 50.0).json()

    # проверка refund новой транзакции
    response = client.post(f'{transaction1["href"]}/refund')
    assert response.status_code == 409
    assert "not resolved" in response.json()["detail"]

    # проверка refund отклонённой транзакции
    client.post(f'{transaction1["href"]}/reject')
    response = client.post(f'{transaction1["href"]}/refund')
    assert response.status_code == 409
    assert "rejected" in response.json()["detail"]

    # проверка refund перевода
    transaction2 = create_transfer_transaction(user1, user2, 50.0).json()
    client.post(f'{transaction2["href"]}/commit')
    response = client.post(f'{transaction2["href"]}/refund')
    assert response.status_code == 409
    assert "transfer" in response.json()["detail"]

    # проверка повторного refund
    transaction3 = create_direct_transaction(user1, 50.0).json()
    response = client.post(f'{transaction3["href"]}/commit')
    assert response.status_code == 201
    response = client.post(f'{transaction3["href"]}/refund')
    assert response.status_code == 201
    transaction4 = response.json()
    response = client.post(f'{transaction3["href"]}/refund')
    assert response.status_code == 409
    assert "refunded" in response.json()["detail"]

    # проверка refund на refund
    response = client.post(f'{transaction4["href"]}/commit')
    assert response.status_code == 201
    response = client.post(f'{transaction4["href"]}/refund')
    assert response.status_code == 409
    assert "is refund" in response.json()["detail"]


@pytest.mark.asyncio
def test_fetch_user_transactions(prepare_db):
    user1 = create_user1().json()
    transaction1 = create_direct_transaction(user1, 10.0).json()
    transaction2 = create_direct_transaction(user1, 20.0).json()
    transaction3 = create_direct_transaction(user1, 30.1).json()
    client.post(f'{transaction1["href"]}/commit')
    client.post(f'{transaction2["href"]}/reject')
    response = client.get(f'{user1["href"]}/transactions')
    assert response.status_code == 200
    assert response.json() == [
        {
            'amount': 10.0,
            'href': '/transaction/1',
            'id': 1,
            'receiver': None,
            'refund': None,
            'refunded': None,
            'status': 'commited',
            'user': {'href': '/user/1', 'id': 1}
        },
        {
            'amount': 20.0,
            'href': '/transaction/2',
            'id': 2,
            'receiver': None,
            'refund': None,
            'refunded': None,
            'status': 'rejected',
            'user': {'href': '/user/1', 'id': 1}
        },
        {
            'amount': 30.1,
            'href': '/transaction/3',
            'id': 3,
            'receiver': None,
            'refund': None,
            'refunded': None,
            'status': 'new',
            'user': {'href': '/user/1', 'id': 1}
        }
    ]
