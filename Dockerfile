FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/data/berlin_stats.db

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py db.py scrap.py ./

RUN useradd --uid 10001 --no-create-home app && mkdir /data && chown app /data
USER 10001

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
