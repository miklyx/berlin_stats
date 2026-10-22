from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from scrap import get_html, parse_polizei_html, parse_meeting_html
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
import db
import dotenv
import os

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLIZEI_URL = 'https://www.berlin.de/polizei/polizeimeldungen'
MEETINGS_URL = 'https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege'



def create_app():
    app = FastAPI(lifespan=lifespan, root_path=os.environ.get("ROOT_PATH", ""))

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    return app

def poll_once():
    # only one replica polls at a time; the others skip this round
    with db.poll_lock() as acquired:
        if not acquired:
            return None
        polizei = parse_polizei_html(get_html(POLIZEI_URL), skip_urls=db.existing_polizei_urls())
        meetings = parse_meeting_html(get_html(MEETINGS_URL))
        return db.insert_only_new_polizei_data(polizei), db.insert_only_new_meeting_data(meetings)


async def poll_loop():
    interval = float(os.environ.get("POLL_INTERVAL_HOURS", "24")) * 3600
    if os.environ.get("POLL_ON_STARTUP", "true").lower() not in ("0", "false", "no"):
        delay = 0
    else:
        delay = interval
    while True:
        await asyncio.sleep(delay)
        delay = interval
        try:
            result = await asyncio.to_thread(poll_once)
            if result is None:
                logger.info("Poll skipped: another replica is polling")
            else:
                logger.info("Poll done: %d new polizei, %d new meetings", *result)
        except Exception:
            logger.exception("Poll failed")


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        db.close_pool()

def verify_password(password: Optional[str] = Header(None, alias="X-Password")):
    if password != os.environ.get("SECRET_PASSWORD"):
        raise HTTPException(
            status_code=401,
            detail="Wrong password",
            headers={"WWW-Authenticate": "Password"},
        )
    return password


app = create_app()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/police_report_by_keyword/{keyword}")
def get_polizei_by_keyword(keyword: str):
    data = db.find_polizei_by_keyword(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}
    
@app.get("/meeting_by_keyword/{keyword}")
def get_meeting_by_keyword(keyword: str):
    data = db.find_meeting_by_keyword(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}

    
@app.get("/meeting_by_keyword_and_datum/{keyword}/{datum}")
def get_meeting_by_keyword_and_datum(keyword: str, datum: str):
    data = db.find_meeting_by_datum_and_keyword(datum, keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}
    
    
@app.get("/update_polizei", dependencies=[Depends(verify_password)])
def update_polizei_endpoint():
    polizei_html = get_html('https://www.berlin.de/polizei/polizeimeldungen')
    polizei = parse_polizei_html(polizei_html, skip_urls=db.existing_polizei_urls())
    res = db.insert_only_new_polizei_data(polizei)
    return {"message": "Polizei updated successfully."}

@app.get("/update_meetings", dependencies=[Depends(verify_password)])
def update_meetings_endpoint():
    meeting_html= get_html('https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege')
    meetings = parse_meeting_html(meeting_html)
    resm = db.insert_only_new_meeting_data(meetings)
    return {"message": "Meetings updated successfully."}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}