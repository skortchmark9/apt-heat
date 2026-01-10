# Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Run backend
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY rates.py ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
EXPOSE 8000
WORKDIR /app/backend
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
