import os
import json
import logging
# ONLY import check_tee_times. Remove cached_results from here.
from checker import check_tee_times

# In scraper.py, we will remove the old CONFIG_FILE and in_memory_config.
# This file will now strictly use the parameters passed to run_scraper from app.py.

def run_scraper(date=None, start=None, end=None):
    # Remove 'global cached_results' as it's not needed here and caused the import error.
    # global cached_results # REMOVE THIS LINE IF IT WAS PRESENT IN YOUR FILE

    # This log will show what config run_scraper actually received from app.py
    logging.info(f"Starting scraper with received config: Date={date}, Start={start}, End={end}")

    # Ensure date, start, and end are not None before passing
    if date is None or start is None or end is None:
        logging.error("Scraper received incomplete configuration. Cannot proceed.")
        return ["Error: Incomplete configuration provided to scraper."]

    # Call check_tee_times with the explicitly passed parameters
    results = check_tee_times(date, start, end)
    
    # The caching logic is handled within checker.py's check_tee_times.
    # So, the line 'cached_results = results' is not needed here in scraper.py
    # cached_results = results # REMOVE OR COMMENT OUT THIS LINE IF PRESENT
    
    logging.info("Scraper run completed.") # More generic message here as checker.py logs details
