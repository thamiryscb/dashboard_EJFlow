from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_cliente_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    inserir_cliente = Mock(return_value=True)
    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "inserir_novo_cliente", inserir_cliente)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/clientes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nome": "Cliente Teste",
            "email": "cliente@example.com",
            "id_empresa": 100,
        },
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Cliente cadastrado com sucesso."}
    inserir_cliente.assert_called_once_with(
        None, "Cliente Teste", "cliente@example.com", 100
    )

@pytest.mark.api
def test_criar_cliente_com_email_invalido(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    inserir_cliente = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "inserir_novo_cliente", inserir_cliente)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/clientes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nome": "Cliente Teste",
            "email": "email-invalido",
            "id_empresa": 100,
        },
    )

    assert resposta.status_code == 422
    erros = resposta.json()["detail"]
    assert any(erro["loc"] == ["body", "email"] for erro in erros)
    inserir_cliente.assert_not_called()

@pytest.mark.api
def test_consultar_cliente_existente(api_client, monkeypatch):
    cliente = {
        "id": 42,
        "nome": "Cliente Teste",
        "email": "cliente@example.com",
        "id_empresa": 100,
    }
    obter_cliente = Mock(return_value=cliente)
    monkeypatch.setattr(data_access, "obter_cliente", obter_cliente)

    resposta = api_client.get("/cliente/42")

    assert resposta.status_code == 200
    assert resposta.json() == cliente
    obter_cliente.assert_called_once_with(None, 42)


@pytest.mark.api
def test_consultar_cliente_inexistente(api_client, monkeypatch):
    obter_cliente = Mock(return_value=None)
    monkeypatch.setattr(data_access, "obter_cliente", obter_cliente)

    resposta = api_client.get("/cliente/999")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Cliente 999 não encontrado."}
    obter_cliente.assert_called_once_with(None, 999)

@pytest.mark.api
def test_excluir_cliente_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_cliente = Mock(return_value={
        "id": 42,
        "nome": "Cliente Teste",
        "email": "cliente@example.com",
        "id_empresa": 100,
    })
    deletar_cliente = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_cliente", obter_cliente)
    monkeypatch.setattr(data_access, "deletar_cliente", deletar_cliente)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/clientes/42",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_cliente.assert_called_once_with(None, 42)
    deletar_cliente.assert_called_once_with(None, 42)

@pytest.mark.api
def test_excluir_cliente_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_cliente = Mock(return_value=None)
    deletar_cliente = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_cliente", obter_cliente)
    monkeypatch.setattr(data_access, "deletar_cliente", deletar_cliente)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/clientes/999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Cliente 999 não encontrado."}
    obter_cliente.assert_called_once_with(None, 999)
    deletar_cliente.assert_not_called()