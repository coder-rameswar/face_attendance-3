# db.py - Database connection with Railway/production support
import mysql.connector
from mysql.connector import Error
import time
import logging
from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_connection(retries=3, delay=2):
    """Get a MySQL connection, with retries for cloud environments."""
    for attempt in range(retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                return conn
        except Error as e:
            logger.warning(f"DB connect attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    raise Exception("Could not connect to database after multiple attempts.")


def execute_query(query, params=None, fetch=False, fetchone=False):
    """Execute a query and optionally return results."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        if fetchone:
            return cursor.fetchone()
        if fetch:
            return cursor.fetchall()
        conn.commit()
        return cursor.lastrowid
    except Error as e:
        logger.error(f"Query error: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        raise
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn and conn.is_connected():
            conn.close()


def init_db():
    """Run database.sql schema on first deploy."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), 'database.sql')
    if not os.path.exists(schema_path):
        logger.warning("database.sql not found, skipping init")
        return False
    try:
        cfg = DB_CONFIG.copy()
        db_name = cfg.pop('database', None)
        cfg.pop('autocommit', None)

        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor()

        with open(schema_path, 'r') as f:
            sql = f.read()

        for statement in sql.split(';'):
            stmt = statement.strip()
            if stmt:
                try:
                    cursor.execute(stmt)
                except Error as e:
                    if 'already exists' not in str(e).lower():
                        logger.warning(f"SQL warning: {e}")

        conn.commit()
        cursor.close()
        conn.close()
        logger.info("✅ Database initialised")
        return True
    except Error as e:
        logger.error(f"DB init error: {e}")
        return False
