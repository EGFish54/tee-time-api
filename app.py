from fastapi import FastAPI, Query
from checker import get_cached_tee_times
import uvicorn
import subprocess
import os
import json
import threading
from scraper import run_scraper
import logging

# Configure logging for app.py as well
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


# Install Playwright browser at runtime (only if it hasn't been installed by postBuildCommand)
# It's generally better to rely on postBuildCommand in render.yaml
try:
    # This line might be redundant if postBuildCommand: playwright install is reliable.
    # Keeping it for robustness, but be aware of potential overhead.
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    logging.error(f"Failed to install Playwright at runtime: {e}")

# New file for runtime configuration that can be updated during the app's life
RUNTIME_CONFIG_FILE = "current_config.json"
DEFAULT_CONFIG = { # Your default configuration
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM"
}

# Initialize in_memory_config at startup with defaults
in_memory_config = DEFAULT_CONFIG.copy()

# Try to load config from the runtime file (if it exists)
# This will pick up the last saved config if the app restarts within the same ephemeral container
if os.path.exists(RUNTIME_CONFIG_FILE):
    try:
        with open(RUNTIME_CONFIG_FILE, "r") as f:
            loaded_config = json.load(f)
            in_memory_config.update(loaded_config)
            logging.info(f"Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
    except Exception as e:
        logging.error(f"Failed to load runtime config from file {RUNTIME_CONFIG_FILE}: {e}")
else:
    logging.info(f"No {RUNTIME_CONFIG_FILE} found, using default config: {in_memory_config}")


app = FastAPI()

@app.get("/")
def root():
    return {"status": "Tee Time API is live"}

@app.get("/set")
def set_time(
    date: str = Query(..., description="Format: MM/DD/YYYY"),
    start: str = Query(..., description="Format: HH:MM AM/PM"),
    end: str = Query(..., description="Format: HH:MM AM/PM")
):
    try:
        # Update in memory
        in_memory_config["date"] = date
        in_memory_config["start"] = start
        in_memory_config["end"] = end

        # Save to runtime file (this will persist for the current Render instance)
        with open(RUNTIME_CONFIG_FILE, "w") as f:
            json.dump(in_memory_config, f)
        logging.info(f"Config updated and saved to {RUNTIME_CONFIG_FILE}: {in_memory_config}")
        return {"message": "Time window updated successfully"}
    except Exception as e:
        logging.error(f"Error setting time window: {e}")
        return {"error": str(e)}

@app.get("/get")
def get_time_window():
    # Try to load from runtime file first for the most current state
    if os.path.exists(RUNTIME_CONFIG_FILE):
        try:
            with open(RUNTIME_CONFIG_FILE, "r") as f:
                current_saved_config = json.load(f)
                return {"current_config": current_saved_config}
        except Exception as e:
            logging.error(f"Failed to load runtime config for /get endpoint: {e}")
            # Fallback to in-memory if file read fails
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
    # Capture the current configuration from in_memory_config
    # This ensures the spawned thread uses the latest config updated by /set
    current_date = in_memory_config["date"]
    current_start = in_memory_config["start"]
    current_end = in_memory_config["end"]

    logging.info(f"Triggered scraper run with config: Date={current_date}, Start={current_start}, End={current_end}")

    def scraper_thread():
        # Pass the explicit captured values to run_scraper
        run_scraper(current_date, current_start, current_end)

    threading.Thread(target=scraper_thread).start()
    return {"message": "Scraper started in background"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
