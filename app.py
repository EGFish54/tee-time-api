from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from checker import check_tee_times, get_cached_tee_times
import subprocess
import os
import json
import threading
from scraper import run_scraper
import logging

# Configure logging for app.py as well
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Install Playwright browser at runtime (only if it hasn't been installed by postBuildCommand)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    logging.error(f"Failed to install Playwright at runtime: {e}")

# --- IMPORTANT CHANGE HERE: Revert to a writable path for free tier ---
RUNTIME_CONFIG_FILE = "current_config.json" # This will be in your app's root directory
# --- END IMPORTANT CHANGE ---

# Ensure the directory for the config file exists (this will create it if using subdirectories,
# but for root, it just ensures the path is valid)
os.makedirs(os.path.dirname(RUNTIME_CONFIG_FILE) or '.', exist_ok=True) # Added 'or '.' for root path


DEFAULT_CONFIG = {
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM"
}

in_memory_config = DEFAULT_CONFIG.copy()

# Try to load config from the runtime file (if it exists)
if os.path.exists(RUNTIME_CONFIG_FILE):
    try:
        with open(RUNTIME_CONFIG_FILE, "r") as f:
            loaded_config = json.load(f)
            in_memory_config.update(loaded_config)
            logging.info(f"Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
    except json.JSONDecodeError:
        logging.warning(f"Error decoding JSON from {RUNTIME_CONFIG_FILE}. Using default config.")
    except Exception as e:
        logging.error(f"Failed to load runtime config from {RUNTIME_CONFIG_FILE}: {e}. Using default config.")


app = FastAPI()

# Mount static file directory to serve index.html, style.css, script.js
# html=True serves index.html if the directory is requested (e.g., /static/)
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# The root route now simply returns a status message,
# the UI is accessed via /static/ or /static/index.html
@app.get("/")
def root():
    return {"status": "Tee Time API is live. Access UI at /static/index.html or /static/"}

@app.get("/set")
def set_config(date: str = Query(...), start: str = Query(...), end: str = Query(...)):
    global in_memory_config

    in_memory_config["date"] = date
    in_memory_config["start"] = start
    in_memory_config["end"] = end

    try:
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(in_memory_config, f)
        logging.info(f"Runtime config updated and saved to file: {in_memory_config}")
        return {"message": "Configuration updated successfully", "current_config": in_memory_config}
    except Exception as e:
        logging.error(f"Failed to save runtime config to file: {e}")
        return {"error": f"Configuration updated in memory but failed to save to file: {e}", "current_config": in_memory_config}


@app.get("/get")
def get_config():
    if os.path.exists(RUNTIME_CONFIG_FILE):
        try:
            with open(RUNTIME_CONFIG_FILE, "r") as f:
                current_saved_config = json.load(f)
                return {"current_config": current_saved_config}
        except Exception as e:
            logging.error(f"Failed to load runtime config for /get endpoint: {e}")
            return {"current_config": in_memory_config}
    else:
        return {"current_config": in_memory_config}


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
    current_date = in_memory_config["date"]
    current_start = in_memory_config["start"]
    current_end = in_memory_config["end"]

    logging.info(f"Triggered scraper run with config: Date={current_date}, Start={current_start}, End={current_end}")

    def scraper_thread():
        run_scraper(current_date, current_start, current_end)

    threading.Thread(target=scraper_thread).start()
    return {"message": "Scraper started in background"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
