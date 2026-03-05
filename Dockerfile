FROM python:3.11-slim

# System libs needed by opencv-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    default-libmysqlclient-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p face_data trained_model static/uploads

EXPOSE $PORT

CMD gunicorn wsgi:app --workers 2 --bind 0.0.0.0:$PORT --timeout 120
