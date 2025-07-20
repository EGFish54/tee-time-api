from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles # ADD THIS LINE
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
            in_memory_config.update(loaded_config) # Update defaults with saved config
            logging.info(f"Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
    except json.JSONDecodeError:
        logging.warning(f"Error decoding JSON from {RUNTIME_CONFIG_FILE}. Using default config.")
    except Exception as e:
        logging.error(f"Failed to load runtime config from {RUNTIME_CONFIG_FILE}: {e}. Using default config.")


app = FastAPI()

# ADD THIS BLOCK AFTER app = FastAPI()
# Serve static files from the 'static' directory
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
def root():
    return {"status": "Tee Time API is live"}


@app.get("/set")
def set_config(date: str = Query(...), start: str = Query(...), end: str = Query(...)):
    global in_memory_config # Declare that we intend to modify the global variable

    # Update the in-memory config
    in_memory_config["date"] = date
    in_memory_config["start"] = start
    in_memory_config["end"] = end

    # Also save to a file for persistence across app restarts (in same ephemeral container)
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
    # Prioritize loading from file to ensure we get the latest saved state
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
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
