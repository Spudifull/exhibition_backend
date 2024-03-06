import pytest

from pytest import fixture
from fastapi.testclient import TestClient

test_data = {'_id': '615bfd5ce012e2215df19db8',
             'email': 'test@mail.com',
             'identity': 'fsdfsdfq2131'}


@fixture
def client():
    from backend.app.app import app
    application = app
    with TestClient(application) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_get_orders_with_default_value(client):
    response = client.get("/users/615bfd5ce012e2215df19db8", )
    data = response.json()

    assert response.status_code == 200
    assert data["_id"] == test_data["_id"]
    assert data["email"] == test_data["email"]
    assert data["identity"] == test_data["identity"]


@pytest.mark.asyncio
async def test_get_user_by_id(client):
    response = client.get(f"/users/{test_data['_id']}", )
    data = response.json()

    assert response.status_code == 200
    assert data["_id"] == test_data["_id"]
    assert data["email"] == test_data["email"]
    assert data["identity"] == test_data["identity"]


@pytest.mark.asyncio
async def test_get_user_by_id_no_exists(client):
    response = client.get(f"/users/615bfd5ce012e2215df19dba", )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_user_by_email(client):
    response = client.get(f"/users/by_email/{test_data['email']}", )
    data = response.json()

    assert response.status_code == 200
    assert data["_id"] == test_data["_id"]
    assert data["email"] == test_data["email"]
    assert data["identity"] == test_data["identity"]


@pytest.mark.asyncio
async def test_get_user_by_email_no_exists(client):
    response = client.get(f"/users/by_email/test_mail@gmail.com", )

    assert response.status_code == 404
