import pytest


@pytest.mark.api
@pytest.mark.parametrize(
    ("url", "campo"),
    [
        ("/tarefas/invalido", ["path", "tarefa_id"]),
        ("/sprints/invalido", ["path", "projeto_id"]),
        ("/analytics?task_status=invalido", ["query", "task_status", 0]),
    ],
)
def test_api_rejeita_parametro_invalido(api_client, url, campo):
    resposta = api_client.get(url)

    assert resposta.status_code == 422
    assert campo in [erro["loc"] for erro in resposta.json()["detail"]]
