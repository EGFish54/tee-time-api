from checker import check_tee_times, cached_results
import json
import os

CONFIG_FILE = "config.json"

def run_scraper():
    # Load from file instead of importing
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            date = config["date"]
            start = config["start"]
            end = config["end"]
            results = check_tee_times(date, start, end)
            cached_results.clear()
            cached_results.extend(results)
        print("✅ Tee times updated and cached.")
    except Exception as e:
        print(f"❌ Scraper error: {e}")
