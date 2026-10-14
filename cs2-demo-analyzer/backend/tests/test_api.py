import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("TASK_MODE", "inline")
    monkeypatch.setenv("CHUNK_SIZE_MB", "1")
    monkeypatch.setenv("MAX_UPLOAD_MB", "100")
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "3")
    from app import config, db

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()


def upload_bytes(client, data: bytes, name="match.dem"):
    r = client.post("/api/uploads", json={"filename": name, "size": len(data)})
    assert r.status_code == 201, r.text
    info = r.json()
    cs = info["chunk_size"]
    for i in range(info["total_chunks"]):
        r = client.put(f"/api/uploads/{info['upload_id']}/chunks/{i}", content=data[i * cs : (i + 1) * cs])
        if r.status_code != 200:
            return info, r
    return info, client.post(f"/api/uploads/{info['upload_id']}/complete")


def test_rejects_wrong_extension(client):
    r = client.post("/api/uploads", json={"filename": "match.zip", "size": 10})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_extension"


def test_rejects_too_large(client):
    r = client.post("/api/uploads", json={"filename": "a.dem", "size": 101 * 1024 * 1024})
    assert r.status_code == 413


def test_rejects_non_demo_by_header(client):
    _, r = upload_bytes(client, b"this is not a demo" * 100)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "not_a_demo"


def test_rejects_csgo_demo(client):
    _, r = upload_bytes(client, b"HL2DEMO\x00" + b"\x00" * 2000)
    assert r.json()["detail"]["code"] == "not_cs2"


def test_corrupt_cs2_demo_reports_error_and_deletes_file(client, tmp_path):
    info, r = upload_bytes(client, b"PBDEMS2\x00" + os.urandom(3 * 1024 * 1024 + 123))
    assert r.status_code == 202
    match_id = r.json()["match_id"]
    m = client.get(f"/api/matches/{match_id}").json()
    assert m["status"] == "failed"
    assert m["error"]["code"] in {"corrupt_demo", "no_rounds"}
    assert not list((tmp_path / "uploads").glob("*.dem"))


def test_incomplete_upload(client):
    r = client.post("/api/uploads", json={"filename": "a.dem", "size": 3 * 1024 * 1024})
    up = r.json()["upload_id"]
    client.put(f"/api/uploads/{up}/chunks/0", content=b"PBDEMS2\x00" + b"\x00" * (1024 * 1024 - 8))
    r = client.post(f"/api/uploads/{up}/complete")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "incomplete"


def test_wrong_chunk_size(client):
    r = client.post("/api/uploads", json={"filename": "a.dem", "size": 3 * 1024 * 1024})
    up = r.json()["upload_id"]
    r = client.put(f"/api/uploads/{up}/chunks/0", content=b"PBDEMS2\x00")
    assert r.status_code == 400


def test_rate_limit(client):
    codes = [client.post("/api/uploads", json={"filename": "a.dem", "size": 10}).status_code for _ in range(4)]
    assert codes == [201, 201, 201, 429]


def test_unknown_ids(client):
    assert client.get("/api/matches/nope").status_code == 404
    assert client.get("/api/reports/nope").status_code == 404


def test_real_demo_end_to_end(client, real_demo_path, tmp_path):
    data = Path(real_demo_path).read_bytes()
    _, r = upload_bytes(client, data)
    assert r.status_code == 202, r.text
    match_id = r.json()["match_id"]
    m = client.get(f"/api/matches/{match_id}").json()
    assert m["status"] == "done", m
    assert m["progress"] == 100
    assert len(m["players"]) == 10
    assert not list((tmp_path / "uploads").glob("*.dem")), "демка должна удаляться после анализа"

    player = m["players"][0]
    rep = client.get(f"/api/reports/{player['report_id']}").json()
    assert rep["report"]["player"]["steamid"] == player["steamid"]
    assert "counterstrafe" in rep["report"] and "rating" in rep["report"]

    found = client.get(f"/api/matches/{match_id}/players/{player['steamid']}").json()
    assert found["report_id"] == player["report_id"]
    r = client.get(f"/api/matches/{match_id}/players/123")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "player_not_found"
