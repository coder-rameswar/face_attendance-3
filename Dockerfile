FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

RUN mkdir -p face_data trained_model static/uploads

# Railway injects $PORT at runtime
ENV PORT=8000
ENV FLASK_ENV=production

# Use shell form so $PORT expands correctly at runtime
CMD gunicorn wsgi:app \
    --workers 2 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
