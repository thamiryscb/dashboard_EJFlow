from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_tarefa_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    autenticar = Mock(return_value=admin)
    obter_projeto = Mock(return_value={"id": 10, "id_empresa": 1})
    inserir_tarefa = Mock(return_value=True)

    monkeypatch.setattr(data_access, "autenticar_usuario", autenticar)
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "inserir_nova_tarefa", inserir_tarefa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/tarefas",
        headers={"Authorization": f"Bearer {token}"},
        json={"id_projeto": 10, "descricao": "Revisar o dashboard"},
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Tarefa cadastrada com sucesso."}
    obter_projeto.assert_called_once_with(None, 10)
    inserir_tarefa.assert_called_once_with(
        None,
        10,
        "Revisar o dashboard",
        estado="nao_iniciada",
        id_sprint=None,
        data_cria=None,
        data_fin=None,
        id_membro=None,
    )
@pytest.mark.api
def test_criar_tarefa_com_projeto_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_projeto = Mock(return_value=None)
    inserir_tarefa = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "inserir_nova_tarefa", inserir_tarefa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/tarefas",
        headers={"Authorization": f"Bearer {token}"},
        json={"id_projeto": 999, "descricao": "Revisar o dashboard"},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Projeto 999 não encontrado."}
    obter_projeto.assert_called_once_with(None, 999)
    inserir_tarefa.assert_not_called()

@pytest.mark.api
def test_consultar_tarefa_existente(api_client, monkeypatch):
    tarefa = {
        "id": 42,
        "id_projeto": 10,
        "descricao": "Revisar o dashboard",
        "estado": "nao_iniciada",
    }
    obter_tarefa = Mock(return_value=tarefa)
    monkeypatch.setattr(data_access, "obter_tarefa", obter_tarefa)

    resposta = api_client.get("/tarefas/42")

    assert resposta.status_code == 200
    corpo = resposta.json()
    for campo, valor in tarefa.items():
        assert corpo[campo] == valor
    obter_tarefa.assert_called_once_with(None, 42)


@pytest.mark.api
def test_consultar_tarefa_inexistente(api_client, monkeypatch):
    obter_tarefa = Mock(return_value=None)
    monkeypatch.setattr(data_access, "obter_tarefa", obter_tarefa)

    resposta = api_client.get("/tarefas/999")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Tarefa 999 não encontrada."}
    obter_tarefa.assert_called_once_with(None, 999)

@pytest.mark.api
def test_atualizar_estado_da_tarefa_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_tarefa = Mock(
        return_value={"id": 42, "id_projeto": 10, "estado": "nao_iniciada"}
    )
    obter_projeto = Mock(return_value={"id": 10, "id_empresa": 1})
    atualizar_estado = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_tarefa", obter_tarefa)
    monkeypatch.setattr(data_access, "obter_projeto", obter_projeto)
    monkeypatch.setattr(data_access, "atualizar_estado_tarefa", atualizar_estado)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.patch(
        "/tarefas/42/estado",
        headers={"Authorization": f"Bearer {token}"},
        json={"estado": "em_andamento"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "mensagem": "Estado da tarefa atualizado com sucesso."
    }
    obter_tarefa.assert_called_once_with(None, 42)
    obter_projeto.assert_called_once_with(None, 10)
    atualizar_estado.assert_called_once_with(None, 42, "em_andamento")

@pytest.mark.api
def test_atualizar_tarefa_com_estado_invalido(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    atualizar_estado = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "atualizar_estado_tarefa", atualizar_estado)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.patch(
        "/tarefas/42/estado",
        headers={"Authorization": f"Bearer {token}"},
        json={"estado": "inexistente"},
    )

    assert resposta.status_code == 422
    erros = resposta.json()["detail"]
    assert any(erro["loc"] == ["body", "estado"] for erro in erros)
    atualizar_estado.assert_not_called()

@pytest.mark.api
def test_excluir_tarefa_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_tarefa = Mock(return_value={"id": 42, "id_projeto": 10})
    deletar_tarefa = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_tarefa", obter_tarefa)
    monkeypatch.setattr(data_access, "deletar_tarefa", deletar_tarefa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/tarefas/42",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_tarefa.assert_called_once_with(None, 42)
    deletar_tarefa.assert_called_once_with(None, 42)

@pytest.mark.api
def test_excluir_tarefa_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_tarefa = Mock(return_value=None)
    deletar_tarefa = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_tarefa", obter_tarefa)
    monkeypatch.setattr(data_access, "deletar_tarefa", deletar_tarefa)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/tarefas/999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Tarefa 999 não encontrada."}
    obter_tarefa.assert_called_once_with(None, 999)
    deletar_tarefa.assert_not_called()