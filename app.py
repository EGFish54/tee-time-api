from fastapi import FastAPI, Query
from checker import check_tee_times
import uvicorn
import subprocess
import os
import json

# Install Playwright browser at runtime
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Failed to install Playwright at runtime: {e}")

CONFIG_FILE = "config.json"
CACHE_FILE = "cached_results.json"

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
        with open("cached_results.json", "r") as f:
            data = json.load(f)
        return data  # already has {"results": [...]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/cached")
def cached():
    try:
        if not os.path.exists(CACHE_FILE):
            return {"results": ["No cached results available yet."]}
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        return {"results": data.get("results", ["No cached results found"])}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
