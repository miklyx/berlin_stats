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
    meetings = parse_meeting_html(meeting_html)
    polizei = parse_polizei_html(polizei_html)
    res = db.upsert_into_supabase_polizei(polizei)


app = create_app()

@app.on_event("startup")
async def startup_event():
        await update_db() 

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/polizei")
def get_polizei():
    # This is where you would call your database function to get the data
    # For example:
    # data = db.get_polizei_data()
    # return data
    return {"message": "This is the polizei endpoint"}