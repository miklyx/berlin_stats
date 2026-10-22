import pytest
from fastapi.testclient import TestClient

import db
import main


@pytest.fixture
def client(clean_db):
    with TestClient(main.app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.head("/health").status_code == 200


def test_search_empty_and_found(client):
    assert client.get("/meeting_by_keyword/xyz").json() == {"message": "No data found."}
    db.insert_only_new_meeting_data(
        [{
            "Datum": "01.01.2025", "Von": "1", "Bis": "2", "Thema": "Klima",
            "PLZ": "1", "Versammlungsort": "o", "Aufzugsstrecke": "",
        }]
    )
    body = client.get("/meeting_by_keyword/klima").json()
    assert body["data"][0]["thema"] == "Klima"
    assert client.get("/meeting_by_keyword_and_datum/klima/01.01.2025").status_code == 200


def test_limit_validation(client):
    assert client.get("/meeting_by_keyword/x?limit=0").status_code == 422
    assert client.get("/meeting_by_keyword/x?limit=501").status_code == 422


def test_update_requires_password(client, monkeypatch):
    assert client.get("/update_meetings").status_code == 401
    assert client.get("/update_meetings", headers={"X-Password": "bad"}).status_code == 401
    monkeypatch.setattr(main, "update_meetings", lambda: 3)
    r = client.get("/update_meetings", headers={"X-Password": "secret"})
    assert r.status_code == 200 and r.json()["new"] == 3


def test_update_rejected_when_secret_unset(client, monkeypatch):
    monkeypatch.delenv("SECRET_PASSWORD")
    assert client.get("/update_meetings").status_code == 401
