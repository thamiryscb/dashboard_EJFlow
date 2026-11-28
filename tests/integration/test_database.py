from uuid import uuid4

import pytest
from mysql.connector import IntegrityError, errorcode


@pytest.mark.integration
def test_mysql_de_testes_tem_schema_e_tabelas(db_test):
    with db_test.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        assert cursor.fetchone() == ("ejflow_test",)

        cursor.execute("SHOW TABLES")
        tabelas = {nome for (nome,) in cursor.fetchall()}

    assert {"empresas", "projetos", "sprints", "tarefas"} <= tabelas


@pytest.mark.integration
def test_mysql_rejeita_email_duplicado_de_cliente(db_test):
    try:
        with db_test.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            assert cursor.fetchone() == ("ejflow_test",)

            cursor.execute("SELECT id FROM empresas ORDER BY id LIMIT 1")
            empresa = cursor.fetchone()
            assert empresa is not None, "O banco de testes precisa ter uma empresa de exemplo."

            empresa_id = empresa[0]
            email = f"cliente-{uuid4().hex}@example.com"
            inserir_cliente = (
                "INSERT INTO clientes (nome, email, id_empresa) VALUES (%s, %s, %s)"
            )

            cursor.execute(inserir_cliente, ("Primeiro Cliente", email, empresa_id))
            assert cursor.rowcount == 1

            with pytest.raises(IntegrityError) as erro:
                cursor.execute(
                    inserir_cliente, ("Segundo Cliente", email, empresa_id)
                )

            assert erro.value.errno == errorcode.ER_DUP_ENTRY
    finally:
        db_test.rollback()
