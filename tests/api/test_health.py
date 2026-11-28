import pytest


@pytest.mark.api
def test_health(api_client):
    resposta = api_client.get("/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}