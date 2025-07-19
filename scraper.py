import json
import os
from checker import check_tee_times

CONFIG_FILE = "config.json"
CACHE_FILE = "cached_results.json"

def run_scraper():
    if not os.path.exists(CONFIG_FILE):
        print("❌ config.json not found.")
        return

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        results = check_tee_times(config["date"], config["start"], config["end"])

        with open(CACHE_FILE, "w") as f:
            json.dump({"results": results}, f)

        print("✅ Tee times updated and cached.")
    except Exception as e:
        print(f"💥 Error during scraping: {e}")

if __name__ == "__main__":
    run_scraper()
