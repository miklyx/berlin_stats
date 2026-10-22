import pytest
import requests

import scrap


def test_parse_polizei_html(fixture_text, monkeypatch):
    monkeypatch.setattr(scrap, "get_html", lambda url: fixture_text("polizei_detail.html"))
    reports = scrap.parse_polizei_html(fixture_text("polizei_list.html"), delay=0)
    assert [r["district"] for r in reports] == ["Mitte", "Pankow"]
    assert reports[0]["url"] == "https://www.berlin.de/polizei/meldung/1.html"
    assert reports[0]["details"] == "Ein Messer wurde gefunden. Zeugen gesucht."


def test_parse_polizei_skips_known_urls(fixture_text, monkeypatch):
    monkeypatch.setattr(scrap, "get_html", lambda url: fixture_text("polizei_detail.html"))
    known = {"https://www.berlin.de/polizei/meldung/1.html"}
    reports = scrap.parse_polizei_html(fixture_text("polizei_list.html"), skip_urls=known, delay=0)
    assert len(reports) == 1


def test_parse_polizei_skips_failed_detail(fixture_text, monkeypatch):
    def boom(url):
        raise requests.ConnectionError("dropped")

    monkeypatch.setattr(scrap, "get_html", boom)
    assert scrap.parse_polizei_html(fixture_text("polizei_list.html"), delay=0) == []


def test_parse_meeting_html(fixture_text):
    rows = scrap.parse_meeting_html(fixture_text("meetings.html"))
    assert len(rows) == 2
    assert rows[0]["Thema"] == "Klima 100% Demo"
    assert rows[1]["Aufzugsstrecke"] == ""


def test_get_html_retries(monkeypatch):
    calls = []

    class Resp:
        text = "ok"

        def raise_for_status(self):
            pass

    def fake_get(url, timeout):
        calls.append(url)
        if len(calls) < 3:
            raise requests.ConnectionError("x")
        return Resp()

    monkeypatch.setattr(scrap._session, "get", fake_get)
    monkeypatch.setattr(scrap.time, "sleep", lambda s: None)
    assert scrap.get_html("http://x") == "ok"
    assert len(calls) == 3


def test_get_html_gives_up(monkeypatch):
    monkeypatch.setattr(scrap._session, "get", lambda url, timeout: (_ for _ in ()).throw(requests.Timeout()))
    monkeypatch.setattr(scrap.time, "sleep", lambda s: None)
    with pytest.raises(requests.Timeout):
        scrap.get_html("http://x", retries=2)
