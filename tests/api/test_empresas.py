from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_empresa_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    inserir_empresa = Mock(return_value=True)
    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "inserir_nova_empresa", inserir_empresa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/empresas",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": 100,
            "nome": "Empresa Teste",
            "rep": "Responsável Teste",
        },
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Empresa cadastrada com sucesso."}
    inserir_empresa.assert_called_once_with(
        None, 100, "Empresa Teste", "Responsável Teste"
    )

@pytest.mark.api
def test_consultar_empresa_existente(api_client, monkeypatch):
    empresa = {
        "id": 100,
        "nome": "Empresa Teste",
        "rep": "Responsável Teste",
    }
    obter_empresa = Mock(return_value=empresa)
    monkeypatch.setattr(data_access, "obter_empresa", obter_empresa)

    resposta = api_client.get("/empresas/100")

    assert resposta.status_code == 200
    assert resposta.json() == empresa
    obter_empresa.assert_called_once_with(None, 100)


@pytest.mark.api
def test_consultar_empresa_inexistente(api_client, monkeypatch):
    obter_empresa = Mock(return_value=None)
    monkeypatch.setattr(data_access, "obter_empresa", obter_empresa)

    resposta = api_client.get("/empresas/999")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Empresa 999 não encontrada."}
    obter_empresa.assert_called_once_with(None, 999)

@pytest.mark.api
def test_excluir_empresa_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    empresa = {
        "id": 100,
        "nome": "Empresa Teste",
        "rep": "Responsável Teste",
    }
    obter_empresa = Mock(return_value=empresa)
    deletar_empresa = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_empresa", obter_empresa)
    monkeypatch.setattr(data_access, "deletar_empresa", deletar_empresa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/empresas/100",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_empresa.assert_called_once_with(None, 100)
    deletar_empresa.assert_called_once_with(None, 100)

@pytest.mark.api
def test_excluir_empresa_com_registros_vinculados(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    empresa = {
        "id": 100,
        "nome": "Empresa Teste",
        "rep": "Responsável Teste",
    }
    deletar_empresa = Mock(return_value=False)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(
        data_access, "obter_empresa", Mock(return_value=empresa)
    )
    monkeypatch.setattr(data_access, "deletar_empresa", deletar_empresa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/empresas/100",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 400
    assert resposta.json() == {
        "detail": (
            "Não foi possível remover a empresa. "
            "Verifique se existem registros vinculados."
        )
    }
    deletar_empresa.assert_called_once_with(None, 100)