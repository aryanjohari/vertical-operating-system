# GSC on Railway: set build variable GCP_SERVICE_ACCOUNT_B64 to base64-encoded service account JSON
# (e.g. base64 -w0 your-key.json) and runtime var GSC_SERVICE_ACCOUNT_FILE=/app/backend/secrets/gcp-secret.json
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG GCP_SERVICE_ACCOUNT_B64
RUN mkdir -p /app/backend/secrets && \
    if [ -n "$GCP_SERVICE_ACCOUNT_B64" ]; then echo "$GCP_SERVICE_ACCOUNT_B64" | base64 -d > /app/backend/secrets/gcp-secret.json; fi

CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT