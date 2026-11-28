import pytest
from mysql.connector import IntegrityError, errorcode


@pytest.mark.integration
def test_mysql_impede_excluir_sprint_com_tarefa(db_test):
    try:
        with db_test.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            assert cursor.fetchone() == ("ejflow_test",)

            cursor.execute("SELECT id FROM projetos ORDER BY id LIMIT 1")
            projeto = cursor.fetchone()
            assert projeto is not None, "O banco de testes precisa ter um projeto de exemplo."
            projeto_id = projeto[0]

            cursor.execute(
                "INSERT INTO sprints (id_projeto) VALUES (%s)",
                (projeto_id,),
            )
            sprint_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO tarefas (id_projeto, id_sprint, descricao) "
                "VALUES (%s, %s, %s)",
                (projeto_id, sprint_id, "Tarefa de teste de integração"),
            )

            with pytest.raises(IntegrityError) as erro:
                cursor.execute(
                    "DELETE FROM sprints WHERE id = %s",
                    (sprint_id,),
                )

            assert erro.value.errno == errorcode.ER_ROW_IS_REFERENCED_2
    finally:
        db_test.rollback()

@pytest.mark.integration
def test_mysql_preserva_tarefa_ao_excluir_membro(db_test):
    try:
        with db_test.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            assert cursor.fetchone() == ("ejflow_test",)

            cursor.execute(
                "SELECT id, id_empresa FROM projetos ORDER BY id LIMIT 1"
            )
            projeto = cursor.fetchone()
            assert projeto is not None, "O banco de testes precisa ter um projeto de exemplo."
            projeto_id, empresa_id = projeto

            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM membros")
            membro_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO membros (id, id_empresa, nome, email, cargo) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    membro_id,
                    empresa_id,
                    "Membro de Teste",
                    f"membro-{membro_id}@example.com",
                    "Desenvolvedor",
                ),
            )

            cursor.execute(
                "INSERT INTO tarefas (id_projeto, id_membro, descricao) "
                "VALUES (%s, %s, %s)",
                (projeto_id, membro_id, "Tarefa vinculada ao membro de teste"),
            )
            tarefa_id = cursor.lastrowid

            cursor.execute("DELETE FROM membros WHERE id = %s", (membro_id,))
            assert cursor.rowcount == 1

            cursor.execute(
                "SELECT id, id_membro FROM tarefas WHERE id = %s",
                (tarefa_id,),
            )
            assert cursor.fetchone() == (tarefa_id, None)
    finally:
        db_test.rollback()

@pytest.mark.integration
def test_mysql_remove_vinculo_ao_excluir_membro(db_test):
    try:
        with db_test.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            assert cursor.fetchone() == ("ejflow_test",)

            cursor.execute(
                "SELECT id, id_empresa FROM projetos ORDER BY id LIMIT 1"
            )
            projeto = cursor.fetchone()
            assert projeto is not None, "O banco de testes precisa ter um projeto de exemplo."
            projeto_id, empresa_id = projeto

            cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM membros")
            membro_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO membros (id, id_empresa, nome, email, cargo) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    membro_id,
                    empresa_id,
                    "Membro de Teste",
                    f"membro-{membro_id}@example.com",
                    "Desenvolvedor",
                ),
            )

            cursor.execute(
                "INSERT INTO membro_projeto (id_projeto, id_membro) VALUES (%s, %s)",
                (projeto_id, membro_id),
            )
            assert cursor.rowcount == 1

            cursor.execute("DELETE FROM membros WHERE id = %s", (membro_id,))
            assert cursor.rowcount == 1

            cursor.execute(
                "SELECT id_membro FROM membro_projeto "
                "WHERE id_projeto = %s AND id_membro = %s",
                (projeto_id, membro_id),
            )
            assert cursor.fetchone() is None

            cursor.execute("SELECT id FROM projetos WHERE id = %s", (projeto_id,))
            assert cursor.fetchone() == (projeto_id,)
    finally:
        db_test.rollback()