FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY atx_ingest ./atx_ingest
COPY config ./config
CMD ["python", "-m", "atx_ingest.cli", "run", "--interval", "1800"]
