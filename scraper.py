import logging
from checker import check_tee_times

def run_scraper(date=None, start=None, end=None, course="All"):
    """
    Wrapper function to run the scraper with provided configuration.
    All the heavy lifting is done in checker.py
    """
    logging.info(f"Triggered scraper run with config: Date={date}, Start={start}, End={end}, Course={course}")

    # Validate inputs
    if date is None or start is None or end is None:
        error_msg = "Error: Incomplete configuration provided to scraper."
        logging.error(error_msg)
        return [error_msg]

    # Call the main checker function
    # The concurrency control and caching are handled within checker.py
    results = check_tee_times(date, start, end, course)
    
    logging.info("Scraper run completed.")
    return results
