from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_sprint_aberta_por_padrao(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_projeto = Mock(return_value={"id": 10, "id_empresa": 100})
    inserir_sprint = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "inserir_nova_sprint", inserir_sprint)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/sprints",
        headers={"Authorization": f"Bearer {token}"},
        json={"id_projeto": 10},
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Sprint cadastrada com sucesso."}
    obter_projeto.assert_called_once_with(None, 10)
    inserir_sprint.assert_called_once_with(None, 10, 0, None, None)

@pytest.mark.api
def test_criar_sprint_com_projeto_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_projeto = Mock(return_value=None)
    inserir_sprint = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "inserir_nova_sprint", inserir_sprint)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/sprints",
        headers={"Authorization": f"Bearer {token}"},
        json={"id_projeto": 999},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Projeto 999 não encontrado."}
    obter_projeto.assert_called_once_with(None, 999)
    inserir_sprint.assert_not_called()

@pytest.mark.api
def test_consultar_sprints_por_projeto(api_client, monkeypatch):
    sprint = {
        "id": 42,
        "id_projeto": 10,
        "isDone": False,
        "data_in": None,
        "data_fin": None,
    }
    listar_sprints = Mock(return_value=[sprint])
    monkeypatch.setattr(data_access, "listar_sprints", listar_sprints)

    resposta = api_client.get("/sprints/10")

    assert resposta.status_code == 200
    assert resposta.json() == [sprint]
    listar_sprints.assert_called_once_with(None, id_projeto=10)

@pytest.mark.api
def test_consultar_projeto_sem_sprints(api_client, monkeypatch):
    listar_sprints = Mock(return_value=[])
    monkeypatch.setattr(data_access, "listar_sprints", listar_sprints)

    resposta = api_client.get("/sprints/10")

    assert resposta.status_code == 200
    assert resposta.json() == []
    listar_sprints.assert_called_once_with(None, id_projeto=10)

@pytest.mark.api
def test_excluir_sprint_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_sprint = Mock(return_value={"id": 42, "id_projeto": 10})
    deletar_sprint = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_sprint", obter_sprint)
    monkeypatch.setattr(data_access, "deletar_sprint", deletar_sprint)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/sprints/42",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_sprint.assert_called_once_with(None, 42)
    deletar_sprint.assert_called_once_with(None, 42)

@pytest.mark.api
def test_excluir_sprint_com_tarefas_vinculadas(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_sprint = Mock(return_value={"id": 42, "id_projeto": 10})
    deletar_sprint = Mock(return_value=False)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_sprint", obter_sprint)
    monkeypatch.setattr(data_access, "deletar_sprint", deletar_sprint)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/sprints/42",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 400
    assert resposta.json() == {
        "detail": (
            "Não foi possível remover a sprint. "
            "Verifique se existem tarefas vinculadas."
        )
    }
    obter_sprint.assert_called_once_with(None, 42)
    deletar_sprint.assert_called_once_with(None, 42)