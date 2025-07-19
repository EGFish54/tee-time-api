from checker import check_tee_times, cached_results
from app import CONFIG  # 👈 This imports the in-memory CONFIG dictionary

def run_scraper():
    try:
        print("🧼 Running tee time scraper...")
        date = CONFIG["date"]
        start = CONFIG["start"]
        end = CONFIG["end"]

        results = check_tee_times(date, start, end)
        cached_results.clear()
        cached_results.extend(results)
        print("✅ Tee times updated and cached.")
    except Exception as e:
        print(f"❌ Scraper error: {e}")
