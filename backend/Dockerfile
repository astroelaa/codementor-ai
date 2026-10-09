# Hugging Face Spaces (Docker, free tier, no card) or any Docker host.
# Build context is the REPO ROOT; the Space's Dockerfile path is backend/Dockerfile.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# HF Spaces listens on 7860; Render-style hosts inject $PORT. Both work.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
