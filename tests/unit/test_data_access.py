
import pytest

from backend.data_access import validate_name


@pytest.mark.unit
@pytest.mark.parametrize(
    "nome",
    ["empresas", "clientes", "meu_banco", "projeto_123", "_teste"]
)
def test_validate_name_valido(nome):
    assert validate_name(nome) == f"`{nome}`"


@pytest.mark.unit
@pytest.mark.parametrize(
    "nome",
    ["", "123empresa", "nome invalido", "nome-tabela", "nome;"]
)
def test_validate_name_invalido(nome):
    with pytest.raises(ValueError):
        validate_name(nome)
