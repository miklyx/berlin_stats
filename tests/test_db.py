import db

REPORT = {"title": "t", "time": "01.01.2025", "district": "Mitte", "url": "u1", "details": "Messer 100% gefunden"}
MEETING = {
    "Datum": "01.01.2025", "Von": "10:00", "Bis": "12:00", "Thema": "Klima_Demo",
    "PLZ": "1", "Versammlungsort": "o", "Aufzugsstrecke": "",
}


def test_polizei_dedup(clean_db):
    assert db.insert_only_new_polizei_data([REPORT, REPORT]) == 1
    assert db.insert_only_new_polizei_data([REPORT]) == 0
    assert db.existing_polizei_urls() == {"u1"}


def test_polizei_search_and_escape(clean_db):
    db.insert_only_new_polizei_data([REPORT])
    assert len(db.find_polizei_by_keyword("messer")) == 1
    assert db.find_polizei_by_keyword("100%") is not None
    assert db.find_polizei_by_keyword("Messer%gefunden") is None
    assert db.find_polizei_by_keyword("nichts") is None


def test_meeting_dedup_and_search(clean_db):
    assert db.insert_only_new_meeting_data([MEETING, MEETING]) == 1
    assert len(db.find_meeting_by_keyword("klima")) == 1
    assert db.find_meeting_by_keyword("klimaXdemo") is None
    assert db.find_meeting_by_datum_and_keyword("01.01.2025", "klima") is not None
    assert db.find_meeting_by_datum_and_keyword("02.01.2025", "klima") is None


def test_pagination(clean_db):
    rows = [{**MEETING, "Thema": f"demo {i}"} for i in range(5)]
    db.insert_only_new_meeting_data(rows)
    assert len(db.find_meeting_by_keyword("demo", limit=2)) == 2
    assert len(db.find_meeting_by_keyword("demo", limit=10, offset=3)) == 2


def test_poll_lock_is_exclusive(clean_db):
    with db.poll_lock() as first:
        assert first
        with db.poll_lock() as second:
            assert not second
    with db.poll_lock() as again:
        assert again
