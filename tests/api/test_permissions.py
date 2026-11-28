import pytest

from backend import data_access


@pytest.mark.api
@pytest.mark.auth
def test_listar_admins_sem_token_retorna_401(api_client):
    resposta = api_client.get("/admins")

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "Autenticação obrigatória."}


@pytest.mark.api
@pytest.mark.auth
@pytest.mark.parametrize(
    ("perfil", "status_esperado"),
    [("admin", 200), ("membro", 403)],
)
def test_listar_admins_por_perfil(
    api_client, monkeypatch, perfil, status_esperado
):
    usuario = {
        "id": 1,
        "nome": "Usuário Teste",
        "email": "usuario@example.com",
        "tipo": perfil,
    }
    admins = [{"id": 2, "nome": "Admin Teste", "email": "admin@example.com"}]

    monkeypatch.setattr(
        data_access, "autenticar_usuario", lambda _db, _email, _senha: usuario
    )
    listar_admins = []

    def listar_admins_fake(_db):
        listar_admins.append(True)
        return admins

    monkeypatch.setattr(data_access, "listar_admins", listar_admins_fake)

    login = api_client.post(
        "/auth/login",
        json={"email": usuario["email"], "senha": "senha-de-teste"},
    )
    assert login.status_code == 200

    token = login.json()["token"]
    resposta = api_client.get(
        "/admins", headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == status_esperado
    if perfil == "admin":
        assert resposta.json() == admins
        assert listar_admins == [True]
    else:
        assert resposta.json() == {
            "detail": "Permissão insuficiente para esta operação."
        }
        assert listar_admins == []
