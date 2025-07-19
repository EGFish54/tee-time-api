import os
import json
import logging
from checker import check_tee_times, cached_results

CONFIG_FILE = "config.json"

# In-memory config as fallback if reading config.json fails
in_memory_config = {
    "date": "07/23/2025",
    "start": "08:00 AM",
    "end": "09:00 AM"
}

# Try to load from config file into in-memory config
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            in_memory_config = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read config.json: {e}")

def run_scraper(date=None, start=None, end=None):
    global cached_results
    logging.info("Starting scraper with provided or fallback config")

    # Use provided values or fallback to in_memory_config
    date = date or in_memory_config["date"]
    start = start or in_memory_config["start"]
    end = end or in_memory_config["end"]

    results = check_tee_times(date, start, end)
    cached_results = results
    logging.info("Scraper results cached.")
