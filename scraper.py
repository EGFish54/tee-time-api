import logging
from checker import check_tee_times

def run_scraper(searches=None):
    """
    Wrapper function to run the scraper with provided configuration.
    All the heavy lifting is done in checker.py
    """
    logging.info(f"Triggered scraper run with {len(searches) if searches else 0} search(es): {searches}")

    # Validate inputs
    if not searches:
        error_msg = "Error: No search configuration provided to scraper."
        logging.error(error_msg)
        return [error_msg]

    # Call the main checker function
    # The concurrency control and caching are handled within checker.py
    results = check_tee_times(searches)

    logging.info("Scraper run completed.")
    return results
