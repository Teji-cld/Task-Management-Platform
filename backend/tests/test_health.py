from app import main as main_module


def test_health_returns_ok_when_database_is_up(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["redis"] in {"disabled", "up"}  # "disabled" unless using real services


def test_health_returns_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(main_module, "check_database", lambda: False)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["database"] == "down"


def test_interactive_docs_are_available(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
