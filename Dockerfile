
FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

FROM base AS backend
COPY backend ./backend
EXPOSE 8000
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS frontend
COPY frontend ./frontend
EXPOSE 8503
CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8503", "--server.headless=true"]
