from unittest.mock import Mock

import pytest

from backend import data_access


@pytest.mark.api
def test_criar_membro_com_perfil_padrao(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    inserir_membro = Mock(return_value=True)
    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "inserir_novo_membro", inserir_membro)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/membros",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": 42,
            "id_empresa": 100,
            "nome": "Membro Teste",
            "email": "membro@example.com",
            "cargo": "Desenvolvedor",
        },
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"mensagem": "Membro cadastrado com sucesso."}
    inserir_membro.assert_called_once_with(
        None,
        42,
        100,
        "Membro Teste",
        "membro@example.com",
        "Desenvolvedor",
        perfil="membro",
        senha=None,
    )

@pytest.mark.api
@pytest.mark.auth
def test_chefe_nao_pode_cadastrar_outro_chefe(api_client, monkeypatch):
    chefe = {
        "id": 2,
        "nome": "Chefe Teste",
        "email": "chefe@example.com",
        "tipo": "chefe",
        "id_empresa": 100,
    }
    inserir_membro = Mock()
    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=chefe)
    )
    monkeypatch.setattr(data_access, "inserir_novo_membro", inserir_membro)

    login = api_client.post(
        "/auth/login",
        json={"email": chefe["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.post(
        "/membros",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "id": 42,
            "id_empresa": 100,
            "nome": "Novo Chefe",
            "email": "novo.chefe@example.com",
            "cargo": "Coordenador",
            "perfil": "chefe",
        },
    )

    assert resposta.status_code == 403
    assert resposta.json() == {
        "detail": "O chefe só pode cadastrar colaboradores com perfil membro."
    }
    inserir_membro.assert_not_called()


@pytest.mark.api
def test_consultar_membro_existente(api_client, monkeypatch):
    membro = {
        "id": 42,
        "id_empresa": 100,
        "nome": "Membro Teste",
        "email": "membro@example.com",
        "cargo": "Desenvolvedor",
        "perfil": "membro",
    }
    obter_membro = Mock(return_value=membro)
    monkeypatch.setattr(data_access, "obter_membro", obter_membro)

    resposta = api_client.get("/membros/42")

    assert resposta.status_code == 200
    assert resposta.json() == membro
    obter_membro.assert_called_once_with(None, 42)


@pytest.mark.api
def test_consultar_membro_inexistente(api_client, monkeypatch):
    obter_membro = Mock(return_value=None)
    monkeypatch.setattr(data_access, "obter_membro", obter_membro)

    resposta = api_client.get("/membros/999")

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Membro 999 não encontrado."}
    obter_membro.assert_called_once_with(None, 999)  

@pytest.mark.api
def test_atualizar_perfil_de_membro_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_membro = Mock(return_value={"id": 42, "perfil": "membro"})
    atualizar_perfil = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_membro", obter_membro)
    monkeypatch.setattr(data_access, "atualizar_perfil_membro", atualizar_perfil)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.patch(
        "/membros/42/perfil",
        headers={"Authorization": f"Bearer {token}"},
        json={"perfil": "chefe"},
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "mensagem": "Perfil do membro atualizado com sucesso."
    }
    obter_membro.assert_called_once_with(None, 42)
    atualizar_perfil.assert_called_once_with(None, 42, "chefe")

@pytest.mark.api
def test_excluir_membro_como_admin(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_membro = Mock(return_value={"id": 42})
    deletar_membro = Mock(return_value=True)

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_membro", obter_membro)
    monkeypatch.setattr(data_access, "deletar_membro", deletar_membro)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/membros/42",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 204
    assert resposta.content == b""
    obter_membro.assert_called_once_with(None, 42)
    deletar_membro.assert_called_once_with(None, 42)
@pytest.mark.api
def test_excluir_membro_inexistente(api_client, monkeypatch):
    admin = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }
    obter_membro = Mock(return_value=None)
    deletar_membro = Mock()

    monkeypatch.setattr(
        data_access, "autenticar_usuario", Mock(return_value=admin)
    )
    monkeypatch.setattr(data_access, "obter_membro", obter_membro)
    monkeypatch.setattr(data_access, "deletar_membro", deletar_membro)

    login = api_client.post(
        "/auth/login",
        json={"email": admin["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200
    token = login.json()["token"]

    resposta = api_client.delete(
        "/membros/999",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Membro 999 não encontrado."}
    obter_membro.assert_called_once_with(None, 999)
    deletar_membro.assert_not_called()