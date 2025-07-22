from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from checker import check_tee_times, get_cached_tee_times
import subprocess
import os
import json
import threading
from scraper import run_scraper
import logging
import psycopg2 # NEW: Import for PostgreSQL database interaction

# Configure logging for app.py as well
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Install Playwright browser at runtime (only if it hasn't been installed by postBuildCommand)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    logging.error(f"Failed to install Playwright at runtime: {e}")

# --- REMOVED: RUNTIME_CONFIG_FILE and os.makedirs for file-based config ---
# RUNTIME_CONFIG_FILE = "current_config.json"
# os.makedirs(os.path.dirname(RUNTIME_CONFIG_FILE) or '.', exist_ok=True)
# --- END REMOVED ---

# NEW: Retrieve DATABASE_URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logging.error("DATABASE_URL environment variable not set. Database operations will fail.")
    # You might want to raise an exception here or handle it more gracefully
    # if the app cannot function without a database.

DEFAULT_CONFIG = {
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM",
    "is_paused": False
}

# --- REMOVED: in_memory_config initialization from file ---
# in_memory_config = DEFAULT_CONFIG.copy()
# if os.path.exists(RUNTIME_CONFIG_FILE):
#     try:
#         with open(RUNTIME_CONFIG_FILE, "r") as f:
#             loaded_config = json.load(f)
#             in_memory_config.update(loaded_config)
#             if "is_paused" not in in_memory_config:
#                 in_memory_config["is_paused"] = DEFAULT_CONFIG["is_paused"]
#             logging.info(f"Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
#     except json.JSONDecodeError:
#         logging.warning(f"Error decoding JSON from {RUNTIME_CONFIG_FILE}. Using default config.")
#     except Exception as e:
#         logging.error(f"Failed to load runtime config from {RUNTIME_CONFIG_FILE}: {e}. Using default config.")
# --- END REMOVED ---


# NEW: Function to connect to DB and create table if not exists
def init_db():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Create table if it doesn't exist. Using a single row with ID 1 for simplicity.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                id SERIAL PRIMARY KEY,
                config_date VARCHAR(10) NOT NULL,
                config_start VARCHAR(10) NOT NULL,
                config_end VARCHAR(10) NOT NULL,
                is_paused BOOLEAN DEFAULT FALSE
            );
        """)
        # Ensure there's always at least one row for config (with id=1)
        # This uses INSERT ... ON CONFLICT (id) DO NOTHING to only insert if ID 1 doesn't exist
        cur.execute("""
            INSERT INTO app_config (id, config_date, config_start, config_end, is_paused)
            VALUES (1, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, (DEFAULT_CONFIG["date"], DEFAULT_CONFIG["start"], DEFAULT_CONFIG["end"], DEFAULT_CONFIG["is_paused"]))
        conn.commit()
        cur.close()
        logging.info("Database initialized and config table ensured.")
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        # If DB init fails, the app might not function correctly. Consider more robust error handling.
    finally:
        if conn:
            conn.close()

# NEW: Helper function to get config from DB
def get_config_from_db():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT config_date, config_start, config_end, is_paused FROM app_config WHERE id = 1;")
        row = cur.fetchone()
        cur.close()
        if row:
            return {
                "date": row[0],
                "start": row[1],
                "end": row[2],
                "is_paused": row[3]
            }
        else:
            # If no config found (shouldn't happen after init_db), return default
            logging.warning("No config found in database, returning default config.")
            return DEFAULT_CONFIG
    except Exception as e:
        logging.error(f"Failed to read config from DB: {e}")
        return DEFAULT_CONFIG # Fallback to default on error
    finally:
        if conn:
            conn.close()

app = FastAPI()

# NEW: Call init_db on application startup
@app.on_event("startup")
async def startup_event():
    init_db()

# Mount static file directory to serve index.html, style.css, script.js
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# The root route now simply returns a status message,
# the UI is accessed via /static/ or /static/index.html
@app.get("/")
def root():
    return {"status": "Tee Time API is live. Access UI at /static/index.html or /static/"}

@app.get("/set")
def set_config(date: str = Query(...), start: str = Query(...), end: str = Query(...)):
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Update the existing config row (assuming only one row with id=1)
        cur.execute("""
            UPDATE app_config SET config_date = %s, config_start = %s, config_end = %s
            WHERE id = 1;
        """, (date, start, end))
        conn.commit()
        cur.close()
        # After update, read back the current config from DB to return
        current_config = get_config_from_db() # Helper function to read from DB
        logging.info(f"Config updated and saved to DB: {current_config}")
        return {"message": "Configuration updated successfully", "current_config": current_config}
    except Exception as e:
        logging.error(f"Failed to update config in DB: {e}")
        return {"error": f"Failed to update config: {e}"}
    finally:
        if conn:
            conn.close()


@app.get("/get")
def get_config():
    # Now simply calls the helper function to read from DB
    return {"current_config": get_config_from_db()}


@app.get("/check")
def check():
    try:
        results = get_cached_tee_times()
        return {"results": results}
    except Exception as e:
        logging.error(f"Error checking cached results: {e}")
        return {"error": str(e)}

@app.get("/run-scraper")
def run_scraper_background():
    # Read latest config from DB
    current_config = get_config_from_db() 

    if current_config.get("is_paused", False): # Check the pause flag
        logging.info("Scraper is currently paused. Not starting a new run.")
        return {"message": "Scraper is currently paused."}

    current_date = current_config["date"]
    current_start = current_config["start"]
    current_end = current_config["end"]

    logging.info(f"Triggered scraper run with config: Date={current_date}, Start={current_start}, End={current_end}")

    def scraper_thread():
        run_scraper(current_date, current_start, current_end)

    threading.Thread(target=scraper_thread).start()
    return {"message": "Scraper started in background"}

# NEW: Endpoint to toggle the scraper pause state
@app.get("/toggle-scraper-pause")
def toggle_scraper_pause():
    conn = None
    try:
        current_config = get_config_from_db() # Get current state from DB
        new_state = not current_config.get("is_paused", False)

        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("UPDATE app_config SET is_paused = %s WHERE id = 1;", (new_state,))
        conn.commit()
        cur.close()

        status_message = "paused" if new_state else "resumed"
        # Return the updated config from DB
        return {"message": f"Scraper has been {status_message}.", "is_paused": new_state, "current_config": get_config_from_db()}
    except Exception as e:
        logging.error(f"Failed to toggle pause state in DB: {e}")
        return {"error": f"Failed to toggle pause state: {e}"}
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
