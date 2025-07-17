# checker.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime
import time
import os

# Config - These are constant across runs, so they stay global
USERNAME = "C399"
PASSWORD = "Goblue8952"# Assuming this is correct from previous context
LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"

# IMPORTANT: Ensure this path is correct for your system!
# You may need to update this if your chromedriver isn't here.
CHROMEDRIVER_PATH = "/Users/danielchodos/Desktop/tee-time-api/chromedriver"


def check_tee_times(date_str: str, start_time_str: str, end_time_str: str):
    """
    Checks for available tee times within a specified date and time range.

    Args:
        date_str (str): The date to check, format MM/DD/YYYY.
        start_time_str (str): The start of the time window, format HH:MM AM/PM.
        end_time_str (str): The end of the time window, format HH:MM AM/PM.

    Returns:
        list: A list of strings describing available tee times, or an error message.
    """
    try:
        # Parse date and time inputs here, inside the function
        # because they are passed as arguments.
        CHECK_MONTH = date_str.split('/')[0] # Get month if needed for calendar navigation
        CHECK_DAY = date_str.split('/')[1]
        CHECK_YEAR = date_str.split('/')[2] # Get year if needed

        START_TIME = datetime.strptime(start_time_str, "%I:%M %p").time() # Use .time() for comparison
        END_TIME = datetime.strptime(end_time_str, "%I:%M %p").time() # Use .time() for comparison

    except Exception as e:
        return [f"Error parsing date/time inputs: {e}. Please ensure formats are MM/DD/YYYY and HH:MM AM/PM."]

    options = Options()
    #options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    # Add an option to prevent the "DevTools listening on ws://" message if it's bothering you
    options.add_argument("--disable-logging")

    service = Service(CHROMEDRIVER_PATH)
    driver = None # Initialize driver to None for proper cleanup
    times_found = []

    try:
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 15)

        # Login
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "lgUserName")))
        driver.find_element(By.ID, "lgUserName").send_keys(USERNAME)
        driver.find_element(By.ID, "lgPassword").send_keys(PASSWORD)
        driver.find_element(By.ID, "lgLoginButton").click()
        wait.until(EC.url_changes(LOGIN_URL)) # Wait for the URL to change after login

        # Navigate to Tee Sheet
        driver.get(TEE_SHEET_URL)
        # Wait for the iframe to be present and switch to it
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrforetees")))

        # Select the date
        # You need to select the month/year first if the target date is not in the current view
        # This part of the script assumes the calendar for the month is already visible.
        # If your target date spans months, you'll need additional logic here to click
        # "next month" arrows on the calendar interface.
        wait.until(EC.presence_of_element_located((By.ID, "member_select_calendar1")))
        date_elements = driver.find_elements(By.CSS_SELECTOR, "#member_select_calendar1 a.ui-state-default")

        # Dynamically find the target date link based on CHECK_DAY
        target_date = next((el for el in date_elements if el.text.strip() == CHECK_DAY), None)
        if target_date:
            driver.execute_script("arguments[0].click();", target_date)
            # Give the page some time to load after clicking the date
            time.sleep(3)
        else:
            return [f"Error: Target day {CHECK_DAY} not found in the visible calendar."]

        # Select "-ALL-" for filters (if available and needed)
        for select_el in driver.find_elements(By.TAG_NAME, "select"):
            try:
                sel = Select(select_el)
                # Check for "All" or "-ALL-" case-insensitively
                if any("all" in opt.text.lower() for opt in sel.options):
                    sel.select_by_visible_text(next(opt.text for opt in sel.options if "all" in opt.text.lower()))
                    break # Assuming only one such select element needs to be processed
            except Exception as e:
                # print(f"Could not process select element: {e}") # For debugging
                continue

        time.sleep(3) # Give time for the filter to apply and page to update

        # Parse tee times
        soup = BeautifulSoup(driver.page_source, "html.parser")
        tee_sheet = soup.find("div", class_="member_sheet_table")

        if not tee_sheet:
            return ["No tee sheet found on the page."]

        for row in tee_sheet.find_all("div", class_="rwdTr"):
            cols = row.find_all("div", class_="rwdTd")
            if len(cols) >= 5:
                time_element = cols[0].find("div", class_="time_slot") or cols[0].find("a", class_="teetime_button")
                time_text = time_element.get_text(strip=True) if time_element else ""
                course = cols[2].get_text(strip=True)
                open_slots = cols[4].get_text(strip=True)

                try:
                    # Parse the time from the row for comparison
                    row_time_obj = datetime.strptime(time_text, "%I:%M %p").time()

                    # Compare only time parts
                    if START_TIME <= row_time_obj <= END_TIME and "Open" in open_slots:
                        num_open = open_slots.split(" ")[0]
                        times_found.append(f"{time_text} - {course} - {num_open} slots open")
                except ValueError: # Handle cases where time_text might not be a valid time
                    continue
                except Exception as e:
                    # print(f"Error processing row: {e}") # For debugging
                    continue

    except TimeoutException:
        return ["A timeout occurred. The page or element took too long to load."]
    except NoSuchElementException as e:
        return [f"Required element not found: {e}. Check selectors or page structure."]
    except Exception as e:
        return [f"An unexpected error occurred: {str(e)}"]
    finally:
        if driver:
            driver.quit() # Ensure the browser is closed

    if not times_found:
        return ["No tee times found for the specified criteria."]
    return times_found
