from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import os
import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time # Added for wait_for_selector timeout

# CONFIG
USERNAME = "C399"
PASSWORD = "Goblue8952" # Note: This is a hardcoded password. Ensure it's not sensitive.
LOGIN_URL = "https://www.prestonwood.com/members-login"
TEE_SHEET_URL = "https://www.prestonwood.com/golf/tee-times-43.html"
# CHECK_DAY will be dynamically set from date_str now - removed CHECK_DAY from here
LOG_FILE = "available_tee_times.txt"
CACHE_FILE = "cached_results.json"
SCREENSHOT_DIR = "screenshots" # Directory to save screenshots

# Logging setup
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
today_str = datetime.today().strftime("%Y-%m-%d")
log_path = os.path.join(log_dir, f"tee_times_{today_str}.log")
# Ensure logging is configured to also output to console for Render logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s",
                    handlers=[
                        logging.FileHandler(log_path),
                        logging.StreamHandler() # Add StreamHandler to output to console/Render logs
                    ])

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Email setup
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL") or GMAIL_USER # Fallback if RECIPIENT_EMAIL not set

def send_email(subject, body):
    if not GMAIL_USER or not GMAIL_PASS or not RECIPIENT_EMAIL:
        logging.error("Email credentials (GMAIL_USER, GMAIL_PASS, RECIPIENT_EMAIL) are not fully set. Cannot send email.")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Use 587 for TLS, 465 for SSL. Most modern SMTP uses 587.
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls() # Secure the connection
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        logging.info("📧 Email sent!")
    except Exception as e:
        logging.error(f"❌ Failed to send email: {e}")
        # Log the specific error for debugging
        if hasattr(e, 'smtp_code') and hasattr(e, 'smtp_error'):
            logging.error(f"SMTP Error Code: {e.smtp_code}, Message: {e.smtp_error}")

def take_screenshot(page, name_prefix="screenshot"):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{name_prefix}_{timestamp}.png")
        page.screenshot(path=screenshot_path)
        logging.info(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        logging.error(f"Could not take screenshot {name_prefix}: {e}")

def check_tee_times(date_str, start_str, end_str):
    # THIS IS THE NEW LOGGING LINE to confirm the config received by checker.py
    logging.info(f"Scraper received config: Date={date_str}, Start={start_str}, End={end_str}")

    try:
        target_date = datetime.strptime(date_str, "%m/%d/%Y")
        start_time_obj = datetime.strptime(start_str, "%I:%M %p").time()
        end_time_obj = datetime.strptime(end_str, "%I:%M %p").time()
        
        # Extract the day from the date_str to use for clicking the calendar
        check_day = str(target_date.day)

    except ValueError as e:
        logging.error(f"Configuration parsing error: {e}. Please check date/time formats.")
        return [f"Error: Invalid date/time format in config: {e}"]

    with sync_playwright() as p:
        browser = None # Initialize browser to None
        try:
            # Use headless=True for production on Render
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logging.info("🔐 Logging in via Playwright")
            page.goto(LOGIN_URL, wait_until="load", timeout=90000) # Increased timeout
            take_screenshot(page, "after_login_page_load")

            # Fill login form
            page.fill("input#member_login_id", USERNAME)
            page.fill("input#password", PASSWORD)
            page.click("input#login")
            take_screenshot(page, "after_successful_login")
            
            # Wait for navigation to complete after login, potentially to tee sheet page or a redirect
            page.wait_for_load_state("domcontentloaded", timeout=60000) # Wait for initial page content
            take_screenshot(page, "after_login_redirect_dom_load")

            # Navigate to the tee sheet page
            logging.info("➡️ Attempting to navigate to tee times page.")
            page.goto(TEE_SHEET_URL, wait_until="load", timeout=90000) # Increased timeout
            
            # Wait for a key element on the main tee sheet page
            logging.info("Waiting for a key element on the main tee sheet page (#content) to confirm load.")
            page.wait_for_selector("#content", timeout=90000) # Wait for the main content div
            take_screenshot(page, "after_tee_sheet_main_page_loaded_element")

            # Find and interact with the iframe
            logging.info("🔍 Searching for iframe 'ifrforetees'.")
            iframe_handle = page.wait_for_selector("iframe#ifrforetees", timeout=60000)
            if iframe_handle:
                logging.info("✅ Found iframe 'ifrforetees'. Waiting for iframe content to load (domcontentloaded).")
                iframe = iframe_handle.content_frame()
                iframe.wait_for_load_state("domcontentloaded", timeout=90000)
                take_screenshot(page, "after_iframe_dom_load")

                logging.info("✅ Iframe content loaded (domcontentloaded). Waiting for networkidle in iframe.")
                iframe.wait_for_load_state("networkidle", timeout=90000)
                take_screenshot(page, "after_iframe_network_idle")

                # Select the date
                logging.info(f"📅 Attempting to select date: {date_str} (Day: {check_day}) by waiting for #member_select_calendar1 within iframe.")
                # Wait for the calendar element to be ready
                iframe.wait_for_selector("#member_select_calendar1", timeout=60000)
                take_screenshot(page, "before_date_selection_in_iframe")
                
                # Click the specific day in the calendar (assuming it's a direct clickable element)
                # The calendar typically uses 'td' elements or 'a' tags within them
                logging.info(f"📆 Clicking on target date: {check_day}")
                
                # Attempt to click based on the day number
                # This selector might need adjustment based on the actual HTML structure of the calendar
                iframe.locator(f"td.ui-datepicker-week-end a:has-text('{check_day}')").click(timeout=30000) # Example for weekend days
                iframe.locator(f"td a:has-text('{check_day}')").first.click(timeout=30000) # More general, click the first matching day
                take_screenshot(page, "after_date_click_in_iframe")

                # Wait for the tee sheet to refresh after date selection
                iframe.wait_for_load_state("networkidle", timeout=90000)
                take_screenshot(page, "after_date_selection_refresh_iframe")

                # Select "All" courses if applicable
                logging.info("🔄 Attempting to set course to '-ALL-'.")
                course_dropdown = iframe.locator("select#course_id")
                if course_dropdown.is_visible():
                    course_dropdown.select_option(value="-ALL-")
                    logging.info("✅ Course set to '-ALL-'.")
                    iframe.wait_for_load_state("networkidle", timeout=90000) # Wait for refresh after course selection
                    take_screenshot(page, "after_course_select_in_iframe")
                else:
                    logging.info("Course dropdown not found or not visible, skipping course selection.")


                # Parse the tee sheet
                logging.info("📄 Parsing tee sheet content.")
                # Wait for the tee sheet table to appear. Adjust selector if necessary.
                iframe.wait_for_selector("table.tbl_tee_times", timeout=60000)
                tee_sheet_html = iframe.content()
                
                soup = BeautifulSoup(tee_sheet_html, "html.parser")
                tee_sheet_table = soup.find("table", class_="tbl_tee_times")

                if not tee_sheet_table:
                    logging.warning("⚠️ Tee sheet table not found in HTML. Check selector or page load.")
                    take_screenshot(page, "error_tee_sheet_table_missing")
                    return ["No tee sheet table found."]

                logging.info("✅ Tee sheet table found in HTML.")
                
                found = []
                # Iterate through rows in the tee sheet table to find tee times
                # Adjust selectors based on the actual table structure
                for row in tee_sheet_table.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) > 4: # Assuming at least 5 columns: Time, Player1, Player2, Course, OpenSlots
                        try:
                            time_text = cols[0].get_text(strip=True)
                            course = cols[3].get_text(strip=True)
                            open_slots_text = cols[4].get_text(strip=True)

                            row_time_obj = datetime.strptime(time_text, "%I:%M %p").time()

                            if start_time_obj <= row_time_obj <= end_time_obj and "Open" in open_slots_text:
                                num_open = open_slots_text.split(" ")[0]
                                msg = f"{time_text} - {course} - {num_open} slots open"
                                found.append(msg)
                        except ValueError:
                            # Handle cases where time_text might not be a valid time format
                            continue
                        except IndexError:
                            # Handle cases where row might not have enough columns
                            continue

                # Log and process new times
                previous = []
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r") as f:
                        previous = [line.strip() for line in f.readlines()]

                new_times = [t for t in found if t not in previous]

                current_results = found if found else ["No new tee times found for the selected criteria."]
                
                # Save current results to cache file for /check endpoint
                with open(CACHE_FILE, "w") as cache_file:
                    json.dump({"results": current_results}, cache_file)


                if new_times:
                    logging.info("✅ New tee times found:\n" + "\n".join(new_times))
                    with open(LOG_FILE, "w") as f:
                        f.write("\n".join(found)) # Log all found times, not just new ones, to update previous
                    send_email("New Tee Times Available", "\n".join(new_times))
                    return new_times
                else:
                    logging.info("🟢 No new tee times found (or no changes since last check).")
                    return ["No new tee times found (or no changes since last check)."]

        except Exception as e:
            logging.error(f"💥 Error during scraping: {e}")
            error_message = f"An error occurred during scraping: {e}"
            take_screenshot(page, "error_state") # Take screenshot on error
            
            # Save error message to cache file
            with open(CACHE_FILE, "w") as cache_file:
                json.dump({"results": [error_message]}, cache_file)
            return [error_message]
        finally:
            if browser: # Ensure browser object exists before trying to close
                browser.close()
                logging.info("Browser closed.")


def get_cached_tee_times():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                return data.get("results", ["No cached tee times found or error in cache file."])
        except json.JSONDecodeError:
            return ["Error reading cached_results.json, file might be corrupted."]
    else:
        return ["No cached tee times found (cache file does not exist)."]
