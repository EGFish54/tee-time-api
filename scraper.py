import os
import json
import logging
from checker import check_tee_times, cached_results # Ensure check_tee_times and cached_results are imported from checker

# In scraper.py, we will remove the old CONFIG_FILE and in_memory_config.
# This file will now strictly use the parameters passed to run_scraper from app.py.

def run_scraper(date=None, start=None, end=None):
    global cached_results # If cached_results is used globally in scraper.py, keep this.
                          # However, it's defined and updated in checker.py primarily.

    # This log will show what config run_scraper actually received from app.py
    logging.info(f"Starting scraper with received config: Date={date}, Start={start}, End={end}")

    # Ensure date, start, and end are not None before passing
    if date is None or start is None or end is None:
        logging.error("Scraper received incomplete configuration. Cannot proceed.")
        # Optionally, you could fall back to defaults or raise an error
        return ["Error: Incomplete configuration provided to scraper."]

    # Call check_tee_times with the explicitly passed parameters
    results = check_tee_times(date, start, end)
    
    # Update cached_results if necessary (though it's primarily managed in checker.py)
    # This line might be redundant if checker.py directly handles caching.
    # cached_results = results 
    
    logging.info("Scraper run completed.") # More generic message here as checker.py logs details
