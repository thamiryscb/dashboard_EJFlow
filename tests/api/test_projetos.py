from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_projeto_com_cliente_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    inserir_projeto = Mock(return_value=True)
    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "inserir_novo_projeto", inserir_projeto)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/projetos",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": 10,
            "id_empresa": 100,
            "nome": "Projeto Teste",
            "descricao": "Revisar o dashboard",
            "id_cliente": 42,
        },
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Projeto cadastrado com sucesso."}
    inserir_projeto.assert_called_once_with(
        None, 10, 100, "Projeto Teste", "Revisar o dashboard", 42
    )

@pytest.mark.api
@pytest.mark.auth
def test_chefe_nao_pode_criar_projeto_em_outra_empresa(api_client, monkeypatch):
    chefe = {
        "id": 2,
        "nome": "Chefe Teste",
        "email": "chefe@example.com",
        "tipo": "chefe",
        "id_empresa": 100,
    }
    inserir_projeto = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=chefe)
    )
    monkeypatch.setattr(data_access, "inserir_novo_projeto", inserir_projeto)

    login = api_client.post(
        "/auth/login",
        json={"email": chefe["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/projetos",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": 10,
            "id_empresa": 200,
            "nome": "Projeto Teste",
            "descricao": "Revisar o dashboard",
        },
    )

    assert resposta.status_code == 403
    assert resposta.json() == {
        "detail": "O perfil chefe só pode gerenciar recursos da própria empresa."
    }
    inserir_projeto.assert_not_called()

@pytest.mark.api
def test_consultar_projeto_com_clientes(api_client, monkeypatch):
    projeto = {
        "id": 10,
        "id_empresa": 100,
        "nome": "Projeto Teste",
        "descricao": "Revisar o dashboard",
    }
    obter_projeto = Mock(return_value=projeto)
    listar_demandas = Mock(return_value=[
        {"id_projeto": 10, "id_cliente": 42},
        {"id_projeto": 10, "id_cliente": 43},
    ])
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "listar_demandas", listar_demandas)

    resposta = api_client.get("/projeto/10")

    assert resposta.status_code == 200
    assert resposta.json() == {**projeto, "clientes": [42, 43]}
    obter_projeto.assert_called_once_with(None, 10)
    listar_demandas.assert_called_once_with(None, id_projeto=10)


@pytest.mark.api
def test_consultar_projeto_inexistente(api_client, monkeypatch):
    obter_projeto = Mock(return_value=None)
    listar_demandas = Mock()
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "listar_demandas", listar_demandas)

    resposta = api_client.get("/projeto/999")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Projeto 999 não encontrado."}
    obter_projeto.assert_called_once_with(None, 999)
    listar_demandas.assert_not_called()

@pytest.mark.api
def test_excluir_projeto_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_projeto = Mock(return_value={"id": 10, "id_empresa": 100})
    deletar_projeto = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "deletar_projeto", deletar_projeto)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/projetos/10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_projeto.assert_called_once_with(None, 10)
    deletar_projeto.assert_called_once_with(None, 10)

@pytest.mark.api
def test_excluir_projeto_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_projeto = Mock(return_value=None)
    deletar_projeto = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "deletar_projeto", deletar_projeto)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/projetos/999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Projeto 999 não encontrado."}
    obter_projeto.assert_called_once_with(None, 999)
    deletar_projeto.assert_not_called()

