import pytest

from backend import data_access


@pytest.mark.api
@pytest.mark.auth
@pytest.mark.parametrize(
    ("senha", "status_esperado"),
    [("senha-de-teste", 200), ("senha-errada", 401)],
    ids=["credenciais-validas", "senha-incorreta"],
)
def test_login(api_client, monkeypatch, senha, status_esperado):
    usuario = {
        "id": 1,
        "nome": "Admin Teste",
        "email": "admin@example.com",
        "tipo": "admin",
    }

    def autenticar_usuario_fake(_db, email, senha_recebida):
        if (email, senha_recebida) == (usuario["email"], "senha-de-teste"):
            return usuario
        return None

    monkeypatch.setattr(data_access, "autenticar_usuario", autenticar_usuario_fake)

    resposta = api_client.post(
        "/auth/login",
        json={"email": usuario["email"], "senha": senha},
    )

    assert resposta.status_code == status_esperado
    corpo = resposta.json()

    if status_esperado == 200:
        assert corpo["email"] == usuario["email"]
        assert corpo["tipo"] == "admin"
        assert isinstance(corpo["token"], str)
        assert corpo["token"]
        assert "senha" not in corpo
    else:
        assert corpo == {"detail": "E-mail ou senha inválidos."}