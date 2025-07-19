from checker import check_tee_times, cached_results
import json
import os

CONFIG_FILE = "config.json"

def run_scraper(date=None, start=None, end=None):
    try:
        if not date or not start or not end:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    date = config["date"]
                    start = config["start"]
                    end = config["end"]
            else:
                print("❌ No config file and no parameters provided.")
                return

        results = check_tee_times(date, start, end)
        cached_results.clear()
        cached_results.extend(results)
    except Exception as e:
        print(f"Scraper error: {e}")
