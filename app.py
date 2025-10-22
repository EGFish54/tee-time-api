from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from checker import check_tee_times, get_cached_tee_times
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

# Default configuration
DEFAULT_CONFIG = {
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM",
    "is_paused": False
}

# In-memory configuration
in_memory_config = DEFAULT_CONFIG.copy()

# Try to load config from file on startup
if os.path.exists(RUNTIME_CONFIG_FILE):
    try:
        with open(RUNTIME_CONFIG_FILE, "r") as f:
            loaded_config = json.load(f)
            in_memory_config.update(loaded_config)
            
            # Ensure 'is_paused' exists
            if "is_paused" not in in_memory_config:
                in_memory_config["is_paused"] = DEFAULT_CONFIG["is_paused"]
            
            logging.info(f"✅ Loaded config from {RUNTIME_CONFIG_FILE}: {in_memory_config}")
    except json.JSONDecodeError:
        logging.warning(f"⚠️ Error decoding JSON from {RUNTIME_CONFIG_FILE}. Using default config.")
    except Exception as e:
        logging.error(f"❌ Failed to load runtime config: {e}. Using default config.")

# Initialize FastAPI
app = FastAPI(title="Tee Time Checker API", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
def root():
    """API root - health check"""
    return {
        "status": "online",
        "message": "Tee Time API is live. Access UI at /static/index.html or /static/"
    }

@app.get("/set")
def set_config(date: str = Query(...), start: str = Query(...), end: str = Query(...)):
    """Update scraper configuration"""
    global in_memory_config
    
    in_memory_config["date"] = date
    in_memory_config["start"] = start
    in_memory_config["end"] = end
    
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
                current_saved_config = json.load(f)
                
                # Ensure 'is_paused' is included
                if "is_paused" not in current_saved_config:
                    current_saved_config["is_paused"] = DEFAULT_CONFIG["is_paused"]
                
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
    
    current_date = in_memory_config["date"]
    current_start = in_memory_config["start"]
    current_end = in_memory_config["end"]
    
    logging.info(f"🚀 Triggered scraper run with config: Date={current_date}, Start={current_start}, End={current_end}")
    
    # Run scraper in background using FastAPI's BackgroundTasks
    # This is safer than threading.Thread as it integrates with FastAPI's lifecycle
    background_tasks.add_task(run_scraper, current_date, current_start, current_end)
    
    return {
        "message": "Scraper started in background",
        "config": {
            "date": current_date,
            "start": current_start,
            "end": current_end
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
