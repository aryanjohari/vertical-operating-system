FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# This forces the Linux dependencies to install perfectly
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .

CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT