from unittest.mock import Mock

import pandas as pd
import pytest

from backend import data_access


@pytest.mark.api
def test_metricas_de_sprints_contam_apenas_tarefas_do_projeto(
    api_client, monkeypatch
):
    sprints = pd.DataFrame(
        {
            "id": [42, 43],
            "id_projeto": [10, 10],
            "data_in": pd.to_datetime(["2025-01-01", None]),
            "data_fin": pd.to_datetime(["2025-01-03", None]),
        }
    )
    tarefas = pd.DataFrame(
        {
            "id_projeto": [10, 10, 20],
            "id_sprint": [42, 42, 42],
            "estado": ["concluida", "em_andamento", "concluida"],
        }
    )
    dados = {"sprints": sprints, "tasks": tarefas}
    calcular_analytics = Mock(return_value=dados)
    monkeypatch.setattr(data_access, "fetch_all", Mock(return_value=({}, {}, {})))
    monkeypatch.setattr(data_access, "normalize", Mock(return_value={}))
    monkeypatch.setattr(data_access, "filtrar_dados_por_usuario", Mock(return_value={}))
    monkeypatch.setattr(data_access, "make_analytics", calcular_analytics)

    resposta = api_client.get("/analytics/sprints?project_ids=10")

    assert resposta.status_code == 200
    metricas = {item["id_sprint"]: item for item in resposta.json()}
    assert set(metricas) == {42, 43}
    assert metricas[42]["tarefas"] == 2
    assert metricas[42]["concluidas"] == 1
    assert metricas[42]["pendentes"] == 1
    assert metricas[42]["taxa_conclusao"] == 50
    assert metricas[42]["duracao_dias"] == 2
    assert metricas[43]["tarefas"] == 0
    assert metricas[43]["taxa_conclusao"] is None
    calcular_analytics.assert_called_once_with(
        {}, company_ids=None, project_ids=[10], task_status=None
    )
