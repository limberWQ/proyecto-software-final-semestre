FROM python:3.12-slim

WORKDIR /app

# Copiar e instalar dependencias
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar backend y frontend manteniendo la estructura
COPY backend/ ./backend/
COPY frontend/ ./frontend/

RUN mkdir -p /app/blockchain_data

EXPOSE 5000

CMD ["python", "backend/run.py"]