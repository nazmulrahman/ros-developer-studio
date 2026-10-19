"""Scaffold contract tests: auth, read-only defaults, no fake data from unimplemented endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.core import auth
from backend.main import create_app


H = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    auth.set_token("test-token")
    with TestClient(create_app()) as c:
        yield c


def test_health_open(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_auth_required(client):
    assert client.get("/api/session").status_code == 401
    assert client.get("/api/live/graph").status_code == 401
    assert client.get("/api/session", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/host/metrics").status_code == 401


def test_session_defaults_are_read_only(client):
    s = client.get("/api/session", headers=H).json()
    assert s["test_tools_enabled"] is False
    assert s["capabilities"]["test_tools"] is False and s["capabilities"]["recording"] is True and s["capabilities"]["offline_bags"] is True


@pytest.mark.parametrize("method,path", [
    ("get", "/api/host/processes"),
])
def test_unimplemented_returns_501_not_fake_data(client, method, path):
    r = getattr(client, method)(path, headers=H)
    assert r.status_code == 501 and r.json()["detail"]["error"] == "not_implemented"


def test_testtools_disabled_and_writes_refused(client):
    assert client.get("/api/testtools/state", headers=H).json()["enabled"] is False
    r = client.post("/api/testtools/publish", headers=H, json={"topic": "/x", "type": "std_msgs/msg/String", "message": {}})
    assert r.status_code == 501


def test_ws_requires_token(client):
    with client.websocket_connect("/ws/live?token=bad") as ws:
        with pytest.raises(Exception):
            ws.receive_text()
