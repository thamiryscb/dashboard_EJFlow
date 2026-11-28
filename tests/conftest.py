import pytest
import mysql.connector
from fastapi.testclient import TestClient

from backend.api import app, get_db


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: None)
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()

@pytest.fixture
def db_test():
    conexao = mysql.connector.connect(
        host="127.0.0.1",
        port=3307,
        user="ejflow_test",
        password="ejflow_test",
        database="ejflow_test",
        connection_timeout=5,
    )
    try:
        yield conexao
    finally:
        conexao.close()