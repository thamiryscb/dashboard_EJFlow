
import pytest
from pydantic import ValidationError

from backend.api import (
    Empresa,
    ClienteCreate,
    MembroCreate,
    TarefaCreate,
)


@pytest.mark.unit
def test_empresa_valida():
    empresa = Empresa(
        id=100,
        nome="Empresa Teste",
        rep="Responsavel Teste"
    )

    assert empresa.id == 100
    assert empresa.nome == "Empresa Teste"


@pytest.mark.unit
def test_empresa_nome_vazio():
    with pytest.raises(ValidationError):
        Empresa(
            id=100,
            nome="",
            rep="Responsavel"
        )


@pytest.mark.unit
def test_cliente_email_invalido():
    with pytest.raises(ValidationError):
        ClienteCreate(
            nome="Cliente Teste",
            email="email-invalido",
            id_empresa=1
        )


@pytest.mark.unit
def test_membro_perfil_invalido():
    with pytest.raises(ValidationError):
        MembroCreate(
            id=100,
            id_empresa=1,
            nome="Membro Teste",
            email="membro@example.com",
            cargo="Desenvolvedor",
            perfil="inexistente"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "estado",
    ["nao_iniciada", "em_andamento", "concluida"]
)
def test_tarefa_estado_valido(estado):
    tarefa = TarefaCreate(
        id_projeto=1,
        descricao="Tarefa Teste",
        estado=estado
    )

    assert tarefa.estado == estado


@pytest.mark.unit
def test_tarefa_estado_invalido():
    with pytest.raises(ValidationError):
        TarefaCreate(
            id_projeto=1,
            descricao="Tarefa Teste",
            estado="inexistente"
        )
