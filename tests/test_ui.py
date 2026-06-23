from fastapi.testclient import TestClient


def test_list_audio_empty(client: TestClient):
    r = client.get("/v1/audio")
    assert r.status_code == 200
    assert r.json() == []


def test_list_audio_returns_mp3_files(client: TestClient, tmp_path):
    name = "a" * 32 + ".mp3"
    path = tmp_path / name
    path.write_bytes(b"ID3fake")

    r = client.get("/v1/audio")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["filename"] == name
    assert data[0]["download_path"] == f"/v1/audio/{name}"
    assert data[0]["size_bytes"] == len(b"ID3fake")
    assert isinstance(data[0]["created_at"], float)


def test_ui_served_at_root(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Turn client requirements into audio" in r.text
