from fastapi import FastAPI, Query
from checker import get_cached_tee_times
import uvicorn
import subprocess
import os
import json
import threading
from scraper import run_scraper

# Install Playwright browser at runtime
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Failed to install Playwright at runtime: {e}")

CONFIG_FILE = "config.json"
in_memory_config = {
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM"
}

# Try to load config from file (if it exists)
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            in_memory_config.update(json.load(f))
    except Exception as e:
        print(f"Failed to load config from file: {e}")

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

        # Attempt to save to file for local dev use (ignored on Render)
        with open(CONFIG_FILE, "w") as f:
            json.dump(in_memory_config, f)

        return {"message": "Time window updated successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/get")
def get_time_window():
    return {"current_config": in_memory_config}

@app.get("/check")
def check():
    try:
        results = get_cached_tee_times()
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

@app.get("/run-scraper")
def run_scraper_background():
    def scraper_thread():
        run_scraper(in_memory_config["date"], in_memory_config["start"], in_memory_config["end"])
    threading.Thread(target=scraper_thread).start()
    return {"message": "Scraper started in background"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
