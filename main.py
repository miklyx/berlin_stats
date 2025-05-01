from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scrap import get_html, parse_polizei_html, parse_meeting_html
from fastapi_utils.tasks import repeat_every
import db

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

@repeat_every(seconds=43200)  # Run twice a day
async def update_db():
    polizei_html = get_html('https://www.berlin.de/polizei/polizeimeldungen')
    meeting_html= get_html('https://www.berlin.de/polizei/service/versammlungsbehoerde/versammlungen-aufzuege')
    polizei = parse_polizei_html(polizei_html)
    res = db.upsert_into_supabase_polizei(polizei)
    meetings = parse_meeting_html(meeting_html)
    resm = db.upsert_into_supabase_meeting(meetings)
    

app = create_app()

@app.on_event("startup")
async def startup_event():
    pass        
    #await update_db()

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/police_report_by_keyword/{keyword}")
def get_polizei_by_keyword(keyword: str):
    data = db.find_polizei_by_keyword_supabase(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}
    
@app.get("/meeting_by_keyword/{keyword}")
def get_meeting_by_keyword(keyword: str):
    data = db.find_meeting_by_keyword_supabase(keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}

    
@app.get("/meeting_by_keyword_and_datum/{keyword}/{datum}")
def get_meeting_by_keyword_and_datum(keyword: str, datum: str):
    data = db.find_meeting_by_datum_and_keyword_supabase(datum, keyword)
    if data:
        return {"data": data}
    else:
        return {"message": "No data found."}