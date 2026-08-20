from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from checker import get_cached_tee_times
import subprocess
import os
import json
import logging
from scraper import run_scraper

# Configure logging for app.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# Install Playwright browser at runtime
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
    logging.info("✅ Playwright chromium installed successfully")
except Exception as e:
    logging.error(f"❌ Failed to install Playwright at runtime: {e}")

# Configuration file in writable location
RUNTIME_CONFIG_FILE = "current_config.json"

# Ensure the directory exists
os.makedirs(os.path.dirname(RUNTIME_CONFIG_FILE) or '.', exist_ok=True)

VALID_COURSES = {"All", "Highlands", "Fairways", "Meadows"}

# Default configuration
DEFAULT_CONFIG = {
    "searches": [
        {"date": "07/23/2025", "start": "08:00 AM", "end": "09:00 AM", "course": "All"}
    ],
    "is_paused": False
}

def normalize_config(config):
    """Ensure config has a 'searches' list and 'is_paused' flag, migrating legacy single-entry configs."""
    normalized = dict(config)

    if "searches" not in normalized:
        if all(k in normalized for k in ("date", "start", "end")):
            normalized["searches"] = [{
                "date": normalized.pop("date"),
                "start": normalized.pop("start"),
                "end": normalized.pop("end"),
                "course": normalized.pop("course", "All")
            }]
        else:
            normalized["searches"] = DEFAULT_CONFIG["searches"]

    if "is_paused" not in normalized:
        normalized["is_paused"] = DEFAULT_CONFIG["is_paused"]

    return normalized

# In-memory configuration
in_memory_config = DEFAULT_CONFIG.copy()

# Try to load config from file on startup
if os.path.exists(RUNTIME_CONFIG_FILE):
    try:
        with open(RUNTIME_CONFIG_FILE, "r") as f:
            loaded_config = json.load(f)
            in_memory_config = normalize_config(loaded_config)
            logging.info(f"✅ Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
    except json.JSONDecodeError:
        logging.warning(f"⚠️ Error decoding JSON from {RUNTIME_CONFIG_FILE}. Using default config.")
    except Exception as e:
        logging.error(f"❌ Failed to load runtime config: {e}. Using default config.")

# Initialize FastAPI
app = FastAPI(title="Tee Time Checker API", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

class SearchEntry(BaseModel):
    date: str
    start: str
    end: str
    course: str = "All"

class SearchesPayload(BaseModel):
    searches: List[SearchEntry]

@app.get("/")
def root():
    """API root - health check"""
    return {
        "status": "online",
        "message": "Tee Time API is live. Access UI at /static/index.html or /static/"
    }

@app.post("/set")
def set_config(payload: SearchesPayload):
    """Update scraper configuration with one or more date/time/course searches"""
    global in_memory_config

    if not payload.searches:
        return {"error": "At least one search entry is required."}

    for entry in payload.searches:
        if entry.course not in VALID_COURSES:
            return {"error": f"Invalid course '{entry.course}'. Must be one of: {', '.join(sorted(VALID_COURSES))}"}

    in_memory_config["searches"] = [entry.model_dump() for entry in payload.searches]

    try:
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(in_memory_config, f, indent=2)
        logging.info(f"✅ Runtime config updated: {in_memory_config}")
        return {
            "message": "Configuration updated successfully",
            "current_config": in_memory_config
        }
    except Exception as e:
        logging.error(f"❌ Failed to save runtime config: {e}")
        return {
            "error": f"Configuration updated in memory but failed to save: {e}",
            "current_config": in_memory_config
        }

@app.get("/get")
def get_config():
    """Get current scraper configuration"""
    if os.path.exists(RUNTIME_CONFIG_FILE):
        try:
            with open(RUNTIME_CONFIG_FILE, "r") as f:
                current_saved_config = normalize_config(json.load(f))
                return {"current_config": current_saved_config}
        except Exception as e:
            logging.error(f"❌ Failed to load runtime config for /get endpoint: {e}")
            return {"current_config": in_memory_config}
    else:
        return {"current_config": in_memory_config}

@app.get("/check")
def check():
    """Get cached tee time results"""
    try:
        results = get_cached_tee_times()
        return {"results": results}
    except Exception as e:
        logging.error(f"❌ Error checking cached results: {e}")
        return {"error": str(e)}

@app.get("/run-scraper")
def run_scraper_endpoint(background_tasks: BackgroundTasks):
    """
    Trigger scraper run in background.
    Uses FastAPI's BackgroundTasks for better concurrency control.
    """
    global in_memory_config

    # Check if scraper is paused
    if in_memory_config.get("is_paused", False):
        logging.info("⏸️ Scraper is currently paused. Not starting a new run.")
        return {
            "message": "Scraper is currently paused.",
            "is_paused": True
        }

    current_searches = in_memory_config.get("searches", DEFAULT_CONFIG["searches"])

    logging.info(f"🚀 Triggered scraper run with {len(current_searches)} search(es): {current_searches}")

    # Run scraper in background using FastAPI's BackgroundTasks
    # This is safer than threading.Thread as it integrates with FastAPI's lifecycle
    background_tasks.add_task(run_scraper, current_searches)

    return {
        "message": "Scraper started in background",
        "config": {
            "searches": current_searches
        }
    }

@app.get("/toggle-scraper-pause")
def toggle_scraper_pause():
    """Toggle the scraper pause state"""
    global in_memory_config

    current_state = in_memory_config.get("is_paused", False)
    new_state = not current_state
    in_memory_config["is_paused"] = new_state

    try:
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(in_memory_config, f, indent=2)

        status_message = "paused" if new_state else "resumed"
        logging.info(f"✅ Scraper {status_message}. New state saved: {in_memory_config}")

        return {
            "message": f"Scraper has been {status_message}.",
            "is_paused": new_state,
            "current_config": in_memory_config
        }
    except Exception as e:
        logging.error(f"❌ Failed to save pause state: {e}")
        return {
            "error": f"Failed to save pause state: {e}",
            "is_paused": new_state,
            "current_config": in_memory_config
        }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "config_loaded": os.path.exists(RUNTIME_CONFIG_FILE),
        "is_paused": in_memory_config.get("is_paused", False)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
