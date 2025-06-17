from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from scrap import get_html, parse_polizei_html, parse_meeting_html
from fastapi_utils.tasks import repeat_every
import db
import dotenv
import os

dotenv.load_dotenv()



def create_app():
    app = FastAPI()

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    return app

@repeat_every(seconds=3600)  # Run twice a day
async def update_db():
    polizei_html = get_html('https://www.berlin.de/polizei/polizeimeldungen')
    meeting_html= get_html('https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege')
    polizei = parse_polizei_html(polizei_html)
    res = db.insert_only_new_polizei_data(polizei)
    meetings = parse_meeting_html(meeting_html)
    resm = db.insert_only_new_meeting_data(meetings)

def verify_password(password: Optional[str] = Header(None, alias="X-Password")):
    if password != os.environ.get("SECRET_PASSWORD"):
        raise HTTPException(
            status_code=401,
            detail="Wrong password",
            headers={"WWW-Authenticate": "Password"},
        )
    return password


app = create_app()

@app.on_event("startup")
async def startup_event():
    #pass        
    await update_db()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/police_report_by_keyword/{keyword}")
async def get_polizei_by_keyword(keyword: str):
    data = await db.find_polizei_by_keyword_supabase(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}
    
@app.get("/meeting_by_keyword/{keyword}")
async def get_meeting_by_keyword(keyword: str):
    data = await db.find_meeting_by_keyword_supabase(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}

    
@app.get("/meeting_by_keyword_and_datum/{keyword}/{datum}")
async def get_meeting_by_keyword_and_datum(keyword: str, datum: str):
    data = await db.find_meeting_by_datum_and_keyword_supabase(datum, keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}
    
    
@app.get("/update_polizei", dependencies=[Depends(verify_password)])
async def update_polizei_endpoint():
    polizei_html = get_html('https://www.berlin.de/polizei/polizeimeldungen')
    polizei = parse_polizei_html(polizei_html)
    res = await db.insert_only_new_polizei_data(polizei)
    return {"message": "Polizei updated successfully."}

@app.get("/update_meetings", dependencies=[Depends(verify_password)])
async def update_meetings_endpoint():
    meeting_html= get_html('https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege')
    meetings = parse_meeting_html(meeting_html)
    resm = await db.insert_only_new_meeting_data(meetings)
    return {"message": "Meetings updated successfully."}

@app.head("/health")
async def health_check():
    await update_meetings_endpoint()
    await update_polizei_endpoint()
    return {"status": "ok"}