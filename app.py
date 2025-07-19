from fastapi import FastAPI, Query
from checker import check_tee_times, get_cached_tee_times
import uvicorn
import subprocess
import os
import json
import threading
from scraper import run_scraper  # 👈 Make sure scraper.py has this function

# Install Playwright browser at runtime
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Failed to install Playwright at runtime: {e}")

CONFIG_FILE = "config.json"

# Ensure config.json exists with defaults
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "date": "07/23/2025",
            "start": "08:00 AM",
            "end": "09:00 AM"
        }, f)

app = FastAPI()

@app.get("/set")
def set_time(
    date: str = Query(..., description="Format: MM/DD/YYYY"),
    start: str = Query(..., description="Format: HH:MM AM/PM"),
    end: str = Query(..., description="Format: HH:MM AM/PM")
):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"date": date, "start": start, "end": end}, f)
        return {"message": "Time window updated successfully"}
    except Exception as e:
        return {"error": str(e)}

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
        run_scraper()
    threading.Thread(target=scraper_thread).start()
    return {"message": "Scraper started in background"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)



@app.get("/")
def root():
    return {"status": "Tee Time API is live"}

@app.get("/get")
def get_time_window():
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return {"current_config": config}
    except Exception as e:
        return {"error": str(e)}
    
