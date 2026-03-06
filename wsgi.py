# wsgi.py - Gunicorn entry point for Railway
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app import app

# Only init DB when running via gunicorn (not during build/import)
def on_starting(server):
    """Called by gunicorn master process before workers fork."""
    try:
        from db import init_db
        logger.info("Running DB init check...")
        init_db()
    except Exception as e:
        logger.warning(f"DB init skipped (will retry on first request): {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))