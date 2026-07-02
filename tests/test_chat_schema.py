from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def assert_chat_schema(body: dict) -> None:
    assert set(body) == {"reply", "recommendations", "end_of_conversation"}
    assert isinstance(body["reply"], str)
    assert isinstance(body["recommendations"], list)
    assert isinstance(body["end_of_conversation"], bool)
    for item in body["recommendations"]:
        assert set(item) == {"name", "url", "test_type"}
        assert all(isinstance(item[key], str) for key in item)


def test_chat_schema_for_valid_request() -> None:
    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Hiring a Java developer"}]})
    assert response.status_code == 200
    assert_chat_schema(response.json())


def test_invalid_request_is_graceful() -> None:
    response = client.post("/chat", json={"messages": []})
    assert response.status_code == 200
    body = response.json()
    assert_chat_schema(body)
    assert body["recommendations"] == []

