import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta

import dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import db
from scrap import get_html, parse_meeting_html, parse_polizei_html

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLIZEI_URL = "https://www.berlin.de/polizei/polizeimeldungen"
MEETINGS_URL = "https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege"

Limit = Query(100, ge=1, le=500, description="Max rows to return")
Offset = Query(0, ge=0, description="Rows to skip")

# Track last successful poll
_last_poll_time: datetime | None = None
_last_poll_result: tuple[int, int] | None = None


def update_polizei() -> int:
    html = get_html(POLIZEI_URL)
    # detail pages are only fetched for reports that are not stored yet
    reports = parse_polizei_html(html, skip_urls=db.existing_polizei_urls())
    return db.insert_only_new_polizei_data(reports)


def update_meetings() -> int:
    return db.insert_only_new_meeting_data(parse_meeting_html(get_html(MEETINGS_URL)))


def poll_once() -> tuple[int, int] | None:
    # only one replica polls at a time; the others skip this round
    with db.poll_lock() as acquired:
        if not acquired:
            return None
        return update_polizei(), update_meetings()


async def poll_loop() -> None:
    global _last_poll_time, _last_poll_result
    interval = float(os.environ.get("POLL_INTERVAL_HOURS", "24")) * 3600
    on_startup = os.environ.get("POLL_ON_STARTUP", "true").lower() not in ("0", "false", "no")
    delay = 0 if on_startup else interval
    consecutive_errors = 0
    while True:
        await asyncio.sleep(delay)
        delay = interval
        try:
            result = await asyncio.to_thread(poll_once)
            if result is None:
                logger.info("Poll skipped: another replica is polling")
            else:
                logger.info("Poll done: %d new polizei, %d new meetings", *result)
                _last_poll_time = datetime.utcnow()
                _last_poll_result = result
            consecutive_errors = 0
        except Exception:
            consecutive_errors += 1
            logger.exception("Poll failed (attempt %d)", consecutive_errors)
            if consecutive_errors >= 5:
                logger.critical("Poll failed %d times in a row - possible permanent issue", consecutive_errors)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        db.close_pool()


def verify_password(password: str | None = Header(None, alias="X-Password")) -> str:
    expected = os.environ.get("SECRET_PASSWORD")
    if not expected or password != expected:
        raise HTTPException(
            status_code=401,
            detail="Wrong password",
            headers={"WWW-Authenticate": "Password"},
        )
    return password


def create_app() -> FastAPI:
    app = FastAPI(
        title="Berlin stats",
        description="Search Berlin police reports and registered demonstrations.",
        lifespan=lifespan,
        root_path=os.environ.get("ROOT_PATH", ""),
    )
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "HEAD"],
        allow_headers=["*"],
    )
    return app


app = create_app()


def _wrap(data: list[dict] | None) -> dict:
    return {"data": data} if data else {"message": "No data found."}


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/police_report_by_keyword/{keyword}")
def get_polizei_by_keyword(keyword: str, limit: int = Limit, offset: int = Offset):
    return _wrap(db.find_polizei_by_keyword(keyword, limit, offset))


@app.get("/meeting_by_keyword/{keyword}")
def get_meeting_by_keyword(keyword: str, limit: int = Limit, offset: int = Offset):
    return _wrap(db.find_meeting_by_keyword(keyword, limit, offset))


@app.get("/meeting_by_keyword_and_datum/{keyword}/{datum}")
def get_meeting_by_keyword_and_datum(keyword: str, datum: str, limit: int = Limit, offset: int = Offset):
    return _wrap(db.find_meeting_by_datum_and_keyword(datum, keyword, limit, offset))


@app.get("/update_polizei", dependencies=[Depends(verify_password)])
def update_polizei_endpoint():
    return {"message": "Polizei updated successfully.", "new": update_polizei()}


@app.get("/update_meetings", dependencies=[Depends(verify_password)])
def update_meetings_endpoint():
    return {"message": "Meetings updated successfully.", "new": update_meetings()}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}


@app.get("/health/scraper")
async def health_check_scraper():
    """Check scraper health - has it run recently?"""
    if _last_poll_time is None:
        return {"status": "unknown", "last_poll": None, "message": "No polls have run yet"}
    
    now = datetime.utcnow()
    hours_since_poll = (now - _last_poll_time).total_seconds() / 3600
    max_hours = float(os.environ.get("POLL_INTERVAL_HOURS", "24")) * 1.5  # Allow 50% buffer
    
    if hours_since_poll > max_hours:
        return {
            "status": "unhealthy",
            "last_poll": _last_poll_time.isoformat() + "Z",
            "hours_since_poll": round(hours_since_poll, 2),
            "max_allowed_hours": round(max_hours, 2),
            "last_result": _last_poll_result,
        }
    
    return {
        "status": "healthy",
        "last_poll": _last_poll_time.isoformat() + "Z",
        "hours_since_poll": round(hours_since_poll, 2),
        "last_result": _last_poll_result,
    }
